"""
Movement validation and anti-cheat systems
"""

import time
from typing import Dict, List, Tuple, Optional
import logging

from shared.math_utils import Vector2
from shared.constants import DEFAULT_MOVE_SPEED, MAX_MOVE_SPEED, RUN_SPEED_MULTIPLIER
from .bounds_checker import BoundsChecker

logger = logging.getLogger(__name__)


class MovementValidator:
    """Validates movement actions and prevents cheating"""

    def __init__(self, bounds_checker: BoundsChecker, server_config=None):
        self.bounds_checker = bounds_checker
        self.movement_history: Dict[str, List[Tuple[Vector2, float]]] = {}
        self.last_movement_time: Dict[str, float] = {}

        # Load movement rules from config
        self.movement_rules = {
            'max_speed': MAX_MOVE_SPEED,
            'default_speed': DEFAULT_MOVE_SPEED,
            'run_multiplier': RUN_SPEED_MULTIPLIER,
            'bounds_checking': True,
            'collision_checking': True
        }

        if server_config:
            self.movement_rules.update(server_config.world_rules.get('movement', {}))

        # Anti-cheat settings
        self.anti_cheat = {
            'speed_checking': True,
            'teleport_detection': True,
            'max_actions_per_second': 10
        }

        if server_config:
            self.anti_cheat.update(server_config.validation.get('anti_cheat', {}))

        # Action rate limiting
        self.action_counts: Dict[str, List[float]] = {}

    def validate_movement(self, entity_id: str, current_pos: Vector2, target_pos: Vector2,
                         speed_modifier: float = 1.0, delta_time: float = 1.0) -> Tuple[bool, Vector2, List[str]]:
        """Validate a movement request"""
        current_time = time.time()
        issues = []

        # Rate limiting check
        if not self._check_rate_limit(entity_id, current_time):
            return False, current_pos, ["Movement rate limit exceeded"]

        # Bounds checking
        if self.movement_rules['bounds_checking']:
            bounds_valid, corrected_target, bounds_issues = self.bounds_checker.validate_movement_path(
                current_pos, target_pos, "agent"
            )
            target_pos = corrected_target
            issues.extend(bounds_issues)

            if not bounds_valid:
                return False, current_pos, issues

        # Speed validation
        if self.anti_cheat['speed_checking']:
            speed_valid, speed_corrected_target, speed_issues = self._validate_speed(
                entity_id, current_pos, target_pos, speed_modifier, delta_time, current_time
            )
            target_pos = speed_corrected_target
            issues.extend(speed_issues)

            if not speed_valid:
                return False, current_pos, issues

        # Teleport detection
        if self.anti_cheat['teleport_detection']:
            teleport_valid, teleport_issues = self._check_teleportation(
                entity_id, current_pos, target_pos, current_time
            )
            issues.extend(teleport_issues)

            if not teleport_valid:
                return False, current_pos, issues

        # Update movement history
        self._update_movement_history(entity_id, target_pos, current_time)

        return True, target_pos, issues

    def _check_rate_limit(self, entity_id: str, current_time: float) -> bool:
        """Check if entity is exceeding movement action rate limit"""
        if entity_id not in self.action_counts:
            self.action_counts[entity_id] = []

        actions = self.action_counts[entity_id]

        # Remove actions older than 1 second
        actions[:] = [t for t in actions if current_time - t < 1.0]

        # Check if under limit
        if len(actions) >= self.anti_cheat['max_actions_per_second']:
            logger.warning(f"Entity {entity_id} exceeded movement rate limit")
            return False

        # Add current action
        actions.append(current_time)
        return True

    def _validate_speed(self, entity_id: str, current_pos: Vector2, target_pos: Vector2,
                       speed_modifier: float, delta_time: float, current_time: float) -> Tuple[bool, Vector2, List[str]]:
        """Validate movement speed"""
        issues = []
        distance = current_pos.distance_to(target_pos)

        # Calculate maximum allowed distance for this time period
        base_speed = self.movement_rules['default_speed']
        max_speed = min(self.movement_rules['max_speed'], base_speed * speed_modifier)

        # Check terrain movement modifier
        terrain_modifier = self.bounds_checker.check_terrain_movement_modifier(target_pos)
        effective_speed = max_speed * terrain_modifier

        max_distance = effective_speed * delta_time

        if distance > max_distance * 1.1:  # 10% tolerance for network lag
            # Cap the movement to maximum allowed distance
            direction = (target_pos - current_pos).normalize()
            corrected_target = current_pos + direction * max_distance
            issues.append(f"Movement speed limited (distance: {distance:.1f}, max: {max_distance:.1f})")

            logger.warning(f"Entity {entity_id} exceeded speed limit: {distance:.1f} > {max_distance:.1f}")
            return True, corrected_target, issues

        return True, target_pos, issues

    def _check_teleportation(self, entity_id: str, current_pos: Vector2, target_pos: Vector2,
                            current_time: float) -> Tuple[bool, List[str]]:
        """Check for suspicious teleportation"""
        issues = []

        # Get last known position and time
        if entity_id in self.movement_history and self.movement_history[entity_id]:
            last_pos, last_time = self.movement_history[entity_id][-1]
            time_diff = current_time - last_time

            if time_diff > 0.1:  # Only check if enough time has passed
                distance = last_pos.distance_to(target_pos)
                max_possible_distance = self.movement_rules['max_speed'] * time_diff * 2  # Extra tolerance

                if distance > max_possible_distance:
                    logger.warning(f"Possible teleportation detected for {entity_id}: "
                                 f"{distance:.1f} units in {time_diff:.3f}s")
                    issues.append("Suspicious movement detected")
                    return False, issues

        return True, issues

    def _update_movement_history(self, entity_id: str, position: Vector2, timestamp: float):
        """Update movement history for an entity"""
        if entity_id not in self.movement_history:
            self.movement_history[entity_id] = []

        history = self.movement_history[entity_id]
        history.append((position, timestamp))

        # Keep only recent history (last 10 positions)
        if len(history) > 10:
            history.pop(0)

        self.last_movement_time[entity_id] = timestamp

    def get_movement_stats(self, entity_id: str) -> Dict[str, any]:
        """Get movement statistics for an entity"""
        if entity_id not in self.movement_history:
            return {}

        history = self.movement_history[entity_id]
        if len(history) < 2:
            return {}

        # Calculate average speed over recent movements
        total_distance = 0
        total_time = 0

        for i in range(1, len(history)):
            prev_pos, prev_time = history[i-1]
            curr_pos, curr_time = history[i]

            distance = prev_pos.distance_to(curr_pos)
            time_diff = curr_time - prev_time

            total_distance += distance
            total_time += time_diff

        avg_speed = total_distance / total_time if total_time > 0 else 0

        return {
            'average_speed': avg_speed,
            'total_distance': total_distance,
            'movement_count': len(history),
            'last_movement': self.last_movement_time.get(entity_id, 0)
        }

    def cleanup_old_data(self, max_age: float = 300.0):
        """Clean up old movement data"""
        current_time = time.time()
        entities_to_remove = []

        for entity_id, last_time in self.last_movement_time.items():
            if current_time - last_time > max_age:
                entities_to_remove.append(entity_id)

        for entity_id in entities_to_remove:
            self.movement_history.pop(entity_id, None)
            self.last_movement_time.pop(entity_id, None)
            self.action_counts.pop(entity_id, None)

    def reset_entity_data(self, entity_id: str):
        """Reset all data for a specific entity"""
        self.movement_history.pop(entity_id, None)
        self.last_movement_time.pop(entity_id, None)
        self.action_counts.pop(entity_id, None)