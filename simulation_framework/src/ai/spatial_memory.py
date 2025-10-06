"""
Spatial Memory System for Agent World Knowledge.

Agents remember explored tiles, resource locations, and entity sightings.
Reduces need for constant world scanning.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ResourceMemory:
    """Memory of a resource location"""

    position: Tuple[int, int]
    resource_type: str
    last_seen_tick: int
    last_seen_quantity: int = 0
    was_depleted: bool = False
    depletion_tick: int = 0


@dataclass
class TileMemory:
    """Memory of a tile"""

    position: Tuple[int, int]
    terrain_type: str
    last_visited_tick: int
    has_resources: bool = False
    is_passable: bool = True


@dataclass
class EntityMemory:
    """Memory of another entity"""

    entity_id: int
    last_seen_position: Tuple[int, int]
    last_seen_tick: int
    entity_type: str  # "agent", "npc", etc.
    was_hostile: bool = False


class SpatialMemory:
    """
    Agent's memory of the world.

    Stores information about:
    - Explored tiles
    - Known resource locations
    - Entity sightings
    - Terrain layout
    """

    def __init__(self, memory_duration: int = 100):
        self.memory_duration = memory_duration

        # Resource memories by type
        self.known_resources: Dict[str, List[ResourceMemory]] = {}

        # Tile memories
        self.visited_tiles: Dict[Tuple[int, int], TileMemory] = {}

        # Entity memories
        self.known_entities: Dict[int, EntityMemory] = {}

        # Exploration tracking
        self.explored_area: Set[Tuple[int, int]] = set()

    def remember_resource(
        self,
        resource_type: str,
        position: Tuple[int, int],
        quantity: int,
        current_tick: int,
    ) -> None:
        """Remember seeing a resource at a location"""
        if resource_type not in self.known_resources:
            self.known_resources[resource_type] = []

        # Check if we already have memory of this resource
        existing = None
        for mem in self.known_resources[resource_type]:
            if mem.position == position:
                existing = mem
                break

        if existing:
            # Update existing memory
            existing.last_seen_tick = current_tick
            existing.last_seen_quantity = quantity
            if quantity == 0:
                existing.was_depleted = True
                existing.depletion_tick = current_tick
            else:
                existing.was_depleted = False
        else:
            # Create new memory
            memory = ResourceMemory(
                position=position,
                resource_type=resource_type,
                last_seen_tick=current_tick,
                last_seen_quantity=quantity,
                was_depleted=(quantity == 0),
                depletion_tick=current_tick if quantity == 0 else 0,
            )
            self.known_resources[resource_type].append(memory)

    def remember_tile(
        self,
        position: Tuple[int, int],
        terrain_type: str,
        has_resources: bool,
        is_passable: bool,
        current_tick: int,
    ) -> None:
        """Remember visiting a tile"""
        self.visited_tiles[position] = TileMemory(
            position=position,
            terrain_type=terrain_type,
            last_visited_tick=current_tick,
            has_resources=has_resources,
            is_passable=is_passable,
        )
        self.explored_area.add(position)

    def remember_entity(
        self,
        entity_id: int,
        position: Tuple[int, int],
        entity_type: str,
        was_hostile: bool,
        current_tick: int,
    ) -> None:
        """Remember seeing an entity"""
        if entity_id in self.known_entities:
            # Update existing memory
            self.known_entities[entity_id].last_seen_position = position
            self.known_entities[entity_id].last_seen_tick = current_tick
            self.known_entities[entity_id].was_hostile = was_hostile
        else:
            # Create new memory
            self.known_entities[entity_id] = EntityMemory(
                entity_id=entity_id,
                last_seen_position=position,
                last_seen_tick=current_tick,
                entity_type=entity_type,
                was_hostile=was_hostile,
            )

    def get_known_resources(
        self,
        resource_type: str,
        agent_position: Tuple[int, int],
        current_tick: int,
        max_age: Optional[int] = None,
    ) -> List[Tuple[float, Tuple[int, int]]]:
        """
        Get known resource locations sorted by distance.

        Returns list of (distance, position) tuples.
        Filters out old memories and known depleted resources.
        """
        if resource_type not in self.known_resources:
            return []

        max_age = max_age or self.memory_duration
        results = []

        for memory in self.known_resources[resource_type]:
            # Skip if memory too old
            age = current_tick - memory.last_seen_tick
            if age > max_age:
                continue

            # Skip if known to be depleted recently
            if memory.was_depleted:
                # Assume respawn time ~100 ticks
                time_since_depletion = current_tick - memory.depletion_tick
                if time_since_depletion < 100:
                    continue

            # Calculate distance
            distance = math.sqrt(
                (memory.position[0] - agent_position[0]) ** 2
                + (memory.position[1] - agent_position[1]) ** 2
            )

            results.append((distance, memory.position))

        # Sort by distance
        results.sort()
        return results

    def get_nearest_known_resource(
        self, resource_type: str, agent_position: Tuple[int, int], current_tick: int
    ) -> Optional[Tuple[int, int]]:
        """Get nearest known resource position"""
        known = self.get_known_resources(resource_type, agent_position, current_tick)
        if known:
            return known[0][1]  # Return position of nearest
        return None

    def get_known_entity(self, entity_id: int) -> Optional[EntityMemory]:
        """Get memory of an entity"""
        return self.known_entities.get(entity_id)

    def get_nearby_entities(
        self,
        agent_position: Tuple[int, int],
        max_distance: float,
        current_tick: int,
        max_age: int = 50,
    ) -> List[EntityMemory]:
        """Get memories of nearby entities"""
        nearby = []

        for memory in self.known_entities.values():
            # Skip old memories
            if current_tick - memory.last_seen_tick > max_age:
                continue

            # Check distance
            distance = math.sqrt(
                (memory.last_seen_position[0] - agent_position[0]) ** 2
                + (memory.last_seen_position[1] - agent_position[1]) ** 2
            )

            if distance <= max_distance:
                nearby.append(memory)

        return nearby

    def forget_old_memories(self, current_tick: int) -> None:
        """Remove memories older than memory duration"""
        # Clean up old resource memories
        for resource_type in list(self.known_resources.keys()):
            self.known_resources[resource_type] = [
                mem
                for mem in self.known_resources[resource_type]
                if current_tick - mem.last_seen_tick <= self.memory_duration
            ]

            # Remove empty lists
            if not self.known_resources[resource_type]:
                del self.known_resources[resource_type]

        # Clean up old entity memories
        self.known_entities = {
            eid: mem
            for eid, mem in self.known_entities.items()
            if current_tick - mem.last_seen_tick <= self.memory_duration
        }

    def has_visited(self, position: Tuple[int, int]) -> bool:
        """Check if agent has visited a tile"""
        return position in self.explored_area

    def get_exploration_percentage(self, world_size: Tuple[int, int]) -> float:
        """Calculate percentage of world explored"""
        world_width, world_height = world_size
        total_tiles = world_width * world_height
        if total_tiles == 0:
            return 0.0
        return (len(self.explored_area) / total_tiles) * 100.0

    def get_memory_summary(self) -> Dict:
        """Get summary of memory contents for debugging"""
        resource_counts = {
            res_type: len(memories)
            for res_type, memories in self.known_resources.items()
        }

        return {
            "known_resource_types": list(self.known_resources.keys()),
            "resource_memories": resource_counts,
            "total_resource_memories": sum(resource_counts.values()),
            "visited_tiles": len(self.visited_tiles),
            "explored_area": len(self.explored_area),
            "known_entities": len(self.known_entities),
        }

    def __repr__(self) -> str:
        res_count = sum(len(mems) for mems in self.known_resources.values())
        return (
            f"SpatialMemory(resources={res_count}, "
            f"tiles={len(self.visited_tiles)}, "
            f"entities={len(self.known_entities)})"
        )
