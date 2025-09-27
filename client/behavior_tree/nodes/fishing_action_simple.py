"""
Simplified OOP-Based Fishing Action Implementation

This module provides fishing actions using clean OOP inheritance while maintaining
compatibility with the existing synchronous behavior tree system.
"""

import logging
from typing import Any, Dict

from shared.action_constants import DISTANCES
from shared.actions import ActionType
from world.tiles import TileType

from .base import ActionNode, ConditionNode, NodeStatus

logger = logging.getLogger(__name__)


class FishingRodRequirement(ConditionNode):
    """Condition node checking if agent has a fishing rod"""

    def __init__(self):
        super().__init__("FishingRodRequirement")

    def check_condition(self, agent) -> bool:
        """Check if agent has fishing rod"""
        has_rod = agent.agent_type == "explorer"
        logger.info(
            f"🎣 FishingRod check: Agent {agent.id[:8]} type '{agent.agent_type}' has rod: {has_rod}"
        )
        return has_rod


class WaterNearbyCondition(ConditionNode):
    """Server-improved water detection condition with better logging"""

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.FISHING_RANGE
        super().__init__("WaterNearbyCondition")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check for nearby water using local agent map with better logging"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            logger.debug(f"WaterNearby: Agent {agent.id[:8]} has no agent_map")
            return False

        agent_x, agent_y = agent.x, agent.y
        search_radius = int(self.max_distance) + 1

        # Count known tiles to check if we have sufficient terrain data
        known_tiles_count = 0
        water_found = False
        closest_distance = float("inf")

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent_x) + dx
                check_y = int(agent_y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    known_tiles_count += 1
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WATER:
                        # Calculate real distance to water tile center
                        water_center_x = check_x + 0.5
                        water_center_y = check_y + 0.5
                        real_distance = (
                            (water_center_x - agent_x) ** 2
                            + (water_center_y - agent_y) ** 2
                        ) ** 0.5

                        if real_distance <= self.max_distance:
                            water_found = True
                            if real_distance < closest_distance:
                                closest_distance = real_distance

        # If we have insufficient terrain data, don't attempt fishing to prevent position issues
        total_search_tiles = (2 * search_radius + 1) ** 2
        terrain_coverage = known_tiles_count / total_search_tiles

        if terrain_coverage < 0.3:  # Need at least 30% terrain coverage
            logger.debug(
                f"🎣 WaterNearby: Agent {agent.id[:8]} insufficient terrain data ({terrain_coverage:.1%} coverage), deferring fishing"
            )
            return False

        # Only log 'inf' if we have sufficient terrain data but no water found
        if closest_distance == float("inf"):
            closest_distance_log = "none found"
        else:
            closest_distance_log = f"{closest_distance:.2f}"

        logger.info(
            f"🎣 WaterNearby: Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) water within {self.max_distance}: {water_found} (closest: {closest_distance_log}, terrain: {terrain_coverage:.1%})"
        )
        return water_found


class FishingAction(ActionNode):
    """Simplified fishing action that works with existing behavior tree system"""

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.FISHING_RANGE
        super().__init__("FishingAction")
        self.max_distance = max_distance
        self.is_fishing = False
        self.fishing_start_time = 0.0

    def start_action(self, agent) -> bool:
        """Start the fishing action"""
        if not self._can_start_fishing(agent):
            return False

        self.is_fishing = True
        import time

        self.fishing_start_time = time.time()
        logger.info(f"🎣 Agent {agent.id[:8]} started fishing")

        # Send fishing action to server via existing mechanism
        self._send_fishing_action(agent)
        return True

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        """Update the fishing action"""
        if not self.is_fishing:
            return NodeStatus.FAILURE

        # Continue fishing (let server handle the actual fishing logic)
        import time

        elapsed = time.time() - self.fishing_start_time

        # Timeout after 10 seconds
        if elapsed > 10.0:
            self.is_fishing = False
            logger.info(f"🎣 Agent {agent.id[:8]} finished fishing (timeout)")
            return NodeStatus.SUCCESS

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        """Stop the fishing action"""
        if self.is_fishing:
            self.is_fishing = False
            logger.info(f"🎣 Agent {agent.id[:8]} stopped fishing")

    def execute(self, agent, delta_time: float) -> NodeStatus:
        """Execute fishing action (required by BehaviorNode)"""
        if not self.is_running:
            # Try to start the action
            if self.start_action(agent):
                self.is_running = True
                return NodeStatus.RUNNING
            else:
                return NodeStatus.FAILURE
        else:
            # Update the running action
            status = self.update_action(agent, delta_time)
            if status != NodeStatus.RUNNING:
                self.is_running = False
                self.stop_action(agent)
            return status

    def _can_start_fishing(self, agent) -> bool:
        """Check if agent can start fishing"""
        # Check fishing rod
        has_rod = agent.agent_type == "explorer"
        if not has_rod:
            logger.warning(f"🎣 Agent {agent.id[:8]} has no fishing rod")
            return False

        # Check water nearby
        water_condition = WaterNearbyCondition(self.max_distance)
        if not water_condition.check_condition(agent):
            logger.warning(f"🎣 Agent {agent.id[:8]} no water within range")
            return False

        return True

    def _send_fishing_action(self, agent):
        """Send fishing action to server using existing action manager"""
        if hasattr(agent, "action_manager") and agent.action_manager:
            import asyncio

            try:
                # Find nearest water tile
                water_pos = self._find_nearest_water(agent)
                if water_pos:
                    fish_params = {"target_x": water_pos[0], "target_y": water_pos[1]}
                    asyncio.create_task(
                        agent.action_manager.request_action(
                            ActionType.FISH, fish_params
                        )
                    )
                    logger.debug(
                        f"🎣 Agent {agent.id[:8]} sent fishing request to server"
                    )
            except Exception as e:
                logger.error(f"🎣 Failed to send fishing action for {agent.id[:8]}: {e}")

    def _find_nearest_water(self, agent) -> tuple:
        """Find nearest water tile"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        agent_x, agent_y = agent.x, agent.y
        search_radius = int(self.max_distance) + 1
        closest_water = None
        closest_distance = float("inf")
        known_tiles_count = 0

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent_x) + dx
                check_y = int(agent_y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    known_tiles_count += 1
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WATER:
                        water_center_x = check_x + 0.5
                        water_center_y = check_y + 0.5
                        distance = (
                            (water_center_x - agent_x) ** 2
                            + (water_center_y - agent_y) ** 2
                        ) ** 0.5

                        if (
                            distance <= self.max_distance
                            and distance < closest_distance
                        ):
                            closest_distance = distance
                            closest_water = (water_center_x, water_center_y)

        # Check if we have sufficient terrain coverage before returning water
        total_search_tiles = (2 * search_radius + 1) ** 2
        terrain_coverage = known_tiles_count / total_search_tiles

        if terrain_coverage < 0.3:  # Need at least 30% terrain coverage
            return None

        return closest_water

    def reset(self):
        """Reset fishing action state"""
        super().reset()
        self.is_fishing = False
        self.fishing_start_time = 0.0


# Backward compatibility aliases
class HasFishingRod(FishingRodRequirement):
    """Backward compatibility alias"""

    pass


class WaterNearby(WaterNearbyCondition):
    """Backward compatibility alias"""

    pass


class FishAtWater(FishingAction):
    """Backward compatibility alias"""

    pass
