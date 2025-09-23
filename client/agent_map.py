import math
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from world.tiles import TILE_PROPERTIES, TileType


class TileKnowledge(Enum):
    UNKNOWN = 0
    EXPLORED = 1


class AgentMap:
    """Personal map system for agents to track discovered terrain"""

    def __init__(self, world_width: int, world_height: int):
        self.world_width = world_width
        self.world_height = world_height

        # Initialize all tiles as unknown
        self.knowledge: List[List[TileKnowledge]] = []
        self.terrain: List[List[Optional[TileType]]] = []

        for y in range(world_height):
            knowledge_row = []
            terrain_row = []
            for x in range(world_width):
                knowledge_row.append(TileKnowledge.UNKNOWN)
                terrain_row.append(None)
            self.knowledge.append(knowledge_row)
            self.terrain.append(terrain_row)

    def is_valid_position(self, x: int, y: int) -> bool:
        """Check if coordinates are within map bounds"""
        return 0 <= x < self.world_width and 0 <= y < self.world_height

    def discover_tile(self, x: int, y: int, tile_type: TileType):
        """Mark a tile as discovered with its terrain type"""
        if self.is_valid_position(x, y):
            self.knowledge[y][x] = TileKnowledge.EXPLORED
            self.terrain[y][x] = tile_type

    def discover_area(
        self,
        center_x: float,
        center_y: float,
        radius: float,
        terrain_data: Dict[Tuple[int, int], TileType],
    ):
        """Discover multiple tiles within a radius based on vision"""
        center_tile_x = int(center_x)
        center_tile_y = int(center_y)

        # Check all tiles within the vision radius
        for y in range(
            max(0, center_tile_y - int(radius) - 1),
            min(self.world_height, center_tile_y + int(radius) + 2),
        ):
            for x in range(
                max(0, center_tile_x - int(radius) - 1),
                min(self.world_width, center_tile_x + int(radius) + 2),
            ):
                # Calculate distance from center
                distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)

                if distance <= radius:
                    # If we have terrain data for this position, discover it
                    if (x, y) in terrain_data:
                        self.discover_tile(x, y, terrain_data[(x, y)])

    def is_tile_known(self, x: int, y: int) -> bool:
        """Check if a tile has been explored"""
        if not self.is_valid_position(x, y):
            return False
        return self.knowledge[y][x] == TileKnowledge.EXPLORED

    def get_tile_type(self, x: int, y: int) -> Optional[TileType]:
        """Get the terrain type of a tile if known"""
        if not self.is_valid_position(x, y) or not self.is_tile_known(x, y):
            return None
        return self.terrain[y][x]

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if a tile is walkable (returns False for unknown tiles)"""
        tile_type = self.get_tile_type(x, y)
        if tile_type is None:
            return False  # Unknown tiles are considered non-walkable for pathfinding
        return TILE_PROPERTIES[tile_type].walkable

    def get_movement_cost(self, x: int, y: int) -> float:
        """Get movement cost for a tile (infinite for unknown/unwalkable tiles)"""
        tile_type = self.get_tile_type(x, y)
        if tile_type is None:
            return float("inf")  # Unknown tiles have infinite cost
        if not TILE_PROPERTIES[tile_type].walkable:
            return float("inf")
        return TILE_PROPERTIES[tile_type].movement_cost

    def get_known_tiles(self) -> Set[Tuple[int, int]]:
        """Get set of all known tile coordinates"""
        known_tiles = set()
        for y in range(self.world_height):
            for x in range(self.world_width):
                if self.is_tile_known(x, y):
                    known_tiles.add((x, y))
        return known_tiles

    def get_unknown_neighbors(
        self, x: int, y: int, radius: int = 1
    ) -> List[Tuple[int, int]]:
        """Get list of unknown tiles near a known position"""
        unknown_neighbors = []

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                new_x, new_y = x + dx, y + dy
                if self.is_valid_position(new_x, new_y) and not self.is_tile_known(
                    new_x, new_y
                ):
                    unknown_neighbors.append((new_x, new_y))

        return unknown_neighbors

    def get_exploration_frontiers(self) -> List[Tuple[int, int]]:
        """Find frontier tiles - unknown tiles adjacent to known tiles"""
        frontiers = []

        for y in range(self.world_height):
            for x in range(self.world_width):
                if not self.is_tile_known(x, y):
                    # Check if this unknown tile is adjacent to any known tile
                    is_frontier = False
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            neighbor_x, neighbor_y = x + dx, y + dy
                            if self.is_valid_position(
                                neighbor_x, neighbor_y
                            ) and self.is_tile_known(neighbor_x, neighbor_y):
                                is_frontier = True
                                break
                        if is_frontier:
                            break

                    if is_frontier:
                        frontiers.append((x, y))

        return frontiers

    def get_map_completion_percentage(self) -> float:
        """Calculate what percentage of the map has been explored"""
        total_tiles = self.world_width * self.world_height
        known_tiles = len(self.get_known_tiles())
        return (known_tiles / total_tiles) * 100.0

    def to_dict(self) -> Dict:
        """Convert map to dictionary for debugging/serialization"""
        return {
            "world_width": self.world_width,
            "world_height": self.world_height,
            "known_tiles": len(self.get_known_tiles()),
            "completion_percentage": self.get_map_completion_percentage(),
            "frontiers": len(self.get_exploration_frontiers()),
        }
