"""
World Builder Pattern for Test Framework

Provides a fluent API for creating deterministic test worlds with
specific terrain layouts, obstacles, and environmental features.
"""

import random
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from server.world import ServerWorld
from shared.collision import CollisionDetector
from world.map import WorldMap
from world.tiles import TileType


class TerrainPattern(Enum):
    """Predefined terrain patterns for common test scenarios"""

    EMPTY = "empty"
    MAZE = "maze"
    ISLAND = "island"
    CORRIDOR = "corridor"
    ROOM = "room"
    POND = "pond"


class WorldBuilder:
    """
    Fluent builder for creating test worlds with specific characteristics.

    Example usage:
        world = (WorldBuilder(20, 20)
                .with_seed(12345)
                .add_maze(entrance=(1, 1), exit=(18, 18))
                .add_water_pond(center=(10, 10), radius=3)
                .add_agent_spawn("explorer", 1, 1)
                .build())
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.terrain: Dict[Tuple[int, int], TileType] = {}
        self.agent_spawns: List[Tuple[str, float, float]] = []
        self.world_objects: List[Dict] = []
        self.seed: Optional[int] = None
        self._random = random.Random()

        # Initialize with grass by default
        self._fill_area(0, 0, width, height, TileType.GRASS)

    def with_seed(self, seed: int) -> "WorldBuilder":
        """Set deterministic seed for reproducible worlds"""
        self.seed = seed
        self._random.seed(seed)
        return self

    def _fill_area(
        self, start_x: int, start_y: int, width: int, height: int, tile_type: TileType
    ):
        """Fill rectangular area with specified tile type"""
        for y in range(start_y, min(start_y + height, self.height)):
            for x in range(start_x, min(start_x + width, self.width)):
                self.terrain[(x, y)] = tile_type

    def add_walls_around_perimeter(self) -> "WorldBuilder":
        """Add walls around the entire world perimeter"""
        for x in range(self.width):
            self.terrain[(x, 0)] = TileType.WALL
            self.terrain[(x, self.height - 1)] = TileType.WALL

        for y in range(self.height):
            self.terrain[(0, y)] = TileType.WALL
            self.terrain[(self.width - 1, y)] = TileType.WALL

        return self

    def add_simple_maze(self, entrance: Tuple[int, int] = (1, 1)) -> "WorldBuilder":
        """
        Add a simple maze pattern for pathfinding tests.
        Creates a maze with guaranteed solution path.
        """
        # Fill with walls first
        self._fill_area(0, 0, self.width, self.height, TileType.WALL)

        # Create corridors (odd coordinates are walkable for simple maze)
        for y in range(1, self.height, 2):
            for x in range(1, self.width, 2):
                self.terrain[(x, y)] = TileType.GRASS

        # Create horizontal connections
        for y in range(1, self.height, 2):
            for x in range(3, self.width, 2):
                if self._random.random() > 0.3:  # 70% chance of connection
                    self.terrain[(x - 1, y)] = TileType.GRASS

        # Create vertical connections
        for y in range(3, self.height, 2):
            for x in range(1, self.width, 2):
                if self._random.random() > 0.3:  # 70% chance of connection
                    self.terrain[(x, y - 1)] = TileType.GRASS

        # Ensure entrance is walkable
        self.terrain[entrance] = TileType.GRASS

        return self

    def add_water_pond(self, center: Tuple[int, int], radius: int) -> "WorldBuilder":
        """Add circular water pond"""
        center_x, center_y = center

        for y in range(
            max(0, center_y - radius), min(self.height, center_y + radius + 1)
        ):
            for x in range(
                max(0, center_x - radius), min(self.width, center_x + radius + 1)
            ):
                distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                if distance <= radius:
                    self.terrain[(x, y)] = TileType.WATER

        return self

    def add_corridor(
        self, start: Tuple[int, int], end: Tuple[int, int], width: int = 1
    ) -> "WorldBuilder":
        """Add straight corridor between two points"""
        start_x, start_y = start
        end_x, end_y = end

        # Simple horizontal then vertical path
        # Horizontal segment
        min_x, max_x = min(start_x, end_x), max(start_x, end_x)
        for x in range(min_x, max_x + 1):
            for w in range(width):
                if start_y + w < self.height:
                    self.terrain[(x, start_y + w)] = TileType.GRASS

        # Vertical segment
        min_y, max_y = min(start_y, end_y), max(start_y, end_y)
        for y in range(min_y, max_y + 1):
            for w in range(width):
                if end_x + w < self.width:
                    self.terrain[(end_x + w, y)] = TileType.GRASS

        return self

    def add_room(
        self,
        top_left: Tuple[int, int],
        width: int,
        height: int,
        door_positions: Optional[List[Tuple[int, int]]] = None,
    ) -> "WorldBuilder":
        """Add rectangular room with optional doors"""
        x, y = top_left

        # Create room interior
        self._fill_area(x + 1, y + 1, width - 2, height - 2, TileType.GRASS)

        # Create walls
        for i in range(width):
            self.terrain[(x + i, y)] = TileType.WALL  # Top wall
            self.terrain[(x + i, y + height - 1)] = TileType.WALL  # Bottom wall

        for i in range(height):
            self.terrain[(x, y + i)] = TileType.WALL  # Left wall
            self.terrain[(x + width - 1, y + i)] = TileType.WALL  # Right wall

        # Add doors
        if door_positions:
            for door_x, door_y in door_positions:
                if x <= door_x < x + width and y <= door_y < y + height:
                    self.terrain[(door_x, door_y)] = TileType.GRASS

        return self

    def add_island(
        self, center: Tuple[int, int], island_radius: int, water_radius: int
    ) -> "WorldBuilder":
        """Add island surrounded by water"""
        center_x, center_y = center

        # Add water
        for y in range(
            max(0, center_y - water_radius),
            min(self.height, center_y + water_radius + 1),
        ):
            for x in range(
                max(0, center_x - water_radius),
                min(self.width, center_x + water_radius + 1),
            ):
                distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                if distance <= water_radius:
                    self.terrain[(x, y)] = TileType.WATER

        # Add island in center
        for y in range(
            max(0, center_y - island_radius),
            min(self.height, center_y + island_radius + 1),
        ):
            for x in range(
                max(0, center_x - island_radius),
                min(self.width, center_x + island_radius + 1),
            ):
                distance = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                if distance <= island_radius:
                    self.terrain[(x, y)] = TileType.GRASS

        return self

    def add_random_obstacles(
        self, density: float = 0.1, obstacle_type: TileType = TileType.WALL
    ) -> "WorldBuilder":
        """Add random obstacles with specified density (0.0 to 1.0)"""
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) not in [
                    (s[1], s[2]) for s in self.agent_spawns
                ]:  # Don't block spawn points
                    if self._random.random() < density:
                        self.terrain[(x, y)] = obstacle_type

        return self

    def add_agent_spawn(self, agent_type: str, x: float, y: float) -> "WorldBuilder":
        """Add agent spawn point"""
        self.agent_spawns.append((agent_type, x, y))
        # Ensure spawn point is walkable
        self.terrain[(int(x), int(y))] = TileType.GRASS
        return self

    def add_wood_resource(self, x: int, y: int) -> "WorldBuilder":
        """Add wood resource at specified location"""
        self.terrain[(x, y)] = TileType.WOOD
        self.world_objects.append({"type": "wood", "x": x, "y": y, "harvestable": True})
        return self

    def add_scattered_resources(
        self, resource_type: TileType, count: int
    ) -> "WorldBuilder":
        """Add randomly scattered resources"""
        walkable_tiles = [
            (x, y) for (x, y), tile in self.terrain.items() if tile == TileType.GRASS
        ]

        if len(walkable_tiles) < count:
            count = len(walkable_tiles)

        selected_tiles = self._random.sample(walkable_tiles, count)

        for x, y in selected_tiles:
            self.terrain[(x, y)] = resource_type
            self.world_objects.append(
                {
                    "type": resource_type.name.lower(),
                    "x": x,
                    "y": y,
                    "harvestable": True,
                }
            )

        return self

    def build(self) -> ServerWorld:
        """Build the final ServerWorld with all specified characteristics"""
        # Create ServerWorld with simple terrain (no Perlin noise)
        world = ServerWorld(width=self.width, height=self.height, use_perlin=False)

        # Set custom terrain
        for (x, y), tile_type in self.terrain.items():
            world.world_map.set_tile(x, y, tile_type)

        # Spawn agents
        for agent_type, x, y in self.agent_spawns:
            agent_id = world.spawn_agent(agent_type, x, y)

        return world

    def get_terrain_dict(self) -> Dict[Tuple[int, int], TileType]:
        """Get terrain as dictionary for legacy compatibility"""
        return self.terrain.copy()


class PredefinedWorlds:
    """Collection of predefined world templates for common test scenarios"""

    @staticmethod
    def empty_arena(size: int = 20) -> WorldBuilder:
        """Simple empty arena for basic movement tests"""
        return WorldBuilder(size, size).with_seed(12345).add_walls_around_perimeter()

    @staticmethod
    def simple_maze(size: int = 21) -> WorldBuilder:
        """Simple maze for pathfinding tests"""
        return (
            WorldBuilder(size, size).with_seed(54321).add_simple_maze(entrance=(1, 1))
        )

    @staticmethod
    def water_navigation_test() -> WorldBuilder:
        """World with water obstacles for navigation testing"""
        return (
            WorldBuilder(20, 20)
            .with_seed(11111)
            .add_water_pond(center=(10, 10), radius=4)
            .add_corridor(start=(0, 10), end=(6, 10), width=2)
            .add_corridor(start=(14, 10), end=(19, 10), width=2)
        )

    @staticmethod
    def multi_room_dungeon() -> WorldBuilder:
        """Multi-room environment for complex navigation"""
        return (
            WorldBuilder(30, 20)
            .with_seed(99999)
            .add_room(top_left=(2, 2), width=8, height=6, door_positions=[(9, 5)])
            .add_room(top_left=(12, 2), width=8, height=6, door_positions=[(12, 5)])
            .add_room(top_left=(22, 2), width=6, height=6, door_positions=[(22, 5)])
            .add_corridor(start=(9, 5), end=(12, 5), width=1)
            .add_corridor(start=(20, 5), end=(22, 5), width=1)
        )

    @staticmethod
    def resource_gathering_area() -> WorldBuilder:
        """Area with scattered resources for harvesting tests"""
        return (
            WorldBuilder(25, 25)
            .with_seed(77777)
            .add_scattered_resources(TileType.WOOD, 8)
            .add_water_pond(center=(12, 12), radius=3)
            .add_agent_spawn("explorer", 5, 5)
        )
