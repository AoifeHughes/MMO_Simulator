from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
from shared.constants import DEFAULT_AGENT_SPEED, DEFAULT_VISION_RANGE, DEFAULT_VISION_ANGLE
from shared.math_utils import clamp, normalize_angle
from shared.collision import CollisionDetector
from shared.pathfinding import Pathfinder
from client.agent_map import AgentMap
from world.tiles import TileType
import time
import math

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

        self.visible_entities: List[Dict[str, Any]] = []
        self.last_update = time.time()

        # Collision detection (will be set when world bounds are known)
        self.collision_detector: Optional[CollisionDetector] = None
        self.world_bounds: Optional[Tuple[int, int]] = None

        # Pathfinding and mapping
        self.agent_map: Optional[AgentMap] = None
        self.pathfinder = Pathfinder()
        self.current_path: Optional[List[Tuple[float, float]]] = None
        self.current_waypoint: Optional[Tuple[float, float]] = None
        self.waypoint_threshold = 0.5

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
        """Find path to target position using agent's known map. Returns True if path found."""
        if not self.agent_map:
            return False

        path = self.pathfinder.find_path(
            self.agent_map,
            (self.x, self.y),
            (target_x, target_y)
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
            self.agent_map,
            (self.x, self.y)
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
            (self.current_waypoint[0] - current_pos[0])**2 +
            (self.current_waypoint[1] - current_pos[1])**2
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

    def discover_terrain_from_vision(self, terrain_data: Dict[Tuple[int, int], TileType]):
        """Update agent map with terrain discovered through vision"""
        if not self.agent_map:
            return

        # Discover terrain within vision range
        self.agent_map.discover_area(
            self.x, self.y, self.vision_range, terrain_data
        )

    def get_state(self) -> Dict[str, Any]:
        state = {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'rotation': self.rotation,
            'type': self.agent_type,
            'health': self.health,
            'velocity_x': self.velocity_x,
            'velocity_y': self.velocity_y
        }

        # Add pathfinding information if available
        if self.agent_map:
            state.update({
                'map_completion': self.agent_map.get_map_completion_percentage(),
                'has_path': self.current_path is not None,
                'current_waypoint': self.current_waypoint
            })

        return state

    def update_from_state(self, state: Dict[str, Any]):
        self.x = state.get('x', self.x)
        self.y = state.get('y', self.y)
        self.rotation = state.get('rotation', self.rotation)
        self.health = state.get('health', self.health)
        self.velocity_x = state.get('velocity_x', 0)
        self.velocity_y = state.get('velocity_y', 0)