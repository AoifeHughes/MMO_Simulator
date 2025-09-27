"""
Centralized Action Constants

This module provides centralized distance and threshold constants for all game actions
to eliminate hardcoded values and ensure consistency across client and server.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ActionDistances:
    """Distance constants for all game actions"""

    # Resource gathering distances
    FISHING_RANGE: float = 1.2
    WOOD_HARVESTING_RANGE: float = 1.2
    MINING_RANGE: float = 1.2

    # Combat distances
    MELEE_ATTACK_RANGE: float = 2.0
    RANGED_ATTACK_RANGE: float = 8.0
    SPELL_CAST_RANGE: float = 6.0

    # Social interaction distances
    TRADE_RANGE: float = 5.0
    CHAT_RANGE: float = 10.0

    # Movement and positioning
    ARRIVAL_THRESHOLD: float = 0.5
    PATHFINDING_THRESHOLD: float = 0.3


@dataclass
class PositionThresholds:
    """Position validation and correction thresholds"""

    # Server position validation
    POSITION_CORRECTION_THRESHOLD: float = 1.0  # Max distance for small corrections
    LARGE_CORRECTION_THRESHOLD: float = 2.0  # Threshold for large position jumps
    SMOOTH_CORRECTION_THRESHOLD: float = 0.5  # When to apply smooth corrections

    # Client-side validation
    VALIDATION_BUFFER: float = 0.05  # Floating point precision buffer
    POSITIONING_TOLERANCE: float = 0.1  # Two-phase action positioning tolerance

    # Smoothing parameters
    SMOOTH_CORRECTION_FACTOR: float = (
        0.7  # Percentage of correction to apply immediately
    )
    INTERPOLATION_THRESHOLD: float = 0.1  # When to interpolate vs snap


@dataclass
class ActionTimeouts:
    """Timeout values for various actions"""

    # Action execution timeouts
    FISHING_TIMEOUT: float = 8.0
    HARVESTING_TIMEOUT: float = 6.0
    CRAFTING_TIMEOUT: float = 10.0
    TRADING_TIMEOUT: float = 30.0

    # Movement timeouts
    POSITIONING_TIMEOUT: float = 10.0  # Max time to reach action position
    PATHFINDING_TIMEOUT: float = 15.0  # Max time for pathfinding to complete


@dataclass
class DebugConfig:
    """Debug and statistics configuration"""

    # Distance tracking
    TRACK_POSITION_DISCREPANCIES: bool = True  # Log client-server position differences
    MAX_ACCEPTABLE_DISCREPANCY: float = 0.5  # Log if difference exceeds this
    POSITION_HISTORY_SIZE: int = 100  # How many position updates to track

    # Performance monitoring
    LOG_ACTION_PROCESSING_TIME: bool = True  # Track action processing performance
    LOG_DISTANCE_VALIDATION: bool = False  # Detailed distance validation logs
    LOG_POSITION_CORRECTIONS: bool = True  # Log all position corrections


# Global instances for easy access
DISTANCES = ActionDistances()
THRESHOLDS = PositionThresholds()
TIMEOUTS = ActionTimeouts()
DEBUG = DebugConfig()


def get_action_range(action_name: str) -> float:
    """
    Get the range for a specific action by name.

    Args:
        action_name: The action name (e.g., 'fishing', 'wood_harvesting')

    Returns:
        The range for the action in world units

    Raises:
        ValueError: If action_name is not recognized
    """
    action_ranges = {
        "fishing": DISTANCES.FISHING_RANGE,
        "wood_harvesting": DISTANCES.WOOD_HARVESTING_RANGE,
        "mining": DISTANCES.MINING_RANGE,
        "melee_attack": DISTANCES.MELEE_ATTACK_RANGE,
        "ranged_attack": DISTANCES.RANGED_ATTACK_RANGE,
        "spell_cast": DISTANCES.SPELL_CAST_RANGE,
        "trade": DISTANCES.TRADE_RANGE,
        "chat": DISTANCES.CHAT_RANGE,
    }

    if action_name not in action_ranges:
        raise ValueError(
            f"Unknown action: {action_name}. Valid actions: {list(action_ranges.keys())}"
        )

    return action_ranges[action_name]


def get_distance_stats() -> Dict[str, Any]:
    """
    Get current distance configuration as a dictionary for debugging.

    Returns:
        Dictionary containing all distance constants
    """
    return {
        "action_distances": {
            "fishing_range": DISTANCES.FISHING_RANGE,
            "wood_harvesting_range": DISTANCES.WOOD_HARVESTING_RANGE,
            "mining_range": DISTANCES.MINING_RANGE,
            "melee_attack_range": DISTANCES.MELEE_ATTACK_RANGE,
            "ranged_attack_range": DISTANCES.RANGED_ATTACK_RANGE,
            "spell_cast_range": DISTANCES.SPELL_CAST_RANGE,
            "trade_range": DISTANCES.TRADE_RANGE,
            "chat_range": DISTANCES.CHAT_RANGE,
            "arrival_threshold": DISTANCES.ARRIVAL_THRESHOLD,
            "pathfinding_threshold": DISTANCES.PATHFINDING_THRESHOLD,
        },
        "position_thresholds": {
            "position_correction_threshold": THRESHOLDS.POSITION_CORRECTION_THRESHOLD,
            "large_correction_threshold": THRESHOLDS.LARGE_CORRECTION_THRESHOLD,
            "smooth_correction_threshold": THRESHOLDS.SMOOTH_CORRECTION_THRESHOLD,
            "validation_buffer": THRESHOLDS.VALIDATION_BUFFER,
            "positioning_tolerance": THRESHOLDS.POSITIONING_TOLERANCE,
            "smooth_correction_factor": THRESHOLDS.SMOOTH_CORRECTION_FACTOR,
            "interpolation_threshold": THRESHOLDS.INTERPOLATION_THRESHOLD,
        },
        "timeouts": {
            "fishing_timeout": TIMEOUTS.FISHING_TIMEOUT,
            "harvesting_timeout": TIMEOUTS.HARVESTING_TIMEOUT,
            "crafting_timeout": TIMEOUTS.CRAFTING_TIMEOUT,
            "trading_timeout": TIMEOUTS.TRADING_TIMEOUT,
            "positioning_timeout": TIMEOUTS.POSITIONING_TIMEOUT,
            "pathfinding_timeout": TIMEOUTS.PATHFINDING_TIMEOUT,
        },
    }


class PositionDiscrepancyTracker:
    """Track and report client-server position discrepancies for debugging"""

    def __init__(self):
        self.position_history: Dict[
            str, list
        ] = {}  # agent_id -> list of (client_pos, server_pos, timestamp)
        self.total_discrepancies = 0
        self.max_discrepancy_seen = 0.0

    def record_discrepancy(
        self,
        agent_id: str,
        client_pos: tuple,
        server_pos: tuple,
        timestamp: float = None,
    ):
        """Record a position discrepancy between client and server"""
        if not DEBUG.TRACK_POSITION_DISCREPANCIES:
            return

        import time

        if timestamp is None:
            timestamp = time.time()

        # Calculate discrepancy distance
        dx = client_pos[0] - server_pos[0]
        dy = client_pos[1] - server_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5

        # Track in history
        if agent_id not in self.position_history:
            self.position_history[agent_id] = []

        self.position_history[agent_id].append(
            (client_pos, server_pos, timestamp, distance)
        )

        # Keep only recent history
        if len(self.position_history[agent_id]) > DEBUG.POSITION_HISTORY_SIZE:
            self.position_history[agent_id].pop(0)

        # Update stats
        self.total_discrepancies += 1
        self.max_discrepancy_seen = max(self.max_discrepancy_seen, distance)

        # Log significant discrepancies
        if distance > DEBUG.MAX_ACCEPTABLE_DISCREPANCY:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"Large position discrepancy for {agent_id[:8]}: "
                f"client=({client_pos[0]:.2f}, {client_pos[1]:.2f}) "
                f"server=({server_pos[0]:.2f}, {server_pos[1]:.2f}) "
                f"distance={distance:.2f}"
            )

    def get_stats(self, agent_id: str = None) -> Dict[str, Any]:
        """Get position discrepancy statistics"""
        if agent_id and agent_id in self.position_history:
            history = self.position_history[agent_id]
            distances = [entry[3] for entry in history]

            return {
                "agent_id": agent_id,
                "total_records": len(history),
                "avg_discrepancy": sum(distances) / len(distances)
                if distances
                else 0.0,
                "max_discrepancy": max(distances) if distances else 0.0,
                "recent_discrepancies": distances[-10:]
                if len(distances) >= 10
                else distances,
            }
        else:
            return {
                "total_discrepancies": self.total_discrepancies,
                "max_discrepancy_seen": self.max_discrepancy_seen,
                "tracked_agents": len(self.position_history),
                "agents_with_large_discrepancies": sum(
                    1
                    for history in self.position_history.values()
                    if any(
                        entry[3] > DEBUG.MAX_ACCEPTABLE_DISCREPANCY for entry in history
                    )
                ),
            }


# Global discrepancy tracker instance
position_tracker = PositionDiscrepancyTracker()
