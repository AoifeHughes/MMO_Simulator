"""
Fishing action node for behavior trees.
"""

import logging
import time
import math
from typing import Any, Dict, List, Optional, Tuple

from shared.actions import ActionRequest, ActionType, fish_params
from world.tiles import TileType

from .base import ActionNode, ConditionNode, NodeStatus
from .action import MoveToTargetWithPathfinding
from .two_phase_action import ResourceActionNode

try:
    from debug_tracker import track_resource_event, track_agent_position
except ImportError:
    # Fallback if debug tracker is not available
    def track_resource_event(*args, **kwargs): pass
    def track_agent_position(*args, **kwargs): pass

logger = logging.getLogger(__name__)


class FishAtWater(ResourceActionNode):
    """Action node that makes the agent fish at nearby water using two-phase positioning"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("FishAtWater", TileType.WATER, max_distance)

    def execute_action(self, agent, target_pos: Tuple[float, float]) -> bool:
        """Execute the fishing action at the confirmed position"""
        # Check if agent has fishing rod
        if not self._has_fishing_rod(agent):
            logger.debug(f"FishAtWater: Agent {agent.id[:8]} has no fishing rod")
            return False

        # Send fishing request to server
        self._request_fishing(agent, target_pos[0], target_pos[1])

        logger.info(f"🎣 Agent {agent.id[:8]} executing fishing at ({target_pos[0]:.2f}, {target_pos[1]:.2f})")
        print(f"🎣 Agent {agent.id[:8]} fishing at validated position - distance should be ≤1.0")

        return True

    def get_action_name(self) -> str:
        return "fishing"

    def get_resource_type(self) -> str:
        return "water"

    def should_complete_action(self, agent, elapsed_time: float) -> bool:
        """Complete fishing after reasonable time"""
        return elapsed_time >= 4.0  # Fish for 4 seconds

    def _has_fishing_rod(self, agent) -> bool:
        """Check if agent has a fishing rod"""
        # This would check the agent's inventory
        # For now, assume explorer agents have fishing rods
        return agent.agent_type == "explorer"

    def _find_nearby_water(self, agent) -> Optional[tuple]:
        """Find nearby water tiles - returns the absolutely closest water tile"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            return None

        # Use agent's exact position for more accurate distance calculations
        agent_x, agent_y = agent.x, agent.y

        # Search in a larger radius to find all possible water tiles
        water_tiles = []
        search_radius = 5  # Search up to 5 tiles away

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                # Check if position is known and is water
                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WATER:
                        # Calculate real distance to water tile center
                        water_center_x = check_x + 0.5
                        water_center_y = check_y + 0.5

                        real_distance = ((water_center_x - agent_x) ** 2 + (water_center_y - agent_y) ** 2) ** 0.5

                        # Only include water within our max distance
                        if real_distance <= self.max_distance:
                            water_tiles.append((check_x, check_y, real_distance, water_center_x, water_center_y))

        if not water_tiles:
            logger.debug(f"Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) found NO water tiles within {self.max_distance} units")
            return None

        # Sort by actual distance and return the closest
        water_tiles.sort(key=lambda t: (t[2], t[0], t[1]))  # Sort by real distance, then by tile coordinates
        closest_water = water_tiles[0]

        logger.info(f"Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) found {len(water_tiles)} water tiles, chose tile ({closest_water[0]}, {closest_water[1]}) at real distance {closest_water[2]:.2f}")

        # Track water discovery for debugging
        track_resource_event(agent.id, "discovered", "water",
                           (closest_water[0], closest_water[1]), (agent_x, agent_y), "find_nearby_water")

        # Log all nearby water for debugging
        for i, (wx, wy, dist, cx, cy) in enumerate(water_tiles[:5]):  # Show top 5
            logger.debug(f"  Water option {i+1}: tile ({wx}, {wy}) center ({cx:.1f}, {cy:.1f}) distance {dist:.2f}")

        return (closest_water[0], closest_water[1])

    def _request_fishing(self, agent, x: float, y: float):
        """Request fishing action from the server"""
        if hasattr(agent, 'action_manager') and agent.action_manager:
            import asyncio
            asyncio.create_task(agent.action_manager.request_action(
                action_type=ActionType.FISH,
                parameters=fish_params(x, y)
            ))
        else:
            # Fallback for legacy system
            if hasattr(agent, 'client') and agent.client:
                import asyncio
                asyncio.create_task(agent.client.request_action(ActionType.FISH, fish_params(x, y)))

    def reset(self):
        """Reset the fishing state"""
        super().reset()
        self.is_fishing = False
        self.fishing_start_time = 0


