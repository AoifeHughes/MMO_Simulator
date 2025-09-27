"""
Test-specific maps for targeted behavior testing

These maps are designed to test specific behaviors and edge cases:
- Small size for fast execution
- Controlled layouts for predictable behavior
- Specific terrain features for focused testing
"""

from typing import Dict, List, Tuple

from world.tiles import TileType


class TestMaps:
    """Collection of test maps for different scenarios"""

    @staticmethod
    def get_empty_arena(
        width: int = 20, height: int = 20
    ) -> Dict[Tuple[int, int], TileType]:
        """Empty arena - all walkable grass for basic movement tests"""
        terrain = {}
        for y in range(height):
            for x in range(width):
                terrain[(x, y)] = TileType.GRASS
        return terrain

    @staticmethod
    def get_combat_arena(
        width: int = 15, height: int = 15
    ) -> Dict[Tuple[int, int], TileType]:
        """Small combat arena with walls around the edge"""
        terrain = {}
        for y in range(height):
            for x in range(width):
                # Walls around the edge
                if x == 0 or x == width - 1 or y == 0 or y == height - 1:
                    terrain[(x, y)] = TileType.WALL
                else:
                    terrain[(x, y)] = TileType.GRASS
        return terrain

    @staticmethod
    def get_pathfinding_maze(
        width: int = 21, height: int = 21
    ) -> Dict[Tuple[int, int], TileType]:
        """Simple maze for pathfinding tests"""
        terrain = {}

        # Fill with walls
        for y in range(height):
            for x in range(width):
                terrain[(x, y)] = TileType.WALL

        # Create corridors (odd coordinates are walkable)
        for y in range(1, height, 2):
            for x in range(1, width, 2):
                terrain[(x, y)] = TileType.GRASS

                # Create horizontal connections
                if x + 1 < width:
                    terrain[(x + 1, y)] = TileType.GRASS

                # Create vertical connections
                if y + 1 < height:
                    terrain[(x, y + 1)] = TileType.GRASS

        return terrain

    @staticmethod
    def get_fishing_pond(
        width: int = 25, height: int = 25
    ) -> Dict[Tuple[int, int], TileType]:
        """Map with water features for fishing tests"""
        terrain = {}
        center_x, center_y = width // 2, height // 2

        for y in range(height):
            for x in range(width):
                # Create a circular pond in the center
                dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                if dist <= 8:
                    terrain[(x, y)] = TileType.WATER
                else:
                    terrain[(x, y)] = TileType.GRASS

        return terrain

    @staticmethod
    def get_exploration_terrain(
        width: int = 30, height: int = 30
    ) -> Dict[Tuple[int, int], TileType]:
        """Varied terrain for exploration behavior tests"""
        terrain = {}

        for y in range(height):
            for x in range(width):
                # Create varied terrain
                if x < 10:
                    terrain[(x, y)] = TileType.GRASS
                elif x < 20:
                    if (x + y) % 3 == 0:
                        terrain[(x, y)] = TileType.SAND
                    else:
                        terrain[(x, y)] = TileType.GRASS
                else:
                    if y < 15:
                        terrain[(x, y)] = (
                            TileType.WATER if (x + y) % 4 == 0 else TileType.GRASS
                        )
                    else:
                        terrain[(x, y)] = (
                            TileType.WALL if (x * y) % 7 == 0 else TileType.GRASS
                        )

        return terrain

    @staticmethod
    def get_corridor_test(
        width: int = 50, height: int = 10
    ) -> Dict[Tuple[int, int], TileType]:
        """Long narrow corridor for movement and collision tests"""
        terrain = {}

        for y in range(height):
            for x in range(width):
                if y == 0 or y == height - 1:
                    terrain[(x, y)] = TileType.WALL
                else:
                    terrain[(x, y)] = TileType.GRASS

        # Add some obstacles in the corridor
        for x in range(10, width, 15):
            if x < width - 5:
                terrain[(x, height // 2)] = TileType.WALL

        return terrain

    @staticmethod
    def get_multi_room_dungeon(
        width: int = 40, height: int = 30
    ) -> Dict[Tuple[int, int], TileType]:
        """Multi-room layout for complex pathfinding tests"""
        terrain = {}

        # Fill with walls
        for y in range(height):
            for x in range(width):
                terrain[(x, y)] = TileType.WALL

        # Define rooms (x1, y1, x2, y2)
        rooms = [
            (2, 2, 15, 12),  # Top-left room
            (25, 2, 37, 12),  # Top-right room
            (2, 18, 15, 27),  # Bottom-left room
            (25, 18, 37, 27),  # Bottom-right room
            (17, 12, 23, 18),  # Center connector
        ]

        # Create rooms
        for x1, y1, x2, y2 in rooms:
            for y in range(y1, y2):
                for x in range(x1, x2):
                    terrain[(x, y)] = TileType.GRASS

        # Create doorways
        doorways = [
            (16, 7),  # Top-left to center
            (24, 7),  # Center to top-right
            (16, 22),  # Bottom-left to center
            (24, 22),  # Center to bottom-right
        ]

        for x, y in doorways:
            terrain[(x, y)] = TileType.GRASS

        return terrain


class MapBuilder:
    """Builder for creating custom test maps"""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.terrain = {}
        # Default to grass
        for y in range(height):
            for x in range(width):
                self.terrain[(x, y)] = TileType.GRASS

    def add_walls_border(self) -> "TestMapBuilder":
        """Add walls around the border"""
        for y in range(self.height):
            for x in range(self.width):
                if x == 0 or x == self.width - 1 or y == 0 or y == self.height - 1:
                    self.terrain[(x, y)] = TileType.WALL
        return self

    def add_rect(
        self, x1: int, y1: int, x2: int, y2: int, tile_type: TileType
    ) -> "TestMapBuilder":
        """Add a rectangular area of specified tile type"""
        for y in range(max(0, y1), min(self.height, y2)):
            for x in range(max(0, x1), min(self.width, x2)):
                self.terrain[(x, y)] = tile_type
        return self

    def add_circle(
        self, center_x: int, center_y: int, radius: float, tile_type: TileType
    ) -> "TestMapBuilder":
        """Add a circular area of specified tile type"""
        for y in range(self.height):
            for x in range(self.width):
                dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
                if dist <= radius:
                    self.terrain[(x, y)] = tile_type
        return self

    def add_line(
        self, x1: int, y1: int, x2: int, y2: int, tile_type: TileType
    ) -> "TestMapBuilder":
        """Add a line of specified tile type using Bresenham's algorithm"""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        x_step = 1 if x1 < x2 else -1
        y_step = 1 if y1 < y2 else -1
        error = dx - dy

        x, y = x1, y1
        while True:
            if 0 <= x < self.width and 0 <= y < self.height:
                self.terrain[(x, y)] = tile_type

            if x == x2 and y == y2:
                break

            error2 = 2 * error
            if error2 > -dy:
                error -= dy
                x += x_step
            if error2 < dx:
                error += dx
                y += y_step

        return self

    def build(self) -> Dict[Tuple[int, int], TileType]:
        """Build and return the terrain map"""
        return self.terrain.copy()


def create_test_world_map(
    terrain_dict: Dict[Tuple[int, int], TileType], width: int, height: int
):
    """Create a WorldMap instance from terrain dictionary for testing"""
    from world.map import WorldMap

    # Create a basic world map with the specified terrain
    world_map = WorldMap(width, height, use_perlin=False)

    # Override the terrain with our test terrain
    for (x, y), tile_type in terrain_dict.items():
        if 0 <= x < width and 0 <= y < height:
            world_map.terrain[y][x] = tile_type

    return world_map
