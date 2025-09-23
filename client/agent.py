import logging
import math
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from client.agent_map import AgentMap
from shared.collision import CollisionDetector
from shared.constants import (
    DEFAULT_AGENT_SPEED,
    DEFAULT_VISION_ANGLE,
    DEFAULT_VISION_RANGE,
)
from shared.math_utils import normalize_angle
from shared.pathfinding import Pathfinder
from world.tiles import TileType

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, agent_id: str, x: float, y: float, agent_type: str):
        self.id = agent_id
        self.x = x
        self.y = y
        self.rotation = 0.0
        self.agent_type = agent_type

        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.speed = DEFAULT_AGENT_SPEED

        self.vision_range = DEFAULT_VISION_RANGE
        self.vision_angle = DEFAULT_VISION_ANGLE

        self.health = 100.0
        self.max_health = 100.0
        self.is_alive = True

        self.visible_entities: List[Dict[str, Any]] = []
        self.last_update = time.time()

        # Intention change cooldown system
        self.current_intention: Optional[str] = None
        self.last_intention_change: float = (
            time.time() - 3.0
        )  # Allow immediate first intention change
        self.intention_cooldown: float = 3.0  # 3 seconds between intention changes
        self.base_intention_cooldown: float = 3.0  # Original cooldown for recovery

        # Collision detection (will be set when world bounds are known)
        self.collision_detector: Optional[CollisionDetector] = None
        self.world_bounds: Optional[Tuple[int, int]] = None

        # Pathfinding and mapping
        self.agent_map: Optional[AgentMap] = None
        self.pathfinder = Pathfinder()
        self.current_path: Optional[List[Tuple[float, float]]] = None
        self.current_waypoint: Optional[Tuple[float, float]] = None
        self.waypoint_threshold = 0.5

        # Behavior tree system
        self.behavior_tree = None
        self.use_behavior_tree = False
        self.last_position = (x, y)
        self.last_position_time = time.time()

        # Action tracking for conditions
        self.current_target: Optional[Tuple[float, float]] = None

    @abstractmethod
    def update(self, delta_time: float):
        pass

    @abstractmethod
    def perceive(self, visible_entities: List[Dict[str, Any]]):
        pass

    @abstractmethod
    def decide(self) -> Optional[Dict[str, Any]]:
        pass

    def move(self, delta_time: float):
        # Calculate intended new position
        new_x = self.x + self.velocity_x * delta_time
        new_y = self.y + self.velocity_y * delta_time

        # Apply collision detection if available
        if self.collision_detector:
            new_x, new_y = self.collision_detector.resolve_movement_collision(
                (self.x, self.y), (new_x, new_y)
            )

        self.x = new_x
        self.y = new_y

    def set_velocity(self, vx: float, vy: float):
        self.velocity_x = vx
        self.velocity_y = vy

    def set_position(self, x: float, y: float):
        # Apply boundary clamping if collision detector is available
        if self.collision_detector:
            x, y = self.collision_detector.clamp_to_bounds(x, y)
        self.x = x
        self.y = y

    def set_world_bounds(self, width: int, height: int):
        """Set the world bounds and initialize collision detector and agent map"""
        self.world_bounds = (width, height)
        self.collision_detector = CollisionDetector(width, height)
        self.agent_map = AgentMap(width, height)

    def can_change_intention(self) -> bool:
        """Check if enough time has passed to allow intention change"""
        current_time = time.time()
        return (current_time - self.last_intention_change) >= self.intention_cooldown

    def set_intention(self, new_intention: str, force: bool = False) -> bool:
        """Set a new intention with cooldown protection"""
        current_time = time.time()

        # Allow setting intention if it's the same as current (no change needed)
        if self.current_intention == new_intention:
            return True

        # Check cooldown unless forced
        if not force and not self.can_change_intention():
            # Still on cooldown, keep current intention
            remaining = self.intention_cooldown - (
                current_time - self.last_intention_change
            )
            logger.debug(
                f"Agent {self.id[:8]} intention change blocked - "
                f"{remaining:.1f}s remaining on cooldown"
            )
            return False

        # Allow intention change
        old_intention = self.current_intention
        self.current_intention = new_intention
        self.last_intention_change = current_time

        if old_intention != new_intention:
            logger.debug(
                f"Agent {self.id[:8]} intention changed: "
                f"{old_intention} → {new_intention}"
            )

        return True

    def get_intention(self) -> Optional[str]:
        """Get current intention"""
        return self.current_intention

    def force_intention(self, new_intention: str):
        """Force an intention change bypassing cooldown (for emergencies)"""
        self.set_intention(new_intention, force=True)

    def check_health_recovery(self):
        """Check if health has recovered and restore normal intention cooldown"""
        # If health is above 40% (healthy), restore normal intention cooldown
        # This provides hysteresis - low health at 20%, recovery at 40%
        if hasattr(self, "max_health") and self.health > (self.max_health * 0.4):
            if self.intention_cooldown > self.base_intention_cooldown:
                self.intention_cooldown = self.base_intention_cooldown

    def set_rotation(self, rotation: float):
        self.rotation = normalize_angle(rotation)

    def take_damage(self, damage: float):
        self.health = max(0, self.health - damage)

    def heal(self, amount: float):
        self.health = min(self.max_health, self.health + amount)

    def is_alive(self) -> bool:
        return self.health > 0

    def get_position(self) -> Tuple[float, float]:
        return self.x, self.y

    # Pathfinding methods
    def find_path_to(self, target_x: float, target_y: float) -> bool:
        """Find path to target position using agent's known map.
        Returns True if path found."""
        if not self.agent_map:
            return False

        path = self.pathfinder.find_path(
            self.agent_map, (self.x, self.y), (target_x, target_y)
        )

        if path:
            self.current_path = self.pathfinder.simplify_path(path, max_waypoints=8)
            self.current_waypoint = self.pathfinder.get_next_waypoint(
                self.current_path, (self.x, self.y), self.waypoint_threshold
            )
            return True

        return False

    def find_path_to_exploration_frontier(self) -> bool:
        """Find path to nearest exploration frontier. Returns True if path found."""
        if not self.agent_map:
            return False

        path = self.pathfinder.find_path_to_nearest_frontier(
            self.agent_map, (self.x, self.y)
        )

        if path:
            self.current_path = self.pathfinder.simplify_path(path, max_waypoints=8)
            self.current_waypoint = self.pathfinder.get_next_waypoint(
                self.current_path, (self.x, self.y), self.waypoint_threshold
            )
            return True

        return False

    def update_pathfinding(self, delta_time: float):
        """Update pathfinding state - call this in agent update loops"""
        if not self.current_path or not self.current_waypoint:
            return

        # Check if we've reached the current waypoint
        current_pos = (self.x, self.y)
        distance_to_waypoint = math.sqrt(
            (self.current_waypoint[0] - current_pos[0]) ** 2
            + (self.current_waypoint[1] - current_pos[1]) ** 2
        )

        if distance_to_waypoint <= self.waypoint_threshold:
            # Move to next waypoint
            self.current_waypoint = self.pathfinder.get_next_waypoint(
                self.current_path, current_pos, self.waypoint_threshold
            )

            if not self.current_waypoint:
                # Path complete
                self.current_path = None
                self.velocity_x = 0
                self.velocity_y = 0
                return

        # Set velocity toward current waypoint
        if self.current_waypoint:
            dx = self.current_waypoint[0] - self.x
            dy = self.current_waypoint[1] - self.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 0:
                self.velocity_x = (dx / distance) * self.speed
                self.velocity_y = (dy / distance) * self.speed
                self.rotation = math.degrees(math.atan2(dy, dx))

    def move_direct(self, target_x: float, target_y: float):
        """Direct movement without pathfinding (fallback behavior)"""
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 0:
            self.velocity_x = (dx / distance) * self.speed
            self.velocity_y = (dy / distance) * self.speed
            self.rotation = math.degrees(math.atan2(dy, dx))

    def stop_movement(self):
        """Stop all movement and clear current path"""
        self.velocity_x = 0
        self.velocity_y = 0
        self.current_path = None
        self.current_waypoint = None

    def discover_terrain_from_vision(
        self, terrain_data: Dict[Tuple[int, int], TileType]
    ):
        """Update agent map with terrain discovered through vision"""
        if not self.agent_map:
            return

        # Discover terrain within vision range
        self.agent_map.discover_area(self.x, self.y, self.vision_range, terrain_data)

    def get_state(self) -> Dict[str, Any]:
        state = {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "type": self.agent_type,
            "health": self.health,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
        }

        # Add pathfinding information if available
        if self.agent_map:
            state.update(
                {
                    "map_completion": self.agent_map.get_map_completion_percentage(),
                    "has_path": self.current_path is not None,
                    "current_waypoint": self.current_waypoint,
                }
            )

        return state

    def update_from_state(self, state: Dict[str, Any]):
        self.x = state.get("x", self.x)
        self.y = state.get("y", self.y)
        self.rotation = state.get("rotation", self.rotation)
        self.health = state.get("health", self.health)
        self.velocity_x = state.get("velocity_x", 0)
        self.velocity_y = state.get("velocity_y", 0)

    # Behavior Tree Support Methods
    def set_behavior_tree(self, behavior_tree):
        """Set the behavior tree for this agent and enable behavior tree mode"""
        self.behavior_tree = behavior_tree
        self.use_behavior_tree = True
        logger.debug(
            f"Agent {self.id[:8]} set to use behavior tree: {behavior_tree.name}"
        )

    def disable_behavior_tree(self):
        """Disable behavior tree mode and revert to legacy behavior"""
        self.use_behavior_tree = False
        if self.behavior_tree:
            self.behavior_tree.reset()
        logger.debug(f"Agent {self.id[:8]} disabled behavior tree mode")

    def update_behavior_tree(self, delta_time: float):
        """Update the agent using the behavior tree system"""
        if not self.behavior_tree or not self.use_behavior_tree:
            return

        # Update position tracking for stuck detection
        current_time = time.time()
        if current_time - self.last_position_time > 2.0:
            self.last_position = (self.x, self.y)
            self.last_position_time = current_time

        # Update pathfinding (still needed for path-based movement)
        self.update_pathfinding(delta_time)

        # Check for health recovery to restore normal intention cooldown
        self.check_health_recovery()

        # Execute behavior tree
        try:
            status = self.behavior_tree.update(self, delta_time)
            logger.debug(f"Agent {self.id[:8]} behavior tree status: {status.value}")
        except Exception as e:
            logger.error(f"Error updating behavior tree for agent {self.id[:8]}: {e}")

        # Apply movement using velocity system
        self.move(delta_time)

    def get_behavior_tree_debug_info(self) -> Optional[Dict[str, Any]]:
        """Get debug information about the current behavior tree state"""
        if not self.behavior_tree:
            return None

        return self.behavior_tree.get_debug_info(self)

    # Utility methods for behavior tree nodes
    def set_target(self, target_x: float, target_y: float):
        """Set the current target position"""
        self.current_target = (target_x, target_y)

    def clear_target(self):
        """Clear the current target"""
        self.current_target = None

    def get_distance_to_target(self) -> Optional[float]:
        """Get distance to current target, or None if no target"""
        if not self.current_target:
            return None

        dx = self.current_target[0] - self.x
        dy = self.current_target[1] - self.y
        return math.sqrt(dx * dx + dy * dy)

    def move_towards_target(
        self, target_x: float, target_y: float, speed_multiplier: float = 1.0
    ):
        """Move towards a target position with optional speed multiplier"""
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 0:
            speed = self.speed * speed_multiplier
            self.velocity_x = (dx / distance) * speed
            self.velocity_y = (dy / distance) * speed
            self.rotation = math.degrees(math.atan2(dy, dx))

    def find_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Find an entity by ID in the visible entities list"""
        for entity in self.visible_entities:
            if entity.get("id") == entity_id:
                return entity
        return None

    def find_entities_by_type(self, entity_types: List[str]) -> List[Dict[str, Any]]:
        """Find all entities of specified types in the visible entities list"""
        matching_entities = []
        for entity in self.visible_entities:
            if (
                entity.get("type") in entity_types
                or entity.get("agent_type") in entity_types
            ):
                matching_entities.append(entity)
        return matching_entities

    def get_nearest_entity_of_type(
        self, entity_types: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get the nearest entity of the specified types"""
        nearest_entity = None
        nearest_distance = float("inf")

        for entity in self.find_entities_by_type(entity_types):
            dx = entity["x"] - self.x
            dy = entity["y"] - self.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < nearest_distance:
                nearest_distance = distance
                nearest_entity = entity

        return nearest_entity
