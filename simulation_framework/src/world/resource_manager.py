"""
Resource Manager for efficient resource tracking and querying.

Provides O(1) resource lookups instead of O(n²) world scanning.
Tracks resource availability and respawn timing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from .tile import ResourceDeposit
    from .world import World


@dataclass
class ResourceNode:
    """Represents a resource location in the world"""

    position: Tuple[int, int]
    resource_type: str
    last_known_quantity: int = 0
    last_checked_tick: int = 0
    is_depleted: bool = False
    respawn_tick: int = 0


class ResourceManager:
    """
    Centralized resource tracking system.

    Maintains spatial index of all resources for efficient queries.
    Tracks resource availability and respawn timing.
    """

    def __init__(self, world: World):
        self.world = world

        # Resource index: resource_type -> list of (x, y) positions
        self.resource_index: Dict[str, List[Tuple[int, int]]] = {}

        # Position to resource deposit mapping for fast lookup
        self.position_to_resources: Dict[Tuple[int, int], List[ResourceDeposit]] = {}

        # Resource nodes with metadata
        self.resource_nodes: Dict[Tuple[int, int, str], ResourceNode] = {}

        # Depleted resources awaiting respawn
        self.depleted_resources: Set[Tuple[int, int, str]] = set()

        # Build initial index
        self._build_resource_index()

    def _build_resource_index(self) -> None:
        """Build resource index from world tiles (called once at initialization)"""
        for y in range(self.world.height):
            for x in range(self.world.width):
                tile = self.world.get_tile(x, y)
                if tile and tile.resources:
                    position = (x, y)
                    self.position_to_resources[position] = tile.resources

                    for resource in tile.resources:
                        resource_type = resource.resource_type

                        # Add to index
                        if resource_type not in self.resource_index:
                            self.resource_index[resource_type] = []
                        self.resource_index[resource_type].append(position)

                        # Create resource node
                        node_key = (x, y, resource_type)
                        self.resource_nodes[node_key] = ResourceNode(
                            position=position,
                            resource_type=resource_type,
                            last_known_quantity=resource.quantity,
                            last_checked_tick=0,
                            is_depleted=resource.quantity == 0,
                        )

    def get_all_resource_positions(self, resource_type: str) -> List[Tuple[int, int]]:
        """Get all positions containing a resource type"""
        return self.resource_index.get(resource_type, []).copy()

    def get_available_resources(
        self,
        resource_type: str,
        current_tick: int,
        agent_position: Optional[Tuple[int, int]] = None,
        max_distance: Optional[float] = None,
    ) -> List[Tuple[int, int]]:
        """
        Get list of available (harvestable) resource positions.

        Args:
            resource_type: Type of resource to find
            current_tick: Current simulation tick
            agent_position: Optional agent position for distance filtering
            max_distance: Optional maximum distance from agent

        Returns:
            List of (x, y) positions with harvestable resources
        """
        available = []

        for position in self.resource_index.get(resource_type, []):
            x, y = position
            node_key = (x, y, resource_type)

            # Check if we have metadata for this node
            if node_key in self.resource_nodes:
                node = self.resource_nodes[node_key]

                # Skip if depleted and not yet respawned
                if node.is_depleted and current_tick < node.respawn_tick:
                    continue

            # Check actual tile resource status
            tile = self.world.get_tile(x, y)
            if not tile:
                continue

            # Find the specific resource deposit
            resource_deposit = None
            for res in tile.resources:
                if res.resource_type == resource_type:
                    resource_deposit = res
                    break

            if not resource_deposit:
                continue

            # Check if can harvest at this tick
            if not resource_deposit.can_harvest(current_tick):
                # Update depletion info
                if node_key in self.resource_nodes:
                    self.resource_nodes[node_key].is_depleted = True
                    self.resource_nodes[node_key].respawn_tick = (
                        resource_deposit.last_harvested + resource_deposit.respawn_time
                    )
                continue

            # Check distance if specified
            if agent_position and max_distance:
                distance = math.sqrt(
                    (x - agent_position[0]) ** 2 + (y - agent_position[1]) ** 2
                )
                if distance > max_distance:
                    continue

            available.append(position)

        return available

    def get_nearest_resource(
        self, resource_type: str, agent_position: Tuple[int, int], current_tick: int
    ) -> Optional[Tuple[int, int]]:
        """Find the nearest available resource of given type"""
        available = self.get_available_resources(
            resource_type, current_tick, agent_position
        )

        if not available:
            return None

        # Sort by distance
        agent_x, agent_y = agent_position
        distances = [
            (math.sqrt((x - agent_x) ** 2 + (y - agent_y) ** 2), (x, y))
            for x, y in available
        ]

        distances.sort()
        return distances[0][1]

    def mark_resource_harvested(
        self,
        position: Tuple[int, int],
        resource_type: str,
        current_tick: int,
        respawn_time: int,
    ) -> None:
        """Mark a resource as harvested/depleted"""
        node_key = (position[0], position[1], resource_type)

        if node_key in self.resource_nodes:
            self.resource_nodes[node_key].is_depleted = True
            self.resource_nodes[node_key].respawn_tick = current_tick + respawn_time
            self.resource_nodes[node_key].last_checked_tick = current_tick
            self.depleted_resources.add(node_key)

    def update_resource_status(
        self,
        position: Tuple[int, int],
        resource_type: str,
        quantity: int,
        current_tick: int,
    ) -> None:
        """Update resource node status"""
        node_key = (position[0], position[1], resource_type)

        if node_key in self.resource_nodes:
            self.resource_nodes[node_key].last_known_quantity = quantity
            self.resource_nodes[node_key].last_checked_tick = current_tick

            if quantity > 0:
                self.resource_nodes[node_key].is_depleted = False
                self.depleted_resources.discard(node_key)
            else:
                self.resource_nodes[node_key].is_depleted = True
                self.depleted_resources.add(node_key)

    def get_resource_statistics(self, resource_type: Optional[str] = None) -> Dict:
        """Get statistics about resources"""
        if resource_type:
            positions = self.resource_index.get(resource_type, [])
            depleted_count = sum(
                1
                for pos in positions
                if (pos[0], pos[1], resource_type) in self.depleted_resources
            )

            return {
                "resource_type": resource_type,
                "total_nodes": len(positions),
                "depleted_nodes": depleted_count,
                "available_nodes": len(positions) - depleted_count,
            }
        else:
            # All resources
            stats = {}
            for res_type in self.resource_index.keys():
                stats[res_type] = self.get_resource_statistics(res_type)
            return stats

    def cleanup_respawned_resources(self, current_tick: int) -> int:
        """
        Check depleted resources and mark them available if respawned.
        Returns count of resources that respawned.
        """
        respawned_count = 0
        to_remove = set()

        for node_key in self.depleted_resources:
            x, y, resource_type = node_key
            node = self.resource_nodes[node_key]

            if current_tick >= node.respawn_tick:
                # Check actual tile status
                tile = self.world.get_tile(x, y)
                if tile:
                    for resource in tile.resources:
                        if resource.resource_type == resource_type:
                            if resource.can_harvest(current_tick):
                                node.is_depleted = False
                                to_remove.add(node_key)
                                respawned_count += 1
                                break

        # Remove respawned resources from depleted set
        self.depleted_resources -= to_remove

        return respawned_count

    def __repr__(self) -> str:
        resource_counts = {
            res_type: len(positions)
            for res_type, positions in self.resource_index.items()
        }
        return f"ResourceManager(resources={resource_counts}, depleted={len(self.depleted_resources)})"
