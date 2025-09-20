"""
Client's limited view of the world
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import logging

from shared.math_utils import Vector2

logger = logging.getLogger(__name__)


@dataclass
class EntityInfo:
    """Client-side entity information"""
    id: str
    name: str
    entity_type: str
    position: Vector2
    health_percentage: float
    level: int
    state: str
    velocity: Optional[Vector2] = None
    last_seen: float = 0


class WorldView:
    """Client's limited view of the game world"""

    def __init__(self):
        # Visible entities
        self.entities: Dict[str, EntityInfo] = {}

        # Terrain and objects
        self.terrain: List[Dict] = []
        self.objects: Dict[str, Dict] = {}

        # Fog of war
        self.explored_areas: Set[tuple] = set()
        self.vision_range = 100.0

        # Current tick from server
        self.server_tick = 0

        logger.debug("WorldView initialized")

    def update(self, world_update):
        """Update world view from server message"""
        self.server_tick = world_update.tick

        # Track which entities are still visible
        visible_ids = set()

        # Update visible entities
        for entity_data in world_update.visible_entities:
            entity_id = entity_data['id']
            visible_ids.add(entity_id)

            # Create or update entity
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                entity.position = Vector2.from_tuple(entity_data['position'])
                entity.health_percentage = entity_data['health_percentage']
                entity.state = entity_data['state']
                entity.level = entity_data['level']

                if entity_data.get('velocity'):
                    entity.velocity = Vector2.from_tuple(entity_data['velocity'])
            else:
                # New entity
                self.entities[entity_id] = EntityInfo(
                    id=entity_id,
                    name=entity_data['name'],
                    entity_type=entity_data['entity_type'],
                    position=Vector2.from_tuple(entity_data['position']),
                    health_percentage=entity_data['health_percentage'],
                    level=entity_data['level'],
                    state=entity_data['state'],
                    velocity=Vector2.from_tuple(entity_data['velocity']) if entity_data.get('velocity') else None
                )

        # Remove entities that are no longer visible
        for entity_id in list(self.entities.keys()):
            if entity_id not in visible_ids:
                del self.entities[entity_id]

        # Process removed entities
        for entity_id in world_update.removed_entities:
            if entity_id in self.entities:
                del self.entities[entity_id]

    def get_nearby_entities(self, position: Vector2, radius: float,
                           entity_type: Optional[str] = None) -> List[EntityInfo]:
        """Get entities near a position"""
        nearby = []
        for entity in self.entities.values():
            if entity.position.distance_to(position) <= radius:
                if entity_type is None or entity.entity_type == entity_type:
                    nearby.append(entity)
        return nearby

    def get_entity(self, entity_id: str) -> Optional[EntityInfo]:
        """Get specific entity if visible"""
        return self.entities.get(entity_id)

    def set_vision_range(self, range: float):
        """Set vision range"""
        self.vision_range = range

    def is_explored(self, position: Vector2) -> bool:
        """Check if area has been explored"""
        grid_x = int(position.x / 50)  # 50 unit grid
        grid_y = int(position.y / 50)
        return (grid_x, grid_y) in self.explored_areas

    def mark_explored(self, position: Vector2):
        """Mark area as explored"""
        grid_x = int(position.x / 50)
        grid_y = int(position.y / 50)
        self.explored_areas.add((grid_x, grid_y))