class MoveToFishingSpot(ActionNode):
    """Action node that finds the nearest water and moves to a fishing position"""

    def __init__(self, rod_range: float = 1.2):
        super().__init__("MoveToFishingSpot")
        self.rod_range = rod_range
        self.target_water_pos: Optional[Tuple[int, int]] = None
        self.fishing_position: Optional[Tuple[float, float]] = None
        self.move_action: Optional[MoveToTargetWithPathfinding] = None

    def start_action(self, agent) -> bool:
        """Start moving to fishing spot"""
        # Find the nearest water tile
        self.target_water_pos = self._find_nearest_water(agent)
        if not self.target_water_pos:
            return False

        # Calculate optimal fishing position near the water
        self.fishing_position = self._calculate_fishing_position(agent, self.target_water_pos)
        if not self.fishing_position:
            return False

        # Start pathfinding to the fishing position
        self.move_action = MoveToTargetWithPathfinding(
            self.fishing_position[0],
            self.fishing_position[1],
            threshold=0.5
        )

        return self.move_action.start_action(agent)

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update movement to fishing spot"""
        if not self.move_action:
            return NodeStatus.FAILURE

        status = self.move_action.update_action(agent, dt)

        if status == NodeStatus.SUCCESS:
            # Check if we're in range to fish at the target water
            if self.target_water_pos and self._is_in_fishing_range(agent, self.target_water_pos):
                return NodeStatus.SUCCESS
            else:
                # Try to find a better fishing position
                self.fishing_position = self._calculate_fishing_position(agent, self.target_water_pos)
                if self.fishing_position:
                    self.move_action.update_target(self.fishing_position[0], self.fishing_position[1])
                    return NodeStatus.RUNNING
                else:
                    return NodeStatus.FAILURE

        return status

    def stop_action(self, agent):
        """Stop movement action"""
        if self.move_action:
            self.move_action.stop_action(agent)

    def _find_nearest_water(self, agent) -> Optional[Tuple[int, int]]:
        """Find the nearest discovered water tile"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            return None

        agent_x, agent_y = int(agent.x), int(agent.y)
        nearest_water = None
        nearest_distance = float('inf')

        # Search in expanding squares around the agent
        for radius in range(1, 50):  # Search up to 50 tiles away
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    # Only check the perimeter of the current radius to optimize
                    if abs(dx) != radius and abs(dy) != radius:
                        continue

                    check_x = agent_x + dx
                    check_y = agent_y + dy

                    # Check if position is known and is water
                    if agent.agent_map.is_tile_known(check_x, check_y):
                        tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                        if tile_type == TileType.WATER:
                            distance = dx * dx + dy * dy
                            if distance < nearest_distance:
                                nearest_distance = distance
                                nearest_water = (check_x, check_y)

            # If we found water at this radius, return it (closest water found)
            if nearest_water:
                return nearest_water

        return nearest_water

    def _calculate_fishing_position(self, agent, water_pos: Tuple[int, int]) -> Optional[Tuple[float, float]]:
        """Calculate the best position to fish from near the water"""
        water_x, water_y = water_pos

        # Try positions around the water tile within fishing rod range
        best_position = None
        best_score = -1

        for angle in range(0, 360, 30):  # Check 12 positions around the water
            rad = math.radians(angle)

            # Place position at fishing rod range from water center
            fish_x = water_x + 0.5 + math.cos(rad) * (self.rod_range - 0.5)
            fish_y = water_y + 0.5 + math.sin(rad) * (self.rod_range - 0.5)

            # Check if this position is valid (not in water, not in mountains)
            if self._is_valid_fishing_position(agent, fish_x, fish_y):
                # Score based on distance from agent (prefer closer positions)
                distance_score = 1.0 / (1.0 + math.sqrt((fish_x - agent.x)**2 + (fish_y - agent.y)**2))

                if distance_score > best_score:
                    best_score = distance_score
                    best_position = (fish_x, fish_y)

        return best_position

    def _is_valid_fishing_position(self, agent, x: float, y: float) -> bool:
        """Check if a position is valid for fishing (not in water or impassable terrain)"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            return True  # Assume valid if no map

        tile_x, tile_y = int(x), int(y)

        if not agent.agent_map.is_tile_known(tile_x, tile_y):
            return True  # Assume valid if unknown

        tile_type = agent.agent_map.get_tile_type(tile_x, tile_y)

        # Valid if it's not water and not impassable terrain
        return tile_type not in [TileType.WATER, TileType.WALL, TileType.LAVA]

    def _is_in_fishing_range(self, agent, water_pos: Tuple[int, int]) -> bool:
        """Check if agent is close enough to fish at the water position"""
        water_x, water_y = water_pos

        # Distance from agent to center of water tile
        dx = (water_x + 0.5) - agent.x
        dy = (water_y + 0.5) - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        return distance <= self.rod_range

    def reset(self):
        """Reset the fishing movement state"""
        super().reset()
        self.target_water_pos = None
        self.fishing_position = None
        if self.move_action:
            self.move_action.reset()


class HasFishingRod(ConditionNode):
    """Condition node that checks if agent has a fishing rod"""

    def __init__(self):
        super().__init__("HasFishingRod")

    def check_condition(self, agent) -> bool:
        """Check if agent has fishing rod"""
        # Check inventory for fishing rod
        # For now, assume explorer agents have fishing rods
        result = agent.agent_type == "explorer"
        logger.info(f"🎣 HasFishingRod: Agent {agent.id[:8]} type '{agent.agent_type}' has rod: {result}")
        return result


class WaterNearby(ConditionNode):
    """Condition node that checks if water is nearby"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("WaterNearby")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if water is nearby and discovered - uses exact same logic as FishAtWater"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            logger.debug(f"WaterNearby: Agent {agent.id[:8]} has no agent_map")
            return False

        # Use exact same logic as _find_nearby_water for consistency
        agent_x, agent_y = agent.x, agent.y
        search_radius = 5  # Same as FishAtWater

        water_found = False
        closest_distance = float('inf')

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                # Check if position is known and is water
                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WATER:
                        # Calculate real distance to water tile center
                        water_center_x = check_x + 0.5
                        water_center_y = check_y + 0.5
                        real_distance = ((water_center_x - agent_x) ** 2 + (water_center_y - agent_y) ** 2) ** 0.5

                        if real_distance <= self.max_distance:
                            water_found = True
                            if real_distance < closest_distance:
                                closest_distance = real_distance

        result = water_found
        logger.info(f"🎣 WaterNearby: Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) water within {self.max_distance}: {result} (closest: {closest_distance:.2f})")
        return result


