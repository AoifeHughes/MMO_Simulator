"""
Position Statistics and Monitoring

This module provides runtime statistics for client-server position discrepancies
and action distance validation to help debug position jumping issues.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from shared.action_constants import DEBUG, THRESHOLDS

logger = logging.getLogger(__name__)


@dataclass
class PositionDiscrepancy:
    """A single recorded position discrepancy"""

    agent_id: str
    client_pos: Tuple[float, float]
    server_pos: Tuple[float, float]
    distance: float
    timestamp: float
    action_context: Optional[str] = None  # What action was being attempted


@dataclass
class ActionDistanceStats:
    """Statistics for action distance validation"""

    action_name: str
    total_attempts: int = 0
    successful_validations: int = 0
    failed_validations: int = 0
    avg_distance_when_successful: float = 0.0
    avg_distance_when_failed: float = 0.0
    max_distance_attempted: float = 0.0
    min_distance_attempted: float = float("inf")


class PositionStatsCollector:
    """Collects and reports position statistics for debugging"""

    def __init__(self):
        self.discrepancies: List[PositionDiscrepancy] = []
        self.action_stats: Dict[str, ActionDistanceStats] = defaultdict(
            ActionDistanceStats
        )
        self.start_time = time.time()

        # Running statistics
        self.total_discrepancies_recorded = 0
        self.large_discrepancies_count = 0
        self.max_discrepancy_seen = 0.0

        logger.info("Position statistics collector initialized")

    def record_position_discrepancy(
        self,
        agent_id: str,
        client_pos: Tuple[float, float],
        server_pos: Tuple[float, float],
        action_context: Optional[str] = None,
    ):
        """Record a position discrepancy between client and server"""
        if not DEBUG.TRACK_POSITION_DISCREPANCIES:
            return

        # Calculate distance
        dx = client_pos[0] - server_pos[0]
        dy = client_pos[1] - server_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5

        # Create discrepancy record
        discrepancy = PositionDiscrepancy(
            agent_id=agent_id,
            client_pos=client_pos,
            server_pos=server_pos,
            distance=distance,
            timestamp=time.time(),
            action_context=action_context,
        )

        # Store in history (with size limit)
        self.discrepancies.append(discrepancy)
        if len(self.discrepancies) > DEBUG.POSITION_HISTORY_SIZE:
            self.discrepancies.pop(0)

        # Update statistics
        self.total_discrepancies_recorded += 1
        if distance > DEBUG.MAX_ACCEPTABLE_DISCREPANCY:
            self.large_discrepancies_count += 1

        self.max_discrepancy_seen = max(self.max_discrepancy_seen, distance)

        # Log significant discrepancies
        if distance > DEBUG.MAX_ACCEPTABLE_DISCREPANCY:
            logger.warning(
                f"Large position discrepancy for {agent_id[:8]} during {action_context or 'unknown'}: "
                f"client=({client_pos[0]:.2f}, {client_pos[1]:.2f}) "
                f"server=({server_pos[0]:.2f}, {server_pos[1]:.2f}) "
                f"distance={distance:.2f}"
            )

    def record_action_distance_attempt(
        self,
        action_name: str,
        agent_pos: Tuple[float, float],
        target_pos: Tuple[float, float],
        max_allowed_distance: float,
        was_successful: bool,
    ):
        """Record an action distance validation attempt"""
        # Calculate actual distance
        dx = target_pos[0] - agent_pos[0]
        dy = target_pos[1] - agent_pos[1]
        actual_distance = (dx * dx + dy * dy) ** 0.5

        # Get or create stats for this action
        if action_name not in self.action_stats:
            self.action_stats[action_name] = ActionDistanceStats(
                action_name=action_name
            )

        stats = self.action_stats[action_name]

        # Update statistics
        stats.total_attempts += 1
        stats.max_distance_attempted = max(
            stats.max_distance_attempted, actual_distance
        )
        stats.min_distance_attempted = min(
            stats.min_distance_attempted, actual_distance
        )

        if was_successful:
            stats.successful_validations += 1
            # Update rolling average for successful attempts
            n = stats.successful_validations
            stats.avg_distance_when_successful = (
                (n - 1) * stats.avg_distance_when_successful + actual_distance
            ) / n
        else:
            stats.failed_validations += 1
            # Update rolling average for failed attempts
            n = stats.failed_validations
            if n == 1:
                stats.avg_distance_when_failed = actual_distance
            else:
                stats.avg_distance_when_failed = (
                    (n - 1) * stats.avg_distance_when_failed + actual_distance
                ) / n

        # Log detailed action attempts if enabled
        if DEBUG.LOG_DISTANCE_VALIDATION:
            status = "SUCCESS" if was_successful else "FAILED"
            logger.debug(
                f"Action {action_name} {status}: distance={actual_distance:.2f}, "
                f"max_allowed={max_allowed_distance:.2f}"
            )

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all tracked data"""
        uptime = time.time() - self.start_time

        # Calculate discrepancy statistics
        recent_discrepancies = [
            d for d in self.discrepancies if (time.time() - d.timestamp) < 300
        ]  # Last 5 minutes
        avg_discrepancy = (
            sum(d.distance for d in recent_discrepancies) / len(recent_discrepancies)
            if recent_discrepancies
            else 0.0
        )

        # Action statistics summary
        action_summary = {}
        for action_name, stats in self.action_stats.items():
            success_rate = (
                (stats.successful_validations / stats.total_attempts * 100)
                if stats.total_attempts > 0
                else 0
            )
            action_summary[action_name] = {
                "total_attempts": stats.total_attempts,
                "success_rate": f"{success_rate:.1f}%",
                "avg_successful_distance": f"{stats.avg_distance_when_successful:.2f}",
                "avg_failed_distance": f"{stats.avg_distance_when_failed:.2f}",
                "distance_range": f"{stats.min_distance_attempted:.2f} - {stats.max_distance_attempted:.2f}",
            }

        return {
            "uptime_seconds": uptime,
            "position_discrepancies": {
                "total_recorded": self.total_discrepancies_recorded,
                "large_discrepancies": self.large_discrepancies_count,
                "max_discrepancy_seen": f"{self.max_discrepancy_seen:.2f}",
                "recent_avg_discrepancy": f"{avg_discrepancy:.2f}",
                "recent_count": len(recent_discrepancies),
            },
            "action_distance_stats": action_summary,
            "config": {
                "max_acceptable_discrepancy": DEBUG.MAX_ACCEPTABLE_DISCREPANCY,
                "position_history_size": DEBUG.POSITION_HISTORY_SIZE,
                "tracking_enabled": DEBUG.TRACK_POSITION_DISCREPANCIES,
            },
        }

    def get_agent_specific_stats(self, agent_id: str) -> Dict[str, Any]:
        """Get statistics specific to one agent"""
        agent_discrepancies = [d for d in self.discrepancies if d.agent_id == agent_id]

        if not agent_discrepancies:
            return {"agent_id": agent_id, "no_data": True}

        # Recent discrepancies (last 5 minutes)
        recent = [d for d in agent_discrepancies if (time.time() - d.timestamp) < 300]

        distances = [d.distance for d in agent_discrepancies]
        recent_distances = [d.distance for d in recent]

        return {
            "agent_id": agent_id,
            "total_discrepancies": len(agent_discrepancies),
            "recent_discrepancies": len(recent),
            "avg_discrepancy_all_time": sum(distances) / len(distances),
            "avg_discrepancy_recent": sum(recent_distances) / len(recent_distances)
            if recent_distances
            else 0,
            "max_discrepancy": max(distances),
            "action_contexts": list(
                set(d.action_context for d in agent_discrepancies if d.action_context)
            ),
            "last_discrepancy_time": max(d.timestamp for d in agent_discrepancies),
            "large_discrepancy_count": sum(
                1
                for d in agent_discrepancies
                if d.distance > DEBUG.MAX_ACCEPTABLE_DISCREPANCY
            ),
        }

    def print_summary_report(self):
        """Print a formatted summary report to the console"""
        stats = self.get_summary_stats()

        print("\n" + "=" * 60)
        print("POSITION STATISTICS SUMMARY")
        print("=" * 60)
        print(f"Uptime: {stats['uptime_seconds']:.1f} seconds")
        print()

        pos_stats = stats["position_discrepancies"]
        print("POSITION DISCREPANCIES:")
        print(f"  Total Recorded: {pos_stats['total_recorded']}")
        print(
            f"  Large Discrepancies (>{DEBUG.MAX_ACCEPTABLE_DISCREPANCY}): {pos_stats['large_discrepancies']}"
        )
        print(f"  Maximum Discrepancy: {pos_stats['max_discrepancy_seen']} units")
        print(
            f"  Recent Average: {pos_stats['recent_avg_discrepancy']} units ({pos_stats['recent_count']} samples)"
        )
        print()

        print("ACTION DISTANCE VALIDATION:")
        for action, stats in stats["action_distance_stats"].items():
            print(f"  {action}:")
            print(f"    Attempts: {stats['total_attempts']}")
            print(f"    Success Rate: {stats['success_rate']}")
            print(f"    Avg Distance (success): {stats['avg_successful_distance']}")
            print(f"    Avg Distance (failed): {stats['avg_failed_distance']}")
            print(f"    Distance Range: {stats['distance_range']}")

        print("=" * 60)

    def reset_stats(self):
        """Reset all statistics (useful for testing)"""
        self.discrepancies.clear()
        self.action_stats.clear()
        self.total_discrepancies_recorded = 0
        self.large_discrepancies_count = 0
        self.max_discrepancy_seen = 0.0
        self.start_time = time.time()
        logger.info("Position statistics reset")


# Global statistics collector instance
global_stats = PositionStatsCollector()


# Convenience functions for easy access
def record_position_discrepancy(
    agent_id: str,
    client_pos: Tuple[float, float],
    server_pos: Tuple[float, float],
    action_context: Optional[str] = None,
):
    """Record a position discrepancy"""
    global_stats.record_position_discrepancy(
        agent_id, client_pos, server_pos, action_context
    )


def record_action_distance_attempt(
    action_name: str,
    agent_pos: Tuple[float, float],
    target_pos: Tuple[float, float],
    max_allowed_distance: float,
    was_successful: bool,
):
    """Record an action distance validation attempt"""
    global_stats.record_action_distance_attempt(
        action_name, agent_pos, target_pos, max_allowed_distance, was_successful
    )


def get_summary_stats() -> Dict[str, Any]:
    """Get current statistics summary"""
    return global_stats.get_summary_stats()


def print_stats_report():
    """Print statistics report to console"""
    global_stats.print_summary_report()


def get_agent_stats(agent_id: str) -> Dict[str, Any]:
    """Get statistics for a specific agent"""
    return global_stats.get_agent_specific_stats(agent_id)
