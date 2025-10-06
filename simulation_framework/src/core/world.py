from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from ..world.generator import WorldGenerator
from ..world.resource_manager import ResourceManager
from ..world.tile import Tile

if TYPE_CHECKING:
    from ..entities.base import Entity


class World:
    def __init__(self, width: int, height: int, seed: Optional[int] = None):
        self.width = width
        self.height = height
        self.seed = seed
        self.tiles: List[List[Tile]] = []
        self.entities: Dict[int, Entity] = {}
        self.current_tick = 0
        self.resource_manager: Optional[ResourceManager] = None

        self._initialize_world()

    def _initialize_world(self) -> None:
        generator = WorldGenerator(seed=self.seed)
        self.tiles = generator.generate_world(self.width, self.height)

        # Initialize resource manager after world generation
        self.resource_manager = ResourceManager(self)

    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        if self.is_valid_position(x, y):
            return self.tiles[y][x]
        return None

    def is_valid_position(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_passable(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        return tile is not None and tile.can_pass()

    def get_neighbors(
        self, x: int, y: int, diagonal: bool = True
    ) -> List[Tuple[int, int]]:
        neighbors = []
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if diagonal:
            directions.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if self.is_valid_position(nx, ny):
                neighbors.append((nx, ny))

        return neighbors

    def get_passable_neighbors(
        self, x: int, y: int, diagonal: bool = True
    ) -> List[Tuple[int, int]]:
        neighbors = self.get_neighbors(x, y, diagonal)
        return [(nx, ny) for nx, ny in neighbors if self.is_passable(nx, ny)]

    def get_entities_at(self, x: int, y: int) -> Set[Entity]:
        result = set()
        for entity in self.entities.values():
            if entity.position == (x, y):
                result.add(entity)
        return result

    def get_entities_in_range(
        self, x: int, y: int, radius: float
    ) -> List[Tuple[Entity, float]]:
        entities_with_distance = []

        for entity in self.entities.values():
            ex, ey = entity.position
            distance = math.sqrt((ex - x) ** 2 + (ey - y) ** 2)
            if distance <= radius:
                entities_with_distance.append((entity, distance))

        entities_with_distance.sort(key=lambda x: x[1])
        return entities_with_distance

    def add_entity(self, entity: Entity) -> None:
        self.entities[entity.id] = entity
        x, y = entity.position
        tile = self.get_tile(x, y)
        if tile:
            tile.entities.add(entity.id)

    def remove_entity(self, entity_id: int) -> None:
        if entity_id in self.entities:
            entity = self.entities[entity_id]
            x, y = entity.position
            tile = self.get_tile(x, y)
            if tile:
                tile.entities.discard(entity_id)
            del self.entities[entity_id]

    def move_entity(self, entity: Entity, new_x: int, new_y: int) -> bool:
        if not self.is_passable(new_x, new_y):
            return False

        old_x, old_y = entity.position
        old_tile = self.get_tile(old_x, old_y)
        new_tile = self.get_tile(new_x, new_y)

        if old_tile:
            old_tile.entities.discard(entity.id)
        if new_tile:
            new_tile.entities.add(entity.id)

        entity.position = (new_x, new_y)
        return True

    def get_spawn_points(self, zone_name: str) -> List[Tuple[int, int]]:
        spawn_points = []
        for y in range(self.height):
            for x in range(self.width):
                tile = self.tiles[y][x]
                if tile.is_spawn_zone(zone_name):
                    spawn_points.append((x, y))
        return spawn_points

    def tick(self) -> None:
        self.current_tick += 1

    def get_terrain_distribution(self) -> Dict[str, float]:
        from ..world.terrain import TerrainType

        counts = {terrain_type.value: 0 for terrain_type in TerrainType}
        total = self.width * self.height

        for row in self.tiles:
            for tile in row:
                counts[tile.terrain_type.value] += 1

        return {k: v / total for k, v in counts.items()}
