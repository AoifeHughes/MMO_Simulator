from enum import Enum
from dataclasses import dataclass
from typing import Tuple

class TileType(Enum):
    GRASS = 0
    WATER = 1
    STONE = 2
    SAND = 3
    DIRT = 4
    WOOD = 5
    WALL = 6
    DOOR = 7
    BRIDGE = 8
    LAVA = 9

@dataclass
class TileProperties:
    walkable: bool
    blocking_vision: bool
    movement_cost: float
    color: Tuple[int, int, int]

TILE_PROPERTIES = {
    TileType.GRASS: TileProperties(
        walkable=True,
        blocking_vision=False,
        movement_cost=1.0,
        color=(34, 139, 34)
    ),
    TileType.WATER: TileProperties(
        walkable=False,
        blocking_vision=False,
        movement_cost=3.0,
        color=(64, 164, 223)
    ),
    TileType.STONE: TileProperties(
        walkable=True,
        blocking_vision=False,
        movement_cost=1.2,
        color=(128, 128, 128)
    ),
    TileType.SAND: TileProperties(
        walkable=True,
        blocking_vision=False,
        movement_cost=1.5,
        color=(238, 203, 173)
    ),
    TileType.DIRT: TileProperties(
        walkable=True,
        blocking_vision=False,
        movement_cost=1.1,
        color=(139, 90, 43)
    ),
    TileType.WOOD: TileProperties(
        walkable=True,
        blocking_vision=False,
        movement_cost=1.0,
        color=(139, 69, 19)
    ),
    TileType.WALL: TileProperties(
        walkable=False,
        blocking_vision=True,
        movement_cost=float('inf'),
        color=(88, 88, 88)
    ),
    TileType.DOOR: TileProperties(
        walkable=True,
        blocking_vision=True,
        movement_cost=1.0,
        color=(139, 90, 0)
    ),
    TileType.BRIDGE: TileProperties(
        walkable=True,
        blocking_vision=False,
        movement_cost=1.0,
        color=(160, 82, 45)
    ),
    TileType.LAVA: TileProperties(
        walkable=False,
        blocking_vision=False,
        movement_cost=float('inf'),
        color=(255, 69, 0)
    )
}