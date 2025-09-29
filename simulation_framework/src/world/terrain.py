from __future__ import annotations
from enum import Enum
from dataclasses import dataclass


class TerrainType(Enum):
    WATER = "water"
    GRASS = "grass"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    DESERT = "desert"


@dataclass
class TerrainProperties:
    passable: bool
    fishable: bool
    mineable: bool
    harvestable: bool
    movement_cost: float = 1.0

    @classmethod
    def for_terrain(cls, terrain_type: TerrainType) -> TerrainProperties:
        properties = {
            TerrainType.WATER: cls(
                passable=False,
                fishable=True,
                mineable=False,
                harvestable=False,
                movement_cost=float('inf')
            ),
            TerrainType.GRASS: cls(
                passable=True,
                fishable=False,
                mineable=False,
                harvestable=True,
                movement_cost=1.0
            ),
            TerrainType.FOREST: cls(
                passable=True,
                fishable=False,
                mineable=False,
                harvestable=True,
                movement_cost=1.5
            ),
            TerrainType.MOUNTAIN: cls(
                passable=True,
                fishable=False,
                mineable=True,
                harvestable=False,
                movement_cost=2.0
            ),
            TerrainType.DESERT: cls(
                passable=True,
                fishable=False,
                mineable=False,
                harvestable=False,
                movement_cost=1.5
            )
        }
        return properties[terrain_type]