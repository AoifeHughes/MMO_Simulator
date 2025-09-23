from abc import ABC, abstractmethod
from typing import Tuple, List, Dict, Any, Optional
from shared.constants import DEFAULT_AGENT_SPEED, DEFAULT_VISION_RANGE, DEFAULT_VISION_ANGLE
from shared.math_utils import clamp, normalize_angle
from shared.collision import CollisionDetector
import time

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
        """Set the world bounds and initialize collision detector"""
        self.world_bounds = (width, height)
        self.collision_detector = CollisionDetector(width, height)

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

    def get_state(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'rotation': self.rotation,
            'type': self.agent_type,
            'health': self.health,
            'velocity_x': self.velocity_x,
            'velocity_y': self.velocity_y
        }

    def update_from_state(self, state: Dict[str, Any]):
        self.x = state.get('x', self.x)
        self.y = state.get('y', self.y)
        self.rotation = state.get('rotation', self.rotation)
        self.health = state.get('health', self.health)
        self.velocity_x = state.get('velocity_x', 0)
        self.velocity_y = state.get('velocity_y', 0)