"""
Authoritative game state management
"""

import time
import uuid
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging

from shared.math_utils import Vector2
from shared.constants import WORLD_WIDTH, WORLD_HEIGHT, ENTITY_VIEW_DISTANCES, PLAYER_TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class ServerEntity:
    """Server-side entity representation"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entity_type: str = "object"  # agent, npc, enemy, object, item
    position: Vector2 = field(default_factory=lambda: Vector2(0, 0))
    velocity: Vector2 = field(default_factory=lambda: Vector2(0, 0))

    # Stats
    health: float = 100.0
    max_health: float = 100.0
    level: int = 1

    # State
    state: str = "idle"
    alive: bool = True
    respawn_time: Optional[float] = None

    # Combat
    in_combat: bool = False
    target_id: Optional[str] = None
    last_attack_time: float = 0

    # Visibility
    vision_range: float = 100.0
    visible: bool = True

    # Metadata
    owner_id: Optional[str] = None  # For player-owned entities
    data: Dict[str, Any] = field(default_factory=dict)  # Extra data

    # Player persistence
    last_update_time: float = field(default_factory=time.time)
    is_active: bool = True  # Whether player is actively connected

    def get_view_distance(self) -> float:
        """Get how far this entity can be seen from"""
        return ENTITY_VIEW_DISTANCES.get(self.entity_type, 100.0)


class SpatialGrid:
    """Spatial partitioning for efficient proximity queries"""

    def __init__(self, width: float, height: float, cell_size: float = 100.0):
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.cols = int(width / cell_size) + 1
        self.rows = int(height / cell_size) + 1
        self.grid: Dict[Tuple[int, int], Set[str]] = {}
        self.entity_cells: Dict[str, Set[Tuple[int, int]]] = {}

    def _get_cells(self, position: Vector2, radius: float = 0) -> Set[Tuple[int, int]]:
        """Get all cells that overlap with a circle"""
        cells = set()

        min_x = max(0, int((position.x - radius) / self.cell_size))
        max_x = min(self.cols - 1, int((position.x + radius) / self.cell_size))
        min_y = max(0, int((position.y - radius) / self.cell_size))
        max_y = min(self.rows - 1, int((position.y + radius) / self.cell_size))

        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                cells.add((x, y))

        return cells

    def insert(self, entity_id: str, position: Vector2, radius: float = 0):
        """Insert entity into grid"""
        # Remove from old cells
        if entity_id in self.entity_cells:
            for cell in self.entity_cells[entity_id]:
                if cell in self.grid:
                    self.grid[cell].discard(entity_id)

        # Add to new cells
        cells = self._get_cells(position, radius)
        self.entity_cells[entity_id] = cells

        for cell in cells:
            if cell not in self.grid:
                self.grid[cell] = set()
            self.grid[cell].add(entity_id)

    def remove(self, entity_id: str):
        """Remove entity from grid"""
        if entity_id in self.entity_cells:
            for cell in self.entity_cells[entity_id]:
                if cell in self.grid:
                    self.grid[cell].discard(entity_id)
            del self.entity_cells[entity_id]

    def query_radius(self, position: Vector2, radius: float) -> Set[str]:
        """Get all entities within radius of position"""
        cells = self._get_cells(position, radius)
        entities = set()

        for cell in cells:
            if cell in self.grid:
                entities.update(self.grid[cell])

        return entities

    def update(self, entity_id: str, new_position: Vector2, radius: float = 0):
        """Update entity position"""
        self.insert(entity_id, new_position, radius)


class GameState:
    """Centralized game state management"""

    def __init__(self):
        # Entity storage
        self.entities: Dict[str, ServerEntity] = {}
        self.agents: Dict[str, str] = {}  # client_id -> entity_id mapping

        # Spatial indexing
        self.spatial_grid = SpatialGrid(WORLD_WIDTH, WORLD_HEIGHT)

        # World zones/areas
        self.zones: Dict[str, Any] = {}

        # Game time
        self.server_time = time.time()
        self.tick = 0

        # Statistics
        self.stats = {
            'entities_created': 0,
            'entities_destroyed': 0,
            'total_damage': 0,
            'total_healing': 0
        }

        logger.info("GameState initialized")

    def create_entity(self, **kwargs) -> ServerEntity:
        """Create a new entity"""
        entity = ServerEntity(**kwargs)
        self.entities[entity.id] = entity
        self.spatial_grid.insert(entity.id, entity.position, entity.vision_range)

        self.stats['entities_created'] += 1
        logger.debug(f"Created entity {entity.id} ({entity.entity_type})")

        return entity

    def destroy_entity(self, entity_id: str):
        """Remove entity from game"""
        if entity_id in self.entities:
            self.spatial_grid.remove(entity_id)
            del self.entities[entity_id]

            # Remove from agent mapping if applicable
            for client_id, eid in list(self.agents.items()):
                if eid == entity_id:
                    del self.agents[client_id]

            self.stats['entities_destroyed'] += 1
            logger.debug(f"Destroyed entity {entity_id}")

    def get_entity(self, entity_id: str) -> Optional[ServerEntity]:
        """Get entity by ID"""
        return self.entities.get(entity_id)

    def update_entity_position(self, entity_id: str, new_position: Vector2):
        """Update entity position and spatial index"""
        entity = self.get_entity(entity_id)
        if entity:
            entity.position = new_position
            self.spatial_grid.update(entity_id, new_position, entity.vision_range)

    def get_entities_in_range(self, position: Vector2, radius: float) -> List[ServerEntity]:
        """Get all entities within range of a position"""
        entity_ids = self.spatial_grid.query_radius(position, radius)
        entities = []

        for eid in entity_ids:
            entity = self.entities.get(eid)
            if entity and entity.position.distance_to(position) <= radius:
                entities.append(entity)

        return entities

    def get_visible_entities(self, observer_id: str) -> List[ServerEntity]:
        """Get entities visible to an observer"""
        observer = self.get_entity(observer_id)
        if not observer:
            return []

        # Get entities in vision range
        nearby = self.get_entities_in_range(observer.position, observer.vision_range)

        # Filter by line of sight (simplified - no obstacle checking yet)
        visible = []
        for entity in nearby:
            if entity.id != observer_id and entity.visible:
                # Check if entity is within its own view distance
                if observer.position.distance_to(entity.position) <= entity.get_view_distance():
                    visible.append(entity)

        return visible

    def apply_damage(self, target_id: str, amount: float, source_id: Optional[str] = None):
        """Apply damage to an entity"""
        target = self.get_entity(target_id)
        if target and target.alive:
            target.health = max(0, target.health - amount)
            self.stats['total_damage'] += amount

            if target.health <= 0:
                target.alive = False
                target.respawn_time = time.time() + 30.0  # 30 second respawn
                logger.info(f"Entity {target_id} died")

            # Set combat state
            if source_id:
                source = self.get_entity(source_id)
                if source:
                    source.in_combat = True
                    source.target_id = target_id
                target.in_combat = True

    def apply_healing(self, target_id: str, amount: float):
        """Apply healing to an entity"""
        target = self.get_entity(target_id)
        if target and target.alive:
            old_health = target.health
            target.health = min(target.max_health, target.health + amount)
            actual_heal = target.health - old_health
            self.stats['total_healing'] += actual_heal

    def update(self, delta_time: float):
        """Update game state"""
        self.tick += 1
        self.server_time = time.time()
        current_time = time.time()

        # Check for inactive players
        self.check_player_timeouts(current_time)

        # Update entity physics (only for active entities)
        for entity in self.entities.values():
            # Skip physics for inactive players
            if entity.entity_type == 'agent' and not entity.is_active:
                continue

            if entity.velocity.magnitude() > 0:
                # Simple movement
                new_x = entity.position.x + entity.velocity.x * delta_time
                new_y = entity.position.y + entity.velocity.y * delta_time

                # Boundary checking
                new_x = max(0, min(WORLD_WIDTH, new_x))
                new_y = max(0, min(WORLD_HEIGHT, new_y))

                self.update_entity_position(entity.id, Vector2(new_x, new_y))

        # Handle respawns
        for entity in self.entities.values():
            if not entity.alive and entity.respawn_time and current_time >= entity.respawn_time:
                entity.alive = True
                entity.health = entity.max_health
                entity.respawn_time = None
                logger.info(f"Entity {entity.id} respawned")

    def check_player_timeouts(self, current_time: float):
        """Check for players that have timed out and mark them inactive"""
        for entity in self.entities.values():
            if entity.entity_type == 'agent':
                if entity.is_active and (current_time - entity.last_update_time) > PLAYER_TIMEOUT:
                    entity.is_active = False
                    entity.velocity = Vector2(0, 0)  # Stop movement
                    entity.state = "disconnected"
                    logger.info(f"Player {entity.name} ({entity.id}) marked inactive due to timeout")

    def touch_player(self, entity_id: str):
        """Update player's last activity time"""
        entity = self.get_entity(entity_id)
        if entity and entity.entity_type == 'agent':
            was_inactive = not entity.is_active
            entity.last_update_time = time.time()
            entity.is_active = True
            if was_inactive:
                entity.state = "idle"
                logger.info(f"Player {entity.name} ({entity.id}) reconnected and reactivated")

    def get_active_players(self) -> List[ServerEntity]:
        """Get list of currently active players"""
        return [entity for entity in self.entities.values()
                if entity.entity_type == 'agent' and entity.is_active]

    def get_inactive_players(self) -> List[ServerEntity]:
        """Get list of inactive players (stored but not updated)"""
        return [entity for entity in self.entities.values()
                if entity.entity_type == 'agent' and not entity.is_active]

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of the current game state"""
        active_players = len(self.get_active_players())
        inactive_players = len(self.get_inactive_players())

        return {
            'tick': self.tick,
            'time': self.server_time,
            'entity_count': len(self.entities),
            'agent_count': len(self.agents),
            'active_players': active_players,
            'inactive_players': inactive_players,
            'stats': self.stats.copy()
        }