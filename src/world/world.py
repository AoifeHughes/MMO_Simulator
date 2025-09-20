from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
import math
import logging
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


@dataclass
class Vector2:
    x: float
    y: float

    def distance_to(self, other: 'Vector2') -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def __hash__(self):
        return hash((self.x, self.y))


@dataclass
class Area:
    id: str
    name: str
    position: Vector2
    size: Vector2
    level_range: Tuple[int, int]
    danger_level: float = 0.5
    terrain_type: str = "grassland"
    connected_areas: List[str] = field(default_factory=list)


class SpatialIndex:
    """Quadtree-based spatial indexing for efficient proximity queries"""

    def __init__(self, bounds: Tuple[float, float, float, float], max_depth: int = 8):
        self.bounds = bounds  # (x_min, y_min, x_max, y_max)
        self.max_depth = max_depth
        self.root = self._create_node(bounds, 0)

    def _create_node(self, bounds: Tuple[float, float, float, float], depth: int):
        return {
            'bounds': bounds,
            'depth': depth,
            'entities': set(),
            'children': None
        }

    def insert(self, entity_id: str, position: Vector2):
        self._insert_recursive(self.root, entity_id, position)

    def _insert_recursive(self, node, entity_id: str, position: Vector2):
        x_min, y_min, x_max, y_max = node['bounds']

        if not (x_min <= position.x <= x_max and y_min <= position.y <= y_max):
            return False

        if node['depth'] >= self.max_depth or len(node['entities']) < 16:
            node['entities'].add((entity_id, position))
            return True

        if node['children'] is None:
            self._subdivide(node)

        for child in node['children']:
            if self._insert_recursive(child, entity_id, position):
                return True

        return False

    def _subdivide(self, node):
        x_min, y_min, x_max, y_max = node['bounds']
        mid_x = (x_min + x_max) / 2
        mid_y = (y_min + y_max) / 2
        depth = node['depth'] + 1

        node['children'] = [
            self._create_node((x_min, y_min, mid_x, mid_y), depth),  # SW
            self._create_node((mid_x, y_min, x_max, mid_y), depth),  # SE
            self._create_node((x_min, mid_y, mid_x, y_max), depth),  # NW
            self._create_node((mid_x, mid_y, x_max, y_max), depth),  # NE
        ]

        # Redistribute existing entities
        for entity in node['entities']:
            for child in node['children']:
                self._insert_recursive(child, entity[0], entity[1])
        node['entities'].clear()

    def query_radius(self, center: Vector2, radius: float) -> List[Tuple[str, Vector2]]:
        results = []
        self._query_radius_recursive(self.root, center, radius, results)
        return results

    def _query_radius_recursive(self, node, center: Vector2, radius: float, results: List):
        x_min, y_min, x_max, y_max = node['bounds']

        # Check if circle intersects with node bounds
        if not self._circle_intersects_rect(center, radius, node['bounds']):
            return

        # Check entities in this node
        for entity_id, pos in node['entities']:
            if center.distance_to(pos) <= radius:
                results.append((entity_id, pos))

        # Check children
        if node['children']:
            for child in node['children']:
                self._query_radius_recursive(child, center, radius, results)

    def _circle_intersects_rect(self, center: Vector2, radius: float,
                                bounds: Tuple[float, float, float, float]) -> bool:
        x_min, y_min, x_max, y_max = bounds
        closest_x = max(x_min, min(center.x, x_max))
        closest_y = max(y_min, min(center.y, y_max))
        distance = center.distance_to(Vector2(closest_x, closest_y))
        return distance <= radius

    def remove(self, entity_id: str):
        self._remove_recursive(self.root, entity_id)

    def _remove_recursive(self, node, entity_id: str):
        node['entities'] = {e for e in node['entities'] if e[0] != entity_id}

        if node['children']:
            for child in node['children']:
                self._remove_recursive(child, entity_id)