class WaterDiscoveredButNotNearby(ConditionNode):
    """Condition node that checks if water has been discovered but is not immediately nearby"""

    def __init__(self, nearby_distance: float = 1.2):
        super().__init__("WaterDiscoveredButNotNearby")
        self.nearby_distance = nearby_distance

    def check_condition(self, agent) -> bool:
        """Check if water is discovered but not nearby (requiring movement to reach)"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            return False

        agent_x, agent_y = int(agent.x), int(agent.y)

        # First check if there's water nearby
        water_nearby = False
        water_discovered = False

        # Search in expanding squares
        for radius in range(1, 50):  # Search up to 50 tiles
            found_at_radius = False
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    # Only check perimeter for efficiency
                    if abs(dx) != radius and abs(dy) != radius:
                        continue

                    check_x = agent_x + dx
                    check_y = agent_y + dy

                    if agent.agent_map.is_tile_known(check_x, check_y):
                        tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                        if tile_type == TileType.WATER:
                            distance = (dx * dx + dy * dy) ** 0.5
                            if distance <= self.nearby_distance:
                                water_nearby = True
                            water_discovered = True
                            found_at_radius = True

            # If we found water at this radius and already checked nearby, we can decide
            if found_at_radius and radius > self.nearby_distance:
                break

        # Return true only if water is discovered but none is nearby
        return water_discovered and not water_nearby