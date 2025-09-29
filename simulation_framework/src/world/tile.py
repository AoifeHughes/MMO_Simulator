from __future__ import annotations
from typing import List, Optional, Set, TYPE_CHECKING
from dataclasses import dataclass, field

from .terrain import TerrainType, TerrainProperties

if TYPE_CHECKING:
    from ..items.item import Item


@dataclass
class ResourceDeposit:
    resource_type: str
    quantity: int
    respawn_time: int = 100
    last_harvested: int = 0

    def can_harvest(self, current_tick: int) -> bool:
        if self.quantity <= 0:
            return current_tick - self.last_harvested >= self.respawn_time
        return True

    def harvest(self, amount: int, current_tick: int) -> int:
        if self.quantity <= 0 and self.can_harvest(current_tick):
            self.quantity = 10

        harvested = min(amount, self.quantity)
        self.quantity -= harvested

        if self.quantity == 0:
            self.last_harvested = current_tick

        return harvested


class Tile:
    def __init__(self, x: int, y: int, terrain_type: TerrainType):
        self.x = x
        self.y = y
        self.terrain_type = terrain_type
        self.properties = TerrainProperties.for_terrain(terrain_type)
        self.resources: List[ResourceDeposit] = []
        self.spawn_zones: Set[str] = set()
        self.entities: Set[int] = set()

    def can_pass(self) -> bool:
        return self.properties.passable

    def can_gather(self, resource_type: Optional[str] = None) -> bool:
        if resource_type:
            return any(r.resource_type == resource_type for r in self.resources)
        return len(self.resources) > 0

    def get_resources(self) -> List[ResourceDeposit]:
        return self.resources

    def add_resource(self, resource: ResourceDeposit) -> None:
        self.resources.append(resource)

    def add_spawn_zone(self, zone_name: str) -> None:
        self.spawn_zones.add(zone_name)

    def is_spawn_zone(self, zone_name: Optional[str] = None) -> bool:
        if zone_name:
            return zone_name in self.spawn_zones
        return len(self.spawn_zones) > 0

    def get_movement_cost(self) -> float:
        return self.properties.movement_cost

    def __repr__(self) -> str:
        return f"Tile({self.x}, {self.y}, {self.terrain_type.value})"