class World:
    def __init__(self):
        self.width = 10000.0
        self.height = 10000.0
        self.areas: Dict[str, Area] = {}
        self.agents: Dict[str, Any] = {}
        self.npcs: Dict[str, Any] = {}
        self.enemies: Dict[str, Any] = {}
        self.objects: Dict[str, Any] = {}
        self.items: Dict[str, Any] = {}
        self.terrain: Dict[str, Any] = {}

        # Spatial indexing for efficient proximity queries
        self.spatial_index = SpatialIndex((0, 0, self.width, self.height))

        # Entity positions tracked separately for performance
        self.entity_positions: Dict[str, Vector2] = {}

        # Initialize world areas
        self._initialize_areas()

        logger.info(f"World initialized: {self.width}x{self.height}")

    def _initialize_areas(self):
        """Create initial world areas"""
        starting_area = Area(
            id="starting_zone",
            name="Newbie Valley",
            position=Vector2(1000, 1000),
            size=Vector2(500, 500),
            level_range=(1, 10),
            danger_level=0.2,
            terrain_type="grassland"
        )
        self.areas[starting_area.id] = starting_area

        forest_area = Area(
            id="dark_forest",
            name="Dark Forest",
            position=Vector2(2000, 1500),
            size=Vector2(800, 800),
            level_range=(10, 25),
            danger_level=0.6,
            terrain_type="forest",
            connected_areas=["starting_zone"]
        )
        self.areas[forest_area.id] = forest_area

        mountain_area = Area(
            id="crystal_mountains",
            name="Crystal Mountains",
            position=Vector2(3500, 2000),
            size=Vector2(1000, 1000),
            level_range=(25, 50),
            danger_level=0.8,
            terrain_type="mountain",
            connected_areas=["dark_forest"]
        )
        self.areas[mountain_area.id] = mountain_area

    def fixed_update(self, delta_time: float):
        """Fixed timestep update for physics and critical systems"""
        # Update terrain systems
        for terrain_id, terrain in self.terrain.items():
            if hasattr(terrain, 'fixed_update'):
                terrain.fixed_update(delta_time)

        # Update game objects
        for obj_id, obj in self.objects.items():
            if hasattr(obj, 'fixed_update'):
                obj.fixed_update(delta_time)

    def add_agent(self, agent):
        """Add an agent to the world"""
        self.agents[agent.id] = agent
        if hasattr(agent, 'position'):
            self.entity_positions[agent.id] = agent.position
            self.spatial_index.insert(agent.id, agent.position)
        logger.debug(f"Added agent {agent.id} to world")

    def remove_agent(self, agent_id: str):
        """Remove an agent from the world"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            if agent_id in self.entity_positions:
                self.spatial_index.remove(agent_id)
                del self.entity_positions[agent_id]
            logger.debug(f"Removed agent {agent_id} from world")

    def add_npc(self, npc):
        """Add an NPC to the world"""
        self.npcs[npc.id] = npc
        if hasattr(npc, 'position'):
            self.entity_positions[npc.id] = npc.position
            self.spatial_index.insert(npc.id, npc.position)
        logger.debug(f"Added NPC {npc.id} to world")

    def add_enemy(self, enemy):
        """Add an enemy to the world"""
        self.enemies[enemy.id] = enemy
        if hasattr(enemy, 'position'):
            self.entity_positions[enemy.id] = enemy.position
            self.spatial_index.insert(enemy.id, enemy.position)
        logger.debug(f"Added enemy {enemy.id} to world")

    def add_object(self, obj):
        """Add a game object to the world"""
        self.objects[obj.id] = obj
        if hasattr(obj, 'position'):
            self.entity_positions[obj.id] = obj.position
            self.spatial_index.insert(obj.id, obj.position)
        logger.debug(f"Added object {obj.id} to world")

    def add_item(self, item):
        """Add an item to the world"""
        self.items[item.id] = item
        if hasattr(item, 'position'):
            self.entity_positions[item.id] = item.position
            self.spatial_index.insert(item.id, item.position)
        logger.debug(f"Added item {item.id} to world")

    def update_entity_position(self, entity_id: str, new_position: Vector2):
        """Update an entity's position in the spatial index"""
        if entity_id in self.entity_positions:
            self.spatial_index.remove(entity_id)
            self.entity_positions[entity_id] = new_position
            self.spatial_index.insert(entity_id, new_position)

    def get_entities_in_radius(self, center: Vector2, radius: float) -> List[str]:
        """Get all entities within a radius of a point"""
        results = self.spatial_index.query_radius(center, radius)
        return [entity_id for entity_id, _ in results]

    def get_nearby_agents(self, position: Vector2, radius: float) -> List[Any]:
        """Get agents within radius of a position"""
        entity_ids = self.get_entities_in_radius(position, radius)
        return [self.agents[eid] for eid in entity_ids if eid in self.agents]

    def get_nearby_enemies(self, position: Vector2, radius: float) -> List[Any]:
        """Get enemies within radius of a position"""
        entity_ids = self.get_entities_in_radius(position, radius)
        return [self.enemies[eid] for eid in entity_ids if eid in self.enemies]

    def get_all_agents(self) -> List[Any]:
        """Get all agents in the world"""
        return list(self.agents.values())

    def get_area_at_position(self, position: Vector2) -> Optional[Area]:
        """Get the area containing a specific position"""
        for area in self.areas.values():
            if (area.position.x <= position.x <= area.position.x + area.size.x and
                area.position.y <= position.y <= area.position.y + area.size.y):
                return area
        return None

    def get_stats(self) -> dict:
        """Get world statistics"""
        return {
            'total_agents': len(self.agents),
            'total_npcs': len(self.npcs),
            'total_enemies': len(self.enemies),
            'total_objects': len(self.objects),
            'total_items': len(self.items),
            'total_areas': len(self.areas),
            'world_size': f"{self.width}x{self.height}"
        }