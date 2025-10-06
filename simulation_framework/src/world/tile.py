from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Set

from .terrain import TerrainProperties, TerrainType

if TYPE_CHECKING:
    pass


@dataclass
class ResourceDeposit:
    resource_type: str
    quantity: int
    respawn_time: int = 75  # Reduced from 100 for faster full respawn
    last_harvested: int = 0
    max_quantity: int = 0  # Maximum quantity for this deposit
    partial_respawn_rate: int = (
        3  # Increased from 2 - units respawned per partial_respawn_interval
    )
    partial_respawn_interval: int = (
        15  # Reduced from 20 - ticks between partial respawns
    )

    def __post_init__(self):
        """Initialize max_quantity if not set"""
        if self.max_quantity == 0:
            self.max_quantity = self.quantity

    def can_harvest(self, current_tick: int) -> bool:
        # Check for partial respawn first
        self._apply_partial_respawn(current_tick)

        if self.quantity <= 0:
            return current_tick - self.last_harvested >= self.respawn_time
        return True

    def _apply_partial_respawn(self, current_tick: int) -> None:
        """Apply partial respawn based on time elapsed"""
        if self.quantity >= self.max_quantity:
            return  # Already at max

        if self.last_harvested == 0:
            return  # Never harvested

        ticks_since_harvest = current_tick - self.last_harvested
        if ticks_since_harvest <= 0:
            return

        # Calculate how much should have respawned
        respawn_cycles = ticks_since_harvest // self.partial_respawn_interval
        respawned_amount = respawn_cycles * self.partial_respawn_rate

        if respawned_amount > 0:
            self.quantity = min(self.max_quantity, self.quantity + respawned_amount)
            # Update last_harvested to account for respawn cycles used
            self.last_harvested += respawn_cycles * self.partial_respawn_interval

    def harvest(self, amount: int, current_tick: int) -> int:
        # Apply partial respawn first
        self._apply_partial_respawn(current_tick)

        # If depleted, check for full respawn
        if self.quantity <= 0 and self.can_harvest(current_tick):
            self.quantity = self.max_quantity

        harvested = min(amount, self.quantity)
        self.quantity -= harvested

        if harvested > 0:
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

    def can_gather(
        self, resource_type: Optional[str] = None, current_tick: int = 0
    ) -> bool:
        """
        Check if resources can be gathered from this tile.

        Args:
            resource_type: Specific resource type to check, or None for any resource
            current_tick: Current simulation tick for respawn checking
        """
        if resource_type:
            # Check if specific resource type exists AND is harvestable
            for r in self.resources:
                if r.resource_type == resource_type:
                    return r.can_harvest(current_tick)
            return False
        else:
            # Check if any resource is harvestable
            return any(r.can_harvest(current_tick) for r in self.resources)

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
