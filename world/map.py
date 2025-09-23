import random
from typing import List, Optional, Tuple

from shared.constants import WORLD_HEIGHT, WORLD_WIDTH
from world.terrain_generator import TerrainType, generate_terrain
from world.tiles import TILE_PROPERTIES, TileType


class WorldMap:
    def __init__(
        self,
        width: int = WORLD_WIDTH,
        height: int = WORLD_HEIGHT,
        terrain_type: Optional[TerrainType] = None,
        seed: int = 42,
        use_perlin: bool = True,
    ):
        self.width = width
        self.height = height
        self.terrain_type = terrain_type or TerrainType.MIXED
        self.seed = seed
        self.use_perlin = use_perlin
        self.tiles: List[List[TileType]] = []
        self.generate()

    def generate(self):
        if self.use_perlin:
            # Use Perlin noise terrain generation
            self.tiles = generate_terrain(
                self.width, self.height, self.seed, self.terrain_type
            )
        else:
            # Use simple flat grass generation (legacy)
            for y in range(self.height):
                row = []
                for x in range(self.width):
                    row.append(TileType.GRASS)
                self.tiles.append(row)

    def get_tile(self, x: int, y: int) -> Optional[TileType]:
        if self.is_valid_position(x, y):
            return self.tiles[y][x]
        return None

    def set_tile(self, x: int, y: int, tile_type: TileType):
        if self.is_valid_position(x, y):
            self.tiles[y][x] = tile_type

    def is_valid_position(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        if tile is None:
            return False
        return TILE_PROPERTIES[tile].walkable

    def blocks_vision(self, x: int, y: int) -> bool:
        tile = self.get_tile(x, y)
        if tile is None:
            return True
        return TILE_PROPERTIES[tile].blocking_vision

    def get_movement_cost(self, x: int, y: int) -> float:
        tile = self.get_tile(x, y)
        if tile is None:
            return float("inf")
        return TILE_PROPERTIES[tile].movement_cost

    def get_random_walkable_position(self) -> Tuple[int, int]:
        while True:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if self.is_walkable(x, y):
                return x, y

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "tiles": [[tile.value for tile in row] for row in self.tiles],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorldMap":
        world_map = cls(data["width"], data["height"])
        world_map.tiles = [[TileType(value) for value in row] for row in data["tiles"]]
        return world_map
