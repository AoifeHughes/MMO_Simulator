"""
Wood harvesting action nodes for behavior trees.
"""

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from shared.actions import ActionRequest, ActionType, harvest_wood_params
from world.tiles import TileType

from .action import MoveToTargetWithPathfinding
from .base import ActionNode, ConditionNode, NodeStatus
from .two_phase_action import ResourceActionNode

try:
    from debug_tracker import track_agent_position, track_resource_event
except ImportError:
    # Fallback if debug tracker is not available
    def track_resource_event(*args, **kwargs):
        pass

    def track_agent_position(*args, **kwargs):
        pass


logger = logging.getLogger(__name__)


class HarvestWood(ResourceActionNode):
    """Action node that makes the agent harvest wood using two-phase positioning"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("HarvestWood", TileType.WOOD, max_distance)

    def execute_action(self, agent, target_pos: Tuple[float, float]) -> bool:
        """Execute the wood harvesting action at the confirmed position"""
        # Send harvesting request to server
        self._request_wood_harvest(agent, target_pos[0], target_pos[1])

        logger.info(
            f"🌲 Agent {agent.id[:8]} executing wood harvesting at ({target_pos[0]:.2f}, {target_pos[1]:.2f})"
        )
        print(
            f"🌲 Agent {agent.id[:8]} harvesting wood at validated position - distance should be ≤1.0"
        )

        return True

    def get_action_name(self) -> str:
        return "wood_harvesting"

    def get_resource_type(self) -> str:
        return "wood"

    def should_complete_action(self, agent, elapsed_time: float) -> bool:
        """Complete harvesting after reasonable time"""
        return elapsed_time >= 3.0  # Harvest for 3 seconds

    def _find_nearby_wood(self, agent) -> Optional[tuple]:
        """Find nearby wood tiles - returns the absolutely closest wood tile"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        # Use agent's exact position for more accurate distance calculations
        agent_x, agent_y = agent.x, agent.y

        # Search in a larger radius to find all possible wood tiles
        wood_tiles = []
        search_radius = 5  # Search up to 5 tiles away

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                # Check if position is known and is wood
                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WOOD:
                        # Calculate real distance to wood tile center
                        wood_center_x = check_x + 0.5
                        wood_center_y = check_y + 0.5

                        real_distance = (
                            (wood_center_x - agent_x) ** 2
                            + (wood_center_y - agent_y) ** 2
                        ) ** 0.5

                        # Only include wood within our max distance
                        if real_distance <= self.max_distance:
                            wood_tiles.append(
                                (
                                    check_x,
                                    check_y,
                                    real_distance,
                                    wood_center_x,
                                    wood_center_y,
                                )
                            )

        if not wood_tiles:
            logger.debug(
                f"Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) found NO wood tiles within {self.max_distance} units"
            )
            return None

        # Sort by actual distance and return the closest
        wood_tiles.sort(
            key=lambda t: (t[2], t[0], t[1])
        )  # Sort by real distance, then by tile coordinates
        closest_wood = wood_tiles[0]

        logger.info(
            f"Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) found {len(wood_tiles)} wood tiles, chose tile ({closest_wood[0]}, {closest_wood[1]}) at real distance {closest_wood[2]:.2f}"
        )

        # Track wood discovery for debugging
        track_resource_event(
            agent.id,
            "discovered",
            "wood",
            (closest_wood[0], closest_wood[1]),
            (agent_x, agent_y),
            "find_nearby_wood",
        )

        # Log all nearby wood for debugging
        for i, (wx, wy, dist, cx, cy) in enumerate(wood_tiles[:5]):  # Show top 5
            logger.debug(
                f"  Wood option {i+1}: tile ({wx}, {wy}) center ({cx:.1f}, {cy:.1f}) distance {dist:.2f}"
            )

        return (closest_wood[0], closest_wood[1])

    def _request_wood_harvest(self, agent, x: float, y: float):
        """Request wood harvesting action from the server"""
        if hasattr(agent, "action_manager") and agent.action_manager:
            import asyncio

            asyncio.create_task(
                agent.action_manager.request_action(
                    action_type=ActionType.HARVEST_WOOD,
                    parameters=harvest_wood_params(x, y),
                )
            )
        else:
            # Fallback for legacy system
            if hasattr(agent, "client") and agent.client:
                import asyncio

                asyncio.create_task(
                    agent.client.request_action(
                        ActionType.HARVEST_WOOD, harvest_wood_params(x, y)
                    )
                )

    def reset(self):
        """Reset the harvesting state"""
        super().reset()
        self.is_harvesting = False
        self.harvest_start_time = 0


