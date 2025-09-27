"""
Target Management System for Behavior Trees

This system provides unified target selection, tracking, and persistence
to prevent the jittery target-switching behavior that causes agents to
act inconsistently in combat.
"""

import logging
import math
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TargetSelectionStrategy(Enum):
    """Strategies for selecting targets from available options"""

    NEAREST = "nearest"
    WEAKEST = "weakest"
    MOST_THREATENING = "most_threatening"
    LEAST_HEALTH = "least_health"


class TargetInfo:
    """Information about a tracked target"""

    def __init__(self, entity: Dict[str, Any], selection_time: float = None):
        self.entity_id = entity.get("id")
        self.entity_type = entity.get("agent_type", entity.get("type", "unknown"))
        self.last_seen_time = selection_time or time.time()
        self.selection_time = selection_time or time.time()
        self.last_position = (entity.get("x", 0), entity.get("y", 0))
        self.last_health = entity.get("health", 100)
        self.engagement_count = 1
        self.priority_score = 0.0

        # Update with current entity data
        self.update(entity)

    def update(self, entity: Dict[str, Any]):
        """Update target info with fresh entity data"""
        self.last_seen_time = time.time()
        self.last_position = (entity.get("x", 0), entity.get("y", 0))
        self.last_health = entity.get("health", self.last_health)

    def get_age(self) -> float:
        """Get how long this target has been selected"""
        return time.time() - self.selection_time

    def get_time_since_seen(self) -> float:
        """Get how long since target was last seen"""
        return time.time() - self.last_seen_time

    def is_stale(self, max_age: float = 10.0) -> bool:
        """Check if target info is too old to be reliable"""
        return self.get_time_since_seen() > max_age


