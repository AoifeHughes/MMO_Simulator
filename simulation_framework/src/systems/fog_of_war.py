from __future__ import annotations
from typing import Set, Tuple, Dict, Optional, TYPE_CHECKING
import math

if TYPE_CHECKING:
    from ..entities.base import Entity
    from ..core.world import World


class FogOfWar:
    """Manages what each agent can see and remember"""

    def __init__(self, world_width: int, world_height: int):
        self.world_width = world_width
        self.world_height = world_height
        self.agent_vision: Dict[int, Set[Tuple[int, int]]] = {}  # agent_id -> visible tiles
        self.agent_memory: Dict[int, Dict[Tuple[int, int], Dict]] = {}  # agent_id -> tile -> info
        self.memory_duration = 100  # How long to remember unseen tiles

    def update_agent_vision(self, agent: Entity, world: World) -> None:
        """Update what an agent can currently see"""
        agent_x, agent_y = agent.position
        vision_range = agent.vision_range

        visible_tiles = set()

        # Calculate visible tiles using line of sight
        for dy in range(-vision_range, vision_range + 1):
            for dx in range(-vision_range, vision_range + 1):
                target_x = agent_x + dx
                target_y = agent_y + dy

                # Check bounds
                if not (0 <= target_x < self.world_width and 0 <= target_y < self.world_height):
                    continue

                # Check distance
                distance = math.sqrt(dx * dx + dy * dy)
                if distance > vision_range:
                    continue

                # Check line of sight
                if self._has_line_of_sight(agent_x, agent_y, target_x, target_y, world):
                    visible_tiles.add((target_x, target_y))

        self.agent_vision[agent.id] = visible_tiles

        # Update memory with current vision
        self._update_agent_memory(agent, world, visible_tiles)

    def _has_line_of_sight(self, x1: int, y1: int, x2: int, y2: int, world: World) -> bool:
        """Check if there's a clear line of sight between two points"""
        # Use Bresenham's line algorithm to check intermediate tiles
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        if dx == 0 and dy == 0:
            return True

        x, y = x1, y1
        x_inc = 1 if x1 < x2 else -1
        y_inc = 1 if y1 < y2 else -1

        if dx > dy:
            error = dx / 2
            while x != x2:
                tile = world.get_tile(x, y)
                if tile and not tile.can_pass():
                    return False

                error -= dy
                if error < 0:
                    y += y_inc
                    error += dx
                x += x_inc
        else:
            error = dy / 2
            while y != y2:
                tile = world.get_tile(x, y)
                if tile and not tile.can_pass():
                    return False

                error -= dx
                if error < 0:
                    x += x_inc
                    error += dy
                y += y_inc

        return True

    def _update_agent_memory(self, agent: Entity, world: World, visible_tiles: Set[Tuple[int, int]]) -> None:
        """Update agent's memory with currently visible information"""
        if agent.id not in self.agent_memory:
            self.agent_memory[agent.id] = {}

        current_tick = world.current_tick
        agent_memory = self.agent_memory[agent.id]

        for x, y in visible_tiles:
            tile = world.get_tile(x, y)
            if tile:
                agent_memory[(x, y)] = {
                    'terrain_type': tile.terrain_type,
                    'resources': [r.resource_type for r in tile.get_resources()],
                    'last_seen': current_tick,
                    'entities': []
                }

                # Add visible entities on this tile
                for entity in world.get_entities_at(x, y):
                    if entity.id != agent.id:
                        agent_memory[(x, y)]['entities'].append({
                            'id': entity.id,
                            'type': type(entity).__name__,
                            'name': entity.name,
                            'health': entity.stats.health,
                            'last_seen': current_tick
                        })

    def can_see_tile(self, agent_id: int, position: Tuple[int, int]) -> bool:
        """Check if an agent can currently see a specific tile"""
        if agent_id not in self.agent_vision:
            return False
        return position in self.agent_vision[agent_id]

    def can_see_entity(self, agent_id: int, entity: Entity) -> bool:
        """Check if an agent can currently see a specific entity"""
        return self.can_see_tile(agent_id, entity.position)

    def get_remembered_tile_info(self, agent_id: int, position: Tuple[int, int]) -> Optional[Dict]:
        """Get what an agent remembers about a tile"""
        if agent_id not in self.agent_memory:
            return None

        return self.agent_memory[agent_id].get(position)

    def get_known_tiles(self, agent_id: int) -> Set[Tuple[int, int]]:
        """Get all tiles that an agent has seen at some point"""
        if agent_id not in self.agent_memory:
            return set()

        return set(self.agent_memory[agent_id].keys())

    def get_visible_entities(self, agent_id: int, world: World) -> Dict[int, Entity]:
        """Get all entities currently visible to an agent"""
        visible_entities = {}

        if agent_id not in self.agent_vision:
            return visible_entities

        for position in self.agent_vision[agent_id]:
            for entity in world.get_entities_at(*position):
                if entity.id != agent_id:
                    visible_entities[entity.id] = entity

        return visible_entities

    def forget_old_memories(self, agent_id: int, current_tick: int) -> None:
        """Remove old memories that are beyond the memory duration"""
        if agent_id not in self.agent_memory:
            return

        agent_memory = self.agent_memory[agent_id]
        positions_to_forget = []

        for position, info in agent_memory.items():
            if current_tick - info['last_seen'] > self.memory_duration:
                positions_to_forget.append(position)

        for position in positions_to_forget:
            del agent_memory[position]

    def clear_agent_data(self, agent_id: int) -> None:
        """Clear all fog of war data for an agent (when they die, etc.)"""
        if agent_id in self.agent_vision:
            del self.agent_vision[agent_id]
        if agent_id in self.agent_memory:
            del self.agent_memory[agent_id]

    def get_pathfinding_grid(self, agent_id: int, world: World) -> list:
        """Get a pathfinding grid based on what the agent knows"""
        grid = []

        for y in range(self.world_height):
            row = []
            for x in range(self.world_width):
                # Default to blocked if unknown
                is_walkable = False

                # Check current vision
                if self.can_see_tile(agent_id, (x, y)):
                    tile = world.get_tile(x, y)
                    is_walkable = tile and tile.can_pass()
                else:
                    # Check memory
                    remembered = self.get_remembered_tile_info(agent_id, (x, y))
                    if remembered:
                        # Use remembered walkability based on terrain type
                        terrain = remembered['terrain_type']
                        is_walkable = terrain.value != 'water' and terrain.value != 'mountain'

                row.append(1 if is_walkable else 0)
            grid.append(row)

        return grid

    def get_exploration_targets(self, agent_id: int, agent_position: Tuple[int, int],
                              max_distance: int = 15) -> list[Tuple[int, int]]:
        """Get potential exploration targets (unknown or old tiles) near the agent"""
        targets = []
        known_tiles = self.get_known_tiles(agent_id)
        agent_x, agent_y = agent_position

        for dy in range(-max_distance, max_distance + 1):
            for dx in range(-max_distance, max_distance + 1):
                target_x = agent_x + dx
                target_y = agent_y + dy

                # Check bounds
                if not (0 <= target_x < self.world_width and 0 <= target_y < self.world_height):
                    continue

                position = (target_x, target_y)

                # Unknown tile
                if position not in known_tiles:
                    distance = math.sqrt(dx * dx + dy * dy)
                    targets.append((position, distance, 'unknown'))
                else:
                    # Old memory that might be worth revisiting
                    remembered = self.get_remembered_tile_info(agent_id, position)
                    if remembered and remembered.get('last_seen', 0) < len(known_tiles) - 50:
                        distance = math.sqrt(dx * dx + dy * dy)
                        targets.append((position, distance, 'old'))

        # Sort by distance, prioritize unknown over old
        targets.sort(key=lambda x: (0 if x[2] == 'unknown' else 1, x[1]))

        return [target[0] for target in targets[:10]]  # Return top 10 targets