class MoveToWoodHarvestingSpot(ActionNode):
    """Action node that finds the nearest wood and moves to a harvesting position"""

    def __init__(self, harvest_range: float = 1.2):
        super().__init__("MoveToWoodHarvestingSpot")
        self.harvest_range = harvest_range
        self.target_wood_pos: Optional[Tuple[int, int]] = None
        self.harvesting_position: Optional[Tuple[float, float]] = None
        self.move_action: Optional[MoveToTargetWithPathfinding] = None

    def start_action(self, agent) -> bool:
        """Start moving to wood harvesting spot"""
        # Find the nearest wood tile
        self.target_wood_pos = self._find_nearest_wood(agent)
        if not self.target_wood_pos:
            return False

        # Calculate optimal harvesting position near the wood
        self.harvesting_position = self._calculate_harvesting_position(
            agent, self.target_wood_pos
        )
        if not self.harvesting_position:
            return False

        # Start pathfinding to the harvesting position
        self.move_action = MoveToTargetWithPathfinding(
            self.harvesting_position[0], self.harvesting_position[1], threshold=0.5
        )

        return self.move_action.start_action(agent)

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update movement to harvesting spot"""
        if not self.move_action:
            return NodeStatus.FAILURE

        status = self.move_action.update_action(agent, dt)

        if status == NodeStatus.SUCCESS:
            # Check if we're in range to harvest the target wood
            if self.target_wood_pos and self._is_in_harvesting_range(
                agent, self.target_wood_pos
            ):
                return NodeStatus.SUCCESS
            else:
                # Try to find a better harvesting position
                self.harvesting_position = self._calculate_harvesting_position(
                    agent, self.target_wood_pos
                )
                if self.harvesting_position:
                    self.move_action.update_target(
                        self.harvesting_position[0], self.harvesting_position[1]
                    )
                    return NodeStatus.RUNNING
                else:
                    return NodeStatus.FAILURE

        return status

    def stop_action(self, agent):
        """Stop movement action"""
        if self.move_action:
            self.move_action.stop_action(agent)

    def _find_nearest_wood(self, agent) -> Optional[Tuple[int, int]]:
        """Find the nearest discovered wood tile"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        agent_x, agent_y = int(agent.x), int(agent.y)
        nearest_wood = None
        nearest_distance = float("inf")

        # Search in expanding squares around the agent
        for radius in range(1, 50):  # Search up to 50 tiles away
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    # Only check the perimeter of the current radius to optimize
                    if abs(dx) != radius and abs(dy) != radius:
                        continue

                    check_x = agent_x + dx
                    check_y = agent_y + dy

                    # Check if position is known and is wood
                    if agent.agent_map.is_tile_known(check_x, check_y):
                        tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                        if tile_type == TileType.WOOD:
                            distance = dx * dx + dy * dy
                            if distance < nearest_distance:
                                nearest_distance = distance
                                nearest_wood = (check_x, check_y)

            # If we found wood at this radius, return it (closest wood found)
            if nearest_wood:
                return nearest_wood

        return nearest_wood

    def _calculate_harvesting_position(
        self, agent, wood_pos: Tuple[int, int]
    ) -> Optional[Tuple[float, float]]:
        """Calculate the best position to harvest from near the wood"""
        wood_x, wood_y = wood_pos

        # Try positions around the wood tile within harvesting range
        best_position = None
        best_score = -1

        for angle in range(0, 360, 30):  # Check 12 positions around the wood
            rad = math.radians(angle)

            # Place position at harvesting range from wood center
            harvest_x = wood_x + 0.5 + math.cos(rad) * (self.harvest_range - 0.5)
            harvest_y = wood_y + 0.5 + math.sin(rad) * (self.harvest_range - 0.5)

            # Check if this position is valid (not in water, not in mountains)
            if self._is_valid_harvesting_position(agent, harvest_x, harvest_y):
                # Score based on distance from agent (prefer closer positions)
                distance_score = 1.0 / (
                    1.0
                    + math.sqrt((harvest_x - agent.x) ** 2 + (harvest_y - agent.y) ** 2)
                )

                if distance_score > best_score:
                    best_score = distance_score
                    best_position = (harvest_x, harvest_y)

        return best_position

    def _is_valid_harvesting_position(self, agent, x: float, y: float) -> bool:
        """Check if a position is valid for harvesting (not in water or impassable terrain)"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return True  # Assume valid if no map

        tile_x, tile_y = int(x), int(y)

        if not agent.agent_map.is_tile_known(tile_x, tile_y):
            return True  # Assume valid if unknown

        tile_type = agent.agent_map.get_tile_type(tile_x, tile_y)

        # Valid if it's not water and not impassable terrain
        return tile_type not in [TileType.WATER, TileType.WALL, TileType.LAVA]

    def _is_in_harvesting_range(self, agent, wood_pos: Tuple[int, int]) -> bool:
        """Check if agent is close enough to harvest at the wood position"""
        wood_x, wood_y = wood_pos

        # Distance from agent to center of wood tile
        dx = (wood_x + 0.5) - agent.x
        dy = (wood_y + 0.5) - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        return distance <= self.harvest_range

    def reset(self):
        """Reset the harvesting movement state"""
        super().reset()
        self.target_wood_pos = None
        self.harvesting_position = None
        if self.move_action:
            self.move_action.reset()


class WoodNearby(ConditionNode):
    """Condition node that checks if wood is nearby"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("WoodNearby")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if wood is nearby and discovered"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            logger.debug(f"WoodNearby: Agent {agent.id[:8]} has no agent_map")
            return False

        # Use exact same logic as _find_nearby_wood for consistency
        agent_x, agent_y = agent.x, agent.y
        search_radius = 5  # Same as HarvestWood

        wood_found = False
        closest_distance = float("inf")

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                # Check if position is known and is wood
                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WOOD:
                        # Calculate real distance to wood tile center
                        wood_center_x = check_x + 0.5
                        wood_center_y = check_y + 0.5
                        real_distance = (
                            (wood_center_x - agent_x) ** 2
                            + (wood_center_y - agent_y) ** 2
                        ) ** 0.5

                        if real_distance <= self.max_distance:
                            wood_found = True
                            if real_distance < closest_distance:
                                closest_distance = real_distance

        result = wood_found
        logger.info(
            f"🌲 WoodNearby: Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) wood within {self.max_distance}: {result} (closest: {closest_distance:.2f})"
        )
        return result


class WoodDiscoveredButNotNearby(ConditionNode):
    """Condition node that checks if wood has been discovered but is not immediately nearby"""

    def __init__(self, nearby_distance: float = 1.2):
        super().__init__("WoodDiscoveredButNotNearby")
        self.nearby_distance = nearby_distance

    def check_condition(self, agent) -> bool:
        """Check if wood is discovered but not nearby (requiring movement to reach)"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return False

        agent_x, agent_y = int(agent.x), int(agent.y)

        # First check if there's wood nearby
        wood_nearby = False
        wood_discovered = False

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
                        if tile_type == TileType.WOOD:
                            distance = (dx * dx + dy * dy) ** 0.5
                            if distance <= self.nearby_distance:
                                wood_nearby = True
                            wood_discovered = True
                            found_at_radius = True

            # If we found wood at this radius and already checked nearby, we can decide
            if found_at_radius and radius > self.nearby_distance:
                break

        # Return true only if wood is discovered but none is nearby
        return wood_discovered and not wood_nearby