class TargetManager:
    """
    Unified target management system for agents.

    Provides consistent target selection, locking, and tracking to prevent
    the jittery behavior caused by constant target switching.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.current_target: Optional[TargetInfo] = None
        self.target_history: Dict[str, TargetInfo] = {}

        # Configuration
        self.lock_duration = 3.0  # How long to stick with a target
        self.max_target_age = 8.0  # When to forget old targets
        self.switch_threshold = 0.3  # How much better a new target must be
        self.max_history_size = 10

        # Target selection strategy
        self.selection_strategy = TargetSelectionStrategy.NEAREST

        logger.debug(f"TargetManager initialized for agent {agent_id[:8]}")

    def update_target_selection(
        self,
        agent,
        visible_entities: List[Dict[str, Any]],
        target_types: List[str],
        max_range: float = float("inf"),
        force_reselect: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Update target selection with locking and persistence logic.

        Args:
            agent: The agent requesting target selection
            visible_entities: List of entities the agent can see
            target_types: List of entity types to consider as targets
            max_range: Maximum range for target selection
            force_reselect: Force reselection even if current target is valid

        Returns:
            The selected target entity, or None if no valid targets
        """
        current_time = time.time()

        # Clean up old targets from history
        self._cleanup_target_history()

        # Filter valid targets
        valid_targets = self._filter_valid_targets(
            agent, visible_entities, target_types, max_range
        )

        if not valid_targets:
            # No valid targets, clear current target
            if self.current_target:
                logger.debug(f"Agent {self.agent_id[:8]} lost all valid targets")
                self.current_target = None
            return None

        # Update current target if it's still visible
        if self.current_target:
            current_entity = self._find_entity_by_id(
                valid_targets, self.current_target.entity_id
            )
            if current_entity:
                self.current_target.update(current_entity)
            else:
                # Current target no longer visible
                logger.debug(
                    f"Agent {self.agent_id[:8]} lost sight of target {self.current_target.entity_id[:8]}"
                )
                self.current_target = None

        # Check if we should stick with current target (target locking)
        if (
            self.current_target
            and not force_reselect
            and self.current_target.get_age() < self.lock_duration
            and not self.current_target.is_stale()
        ):
            # Stick with current target
            current_entity = self._find_entity_by_id(
                valid_targets, self.current_target.entity_id
            )
            if current_entity:
                logger.debug(
                    f"Agent {self.agent_id[:8]} maintaining target lock on {self.current_target.entity_id[:8]} (age: {self.current_target.get_age():.1f}s)"
                )
                return current_entity

        # Select new target
        best_target = self._select_best_target(agent, valid_targets)
        if best_target:
            # Check if new target is significantly better than current (prevents micro-switching)
            if self.current_target and not force_reselect:
                current_entity = self._find_entity_by_id(
                    valid_targets, self.current_target.entity_id
                )
                if current_entity and not self._is_significantly_better(
                    agent, best_target, current_entity
                ):
                    # New target not significantly better, keep current
                    logger.debug(
                        f"Agent {self.agent_id[:8]} keeping current target {self.current_target.entity_id[:8]} (new target not significantly better)"
                    )
                    return current_entity

            # Switch to new target
            old_target_id = (
                self.current_target.entity_id[:8] if self.current_target else "None"
            )
            self._set_new_target(best_target)
            logger.info(
                f"Agent {self.agent_id[:8]} switched target: {old_target_id} -> {self.current_target.entity_id[:8]}"
            )
            return best_target

        return None

    def get_current_target(self) -> Optional[Dict[str, Any]]:
        """Get current target entity data, or None if no target"""
        if not self.current_target or self.current_target.is_stale():
            return None
        return {
            "id": self.current_target.entity_id,
            "agent_type": self.current_target.entity_type,
            "x": self.current_target.last_position[0],
            "y": self.current_target.last_position[1],
            "health": self.current_target.last_health,
        }

    def force_target_reselection(self):
        """Force the next target selection to ignore locking"""
        if self.current_target:
            logger.debug(f"Agent {self.agent_id[:8]} forced target reselection")
            # Move current target to history but don't clear it immediately
            # This allows for immediate reselection while preserving history
            self.current_target.selection_time = 0  # Make it appear very old

    def clear_target(self):
        """Clear the current target"""
        if self.current_target:
            logger.debug(
                f"Agent {self.agent_id[:8]} cleared target {self.current_target.entity_id[:8]}"
            )
            self.current_target = None

    def get_target_age(self) -> float:
        """Get age of current target selection"""
        return self.current_target.get_age() if self.current_target else 0.0

    def is_target_locked(self) -> bool:
        """Check if we're currently in target lock period"""
        return (
            self.current_target
            and self.current_target.get_age() < self.lock_duration
            and not self.current_target.is_stale()
        )

    def _filter_valid_targets(
        self,
        agent,
        entities: List[Dict[str, Any]],
        target_types: List[str],
        max_range: float,
    ) -> List[Dict[str, Any]]:
        """Filter entities to valid targets"""
        valid_targets = []

        for entity in entities:
            # Check entity type
            entity_type = entity.get("agent_type", entity.get("type"))
            if entity_type not in target_types:
                continue

            # Skip self
            if entity.get("id") == agent.id:
                continue

            # Check if alive (default to True for compatibility)
            if not entity.get("is_alive", True):
                continue

            # Check range
            if max_range < float("inf"):
                dx = entity.get("x", 0) - agent.x
                dy = entity.get("y", 0) - agent.y
                distance = math.sqrt(dx * dx + dy * dy)
                if distance > max_range:
                    continue

            valid_targets.append(entity)

        return valid_targets

    def _select_best_target(
        self, agent, targets: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select the best target based on current strategy"""
        if not targets:
            return None

        if self.selection_strategy == TargetSelectionStrategy.NEAREST:
            return self._select_nearest_target(agent, targets)
        elif self.selection_strategy == TargetSelectionStrategy.WEAKEST:
            return self._select_weakest_target(targets)
        elif self.selection_strategy == TargetSelectionStrategy.LEAST_HEALTH:
            return self._select_lowest_health_target(targets)
        else:
            # Default to nearest
            return self._select_nearest_target(agent, targets)

    def _select_nearest_target(
        self, agent, targets: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select the nearest target"""
        nearest = None
        nearest_distance = float("inf")

        for target in targets:
            dx = target.get("x", 0) - agent.x
            dy = target.get("y", 0) - agent.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < nearest_distance:
                nearest_distance = distance
                nearest = target

        return nearest

    def _select_weakest_target(
        self, targets: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select target with lowest health percentage"""
        weakest = None
        lowest_health_pct = 1.0

        for target in targets:
            health = target.get("health", 100)
            max_health = target.get("max_health", 100)
            health_pct = health / max_health if max_health > 0 else 0

            if health_pct < lowest_health_pct:
                lowest_health_pct = health_pct
                weakest = target

        return weakest

    def _select_lowest_health_target(
        self, targets: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select target with lowest absolute health"""
        lowest_health_target = None
        lowest_health = float("inf")

        for target in targets:
            health = target.get("health", 100)
            if health < lowest_health:
                lowest_health = health
                lowest_health_target = target

        return lowest_health_target

    def _is_significantly_better(
        self, agent, new_target: Dict[str, Any], current_target: Dict[str, Any]
    ) -> bool:
        """Check if new target is significantly better than current target"""
        # Calculate distances
        new_dx = new_target.get("x", 0) - agent.x
        new_dy = new_target.get("y", 0) - agent.y
        new_distance = math.sqrt(new_dx * new_dx + new_dy * new_dy)

        current_dx = current_target.get("x", 0) - agent.x
        current_dy = current_target.get("y", 0) - agent.y
        current_distance = math.sqrt(current_dx * current_dx + current_dy * current_dy)

        # New target must be significantly closer
        distance_improvement = (current_distance - new_distance) / current_distance
        return distance_improvement > self.switch_threshold

    def _set_new_target(self, target_entity: Dict[str, Any]):
        """Set a new target and update history"""
        # Store old target in history if it exists
        if self.current_target:
            self.target_history[self.current_target.entity_id] = self.current_target

        # Create new target info
        self.current_target = TargetInfo(target_entity)

        # Clean up history if it's getting too large
        if len(self.target_history) > self.max_history_size:
            oldest_key = min(
                self.target_history.keys(),
                key=lambda k: self.target_history[k].selection_time,
            )
            del self.target_history[oldest_key]

    def _find_entity_by_id(
        self, entities: List[Dict[str, Any]], entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Find entity by ID in the entities list"""
        for entity in entities:
            if entity.get("id") == entity_id:
                return entity
        return None

    def _cleanup_target_history(self):
        """Remove old targets from history"""
        current_time = time.time()
        to_remove = []

        for entity_id, target_info in self.target_history.items():
            if current_time - target_info.selection_time > self.max_target_age:
                to_remove.append(entity_id)

        for entity_id in to_remove:
            del self.target_history[entity_id]

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about current target state"""
        info = {
            "has_target": self.current_target is not None,
            "target_locked": self.is_target_locked(),
            "history_count": len(self.target_history),
            "selection_strategy": self.selection_strategy.value,
        }

        if self.current_target:
            info.update(
                {
                    "target_id": self.current_target.entity_id[:8],
                    "target_age": self.current_target.get_age(),
                    "time_since_seen": self.current_target.get_time_since_seen(),
                    "target_position": self.current_target.last_position,
                }
            )

        return info
