"""
Movement Validation System

This module provides movement validation to reduce server-client conflicts
by pre-validating movements before sending them to the server.

Key features:
- Validates movement against known terrain constraints
- Checks distance limits and movement bounds
- Prevents invalid movements that would trigger server corrections
- Provides feedback for behavior tree decision making
"""

import logging
import math
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class MovementValidator:
    """Validates movements before sending to server to reduce conflicts"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

        # Validation parameters
        self.max_single_movement = 10.0  # Max distance in single movement
        self.max_speed = 5.0  # Max speed units/second
        self.min_movement_distance = 0.1  # Ignore tiny movements

        # Terrain awareness (will be populated when terrain data is available)
        self.terrain_cache = {}
        self.world_bounds = None

        # Statistics
        self.stats = {
            "movements_validated": 0,
            "movements_rejected": 0,
            "terrain_violations": 0,
            "distance_violations": 0,
            "bound_violations": 0
        }

    def set_world_bounds(self, width: int, height: int):
        """Set world boundaries for validation"""
        self.world_bounds = (width, height)
        logger.debug(f"Movement validator for {self.agent_id[:8]} set bounds: {width}x{height}")

    def update_terrain_cache(self, terrain_data: dict):
        """Update terrain cache for better validation"""
        if terrain_data:
            self.terrain_cache.update(terrain_data)
            logger.debug(f"Movement validator updated terrain cache with {len(terrain_data)} tiles")

    def validate_movement(self, current_x: float, current_y: float,
                         target_x: float, target_y: float,
                         max_distance: Optional[float] = None) -> Tuple[bool, str]:
        """
        Validate a movement from current position to target position

        Args:
            current_x, current_y: Current agent position
            target_x, target_y: Intended target position
            max_distance: Maximum allowed movement distance (optional)

        Returns:
            (is_valid, reason): Whether movement is valid and reason if not
        """
        self.stats["movements_validated"] += 1

        # Calculate movement distance
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.sqrt(dx * dx + dy * dy)

        # Check minimum movement threshold
        if distance < self.min_movement_distance:
            return True, "Movement too small to matter"

        # Check maximum movement distance
        max_allowed = max_distance if max_distance is not None else self.max_single_movement
        if distance > max_allowed:
            self.stats["movements_rejected"] += 1
            self.stats["distance_violations"] += 1
            return False, f"Movement distance {distance:.2f} exceeds maximum {max_allowed:.2f}"

        # Check world bounds
        if self.world_bounds:
            width, height = self.world_bounds
            if not (0 <= target_x < width and 0 <= target_y < height):
                self.stats["movements_rejected"] += 1
                self.stats["bound_violations"] += 1
                return False, f"Target ({target_x:.2f}, {target_y:.2f}) outside world bounds {width}x{height}"

        # Check terrain walkability if we have terrain data
        if self.terrain_cache:
            if not self._is_path_walkable(current_x, current_y, target_x, target_y):
                self.stats["movements_rejected"] += 1
                self.stats["terrain_violations"] += 1
                return False, f"Path from ({current_x:.2f}, {current_y:.2f}) to ({target_x:.2f}, {target_y:.2f}) blocked by terrain"

        return True, "Movement valid"

    def _is_path_walkable(self, start_x: float, start_y: float,
                         end_x: float, end_y: float) -> bool:
        """Check if path between two points is walkable based on terrain cache"""
        # Simple line sampling - check key points along the path
        num_samples = max(3, int(math.sqrt((end_x - start_x) ** 2 + (end_y - start_y) ** 2)))

        for i in range(num_samples + 1):
            t = i / num_samples if num_samples > 0 else 0
            check_x = start_x + (end_x - start_x) * t
            check_y = start_y + (end_y - start_y) * t

            # Check if this point is walkable
            tile_x, tile_y = int(check_x), int(check_y)
            if (tile_x, tile_y) in self.terrain_cache:
                tile_type = self.terrain_cache[(tile_x, tile_y)]
                # Check if tile is walkable (this depends on your terrain system)
                if hasattr(tile_type, 'walkable'):
                    if not tile_type.walkable:
                        return False
                elif hasattr(tile_type, 'name'):
                    # Common non-walkable tile types
                    if tile_type.name in ['WALL', 'WATER', 'VOID', 'OBSTACLE']:
                        return False

        return True

    def validate_speed(self, distance: float, time_delta: float) -> Tuple[bool, str]:
        """Validate movement speed"""
        if time_delta <= 0:
            return True, "Instantaneous movement"

        speed = distance / time_delta
        if speed > self.max_speed:
            self.stats["movements_rejected"] += 1
            return False, f"Speed {speed:.2f} exceeds maximum {self.max_speed:.2f}"

        return True, "Speed valid"

    def suggest_corrected_movement(self, current_x: float, current_y: float,
                                  target_x: float, target_y: float) -> Tuple[float, float]:
        """
        Suggest a corrected movement when the original is invalid

        Returns:
            (corrected_x, corrected_y): A valid movement target
        """
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.sqrt(dx * dx + dy * dy)

        # If distance is the issue, scale down
        if distance > self.max_single_movement:
            scale = self.max_single_movement / distance
            corrected_x = current_x + dx * scale
            corrected_y = current_y + dy * scale
        else:
            corrected_x, corrected_y = target_x, target_y

        # Clamp to world bounds
        if self.world_bounds:
            width, height = self.world_bounds
            corrected_x = max(0, min(width - 1, corrected_x))
            corrected_y = max(0, min(height - 1, corrected_y))

        return corrected_x, corrected_y

    def validate_behavior_tree_movement(self, agent, target_x: float, target_y: float) -> Tuple[bool, str]:
        """
        Special validation for behavior tree movements

        Args:
            agent: The agent object (for current position)
            target_x, target_y: Target position

        Returns:
            (is_valid, reason): Validation result
        """
        current_x, current_y = agent.x, agent.y

        # Check if agent has sufficient terrain coverage for safe movement
        if hasattr(agent, 'agent_map') and agent.agent_map:
            if hasattr(agent, '_has_sufficient_terrain_coverage'):
                if not agent._has_sufficient_terrain_coverage():
                    # More conservative movement when terrain data is sparse
                    max_distance = self.max_single_movement * 0.3  # Very conservative
                    logger.debug(f"Movement validator using conservative limits for {self.agent_id[:8]} due to insufficient terrain data")
                else:
                    max_distance = self.max_single_movement
            else:
                max_distance = self.max_single_movement
        else:
            # No terrain data - be very conservative
            max_distance = self.max_single_movement * 0.2
            logger.debug(f"Movement validator using very conservative limits for {self.agent_id[:8]} due to no terrain data")

        # Use position reconciler data if available for more accurate validation
        if hasattr(agent, 'position_reconciler') and agent.position_reconciler:
            # Check against server position for better accuracy
            server_error = agent.position_reconciler.get_position_error()
            if server_error > 2.0:  # Large position error
                return False, f"Agent position too far from server (error: {server_error:.2f})"

            # Use more conservative limits when position is uncertain
            max_distance = max_distance * 0.7  # Further reduce limit when position uncertain

        return self.validate_movement(current_x, current_y, target_x, target_y, max_distance)

    def get_stats(self) -> dict:
        """Get validation statistics"""
        total_validated = self.stats["movements_validated"]
        rejection_rate = (self.stats["movements_rejected"] / total_validated * 100) if total_validated > 0 else 0

        return {
            **self.stats,
            "rejection_rate_percent": round(rejection_rate, 1),
            "terrain_cache_size": len(self.terrain_cache),
            "world_bounds": self.world_bounds
        }

    def reset_stats(self):
        """Reset validation statistics"""
        for key in self.stats:
            self.stats[key] = 0