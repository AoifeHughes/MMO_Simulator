"""
MMO-Compatible Action Nodes for Behavior Trees

These action nodes work with the new MMO architecture while maintaining
compatibility with existing behavior tree systems.
"""

import asyncio
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from shared.actions import ActionResult, ActionType
from world.tiles import TileType

from .base import ActionNode, ConditionNode, NodeStatus

logger = logging.getLogger(__name__)


class MMOFishingAction(ActionNode):
    """MMO-compatible fishing action that works with authoritative server"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("MMOFishingAction")
        self.max_distance = max_distance
        self.is_fishing = False
        self.fishing_start_time = 0.0
        self.target_water_pos: Optional[Tuple[int, int]] = None

    def start_action(self, agent) -> bool:
        """Start fishing action"""
        # Find nearby water
        water_pos = self._find_nearby_water(agent)
        if not water_pos:
            logger.debug(
                f"No water found within {self.max_distance} units for agent {agent.id[:8]}"
            )
            return False

        self.target_water_pos = water_pos
        self.is_fishing = True
        self.fishing_start_time = time.time()

        logger.info(
            f"🎣 MMO Fishing: Agent {agent.id[:8]} starting to fish at water tile {water_pos}"
        )
        return True

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update fishing action"""
        if not self.is_fishing or not self.target_water_pos:
            return NodeStatus.FAILURE

        # Check if we're still close enough to the water
        if not self._is_in_fishing_range(agent, self.target_water_pos):
            logger.warning(
                f"Agent {agent.id[:8]} moved too far from water during fishing"
            )
            return NodeStatus.FAILURE

        # Execute fishing action through MMO client
        if hasattr(agent, "mmo_client") and agent.mmo_client:
            # Use MMO client for fishing
            water_center_x = self.target_water_pos[0] + 0.5
            water_center_y = self.target_water_pos[1] + 0.5

            try:
                # Request fishing action
                future = asyncio.create_task(
                    agent.fish_at_location(water_center_x, water_center_y)
                )

                # For behavior tree compatibility, we need to handle this synchronously
                # In a real implementation, you might want to track this differently
                if future.done():
                    result = future.result()
                    if result and result.result == ActionResult.APPROVED:
                        logger.info(f"🎣 Fishing successful for agent {agent.id[:8]}")
                        return NodeStatus.SUCCESS
                    else:
                        logger.warning(
                            f"🎣 Fishing failed for agent {agent.id[:8]}: {result.message if result else 'Unknown error'}"
                        )
                        return NodeStatus.FAILURE

                return NodeStatus.RUNNING

            except Exception as e:
                logger.error(f"Error in MMO fishing action: {e}")
                return NodeStatus.FAILURE

        # Fallback for legacy action manager
        elif hasattr(agent, "action_manager") and agent.action_manager:
            water_center_x = self.target_water_pos[0] + 0.5
            water_center_y = self.target_water_pos[1] + 0.5

            asyncio.create_task(
                agent.action_manager.request_action(
                    ActionType.FISH,
                    {"target_x": water_center_x, "target_y": water_center_y},
                )
            )

            # Assume success for now (server will validate)
            logger.info(f"🎣 Sent fishing request for agent {agent.id[:8]}")
            return NodeStatus.SUCCESS

        return NodeStatus.FAILURE

    def stop_action(self, agent):
        """Stop fishing action"""
        self.is_fishing = False
        self.fishing_start_time = 0.0
        self.target_water_pos = None

    def _find_nearby_water(self, agent) -> Optional[Tuple[int, int]]:
        """Find nearby water tiles"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        agent_x, agent_y = agent.x, agent.y
        water_tiles = []
        search_radius = 5

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WATER:
                        water_center_x = check_x + 0.5
                        water_center_y = check_y + 0.5
                        real_distance = (
                            (water_center_x - agent_x) ** 2
                            + (water_center_y - agent_y) ** 2
                        ) ** 0.5

                        if real_distance <= self.max_distance:
                            water_tiles.append((check_x, check_y, real_distance))

        if not water_tiles:
            return None

        # Return closest water
        water_tiles.sort(key=lambda t: t[2])
        return (water_tiles[0][0], water_tiles[0][1])

    def _is_in_fishing_range(self, agent, water_pos: Tuple[int, int]) -> bool:
        """Check if agent is in fishing range of water"""
        water_x, water_y = water_pos
        water_center_x = water_x + 0.5
        water_center_y = water_y + 0.5

        distance = (
            (water_center_x - agent.x) ** 2 + (water_center_y - agent.y) ** 2
        ) ** 0.5
        return distance <= 1.2  # MMO fishing range

    def reset(self):
        """Reset the fishing state"""
        super().reset()
        self.is_fishing = False
        self.fishing_start_time = 0.0
        self.target_water_pos = None


class MMOHarvestWoodAction(ActionNode):
    """MMO-compatible wood harvesting action"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("MMOHarvestWoodAction")
        self.max_distance = max_distance
        self.is_harvesting = False
        self.harvest_start_time = 0.0
        self.target_wood_pos: Optional[Tuple[int, int]] = None

    def start_action(self, agent) -> bool:
        """Start wood harvesting action"""
        # Find nearby wood
        wood_pos = self._find_nearby_wood(agent)
        if not wood_pos:
            logger.debug(
                f"No wood found within {self.max_distance} units for agent {agent.id[:8]}"
            )
            return False

        self.target_wood_pos = wood_pos
        self.is_harvesting = True
        self.harvest_start_time = time.time()

        logger.info(
            f"🌲 MMO Wood Harvesting: Agent {agent.id[:8]} starting to harvest at wood tile {wood_pos}"
        )
        return True

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update wood harvesting action"""
        if not self.is_harvesting or not self.target_wood_pos:
            return NodeStatus.FAILURE

        # Check if we're still close enough to the wood
        if not self._is_in_harvest_range(agent, self.target_wood_pos):
            logger.warning(
                f"Agent {agent.id[:8]} moved too far from wood during harvesting"
            )
            return NodeStatus.FAILURE

        # Execute harvesting action through MMO client
        if hasattr(agent, "mmo_client") and agent.mmo_client:
            wood_center_x = self.target_wood_pos[0] + 0.5
            wood_center_y = self.target_wood_pos[1] + 0.5

            try:
                future = asyncio.create_task(
                    agent.harvest_wood_at_location(wood_center_x, wood_center_y)
                )

                if future.done():
                    result = future.result()
                    if result and result.result == ActionResult.APPROVED:
                        logger.info(
                            f"🌲 Wood harvesting successful for agent {agent.id[:8]}"
                        )
                        return NodeStatus.SUCCESS
                    else:
                        logger.warning(
                            f"🌲 Wood harvesting failed for agent {agent.id[:8]}: {result.message if result else 'Unknown error'}"
                        )
                        return NodeStatus.FAILURE

                return NodeStatus.RUNNING

            except Exception as e:
                logger.error(f"Error in MMO wood harvesting action: {e}")
                return NodeStatus.FAILURE

        # Fallback for legacy action manager
        elif hasattr(agent, "action_manager") and agent.action_manager:
            wood_center_x = self.target_wood_pos[0] + 0.5
            wood_center_y = self.target_wood_pos[1] + 0.5

            asyncio.create_task(
                agent.action_manager.request_action(
                    ActionType.HARVEST_WOOD,
                    {"target_x": wood_center_x, "target_y": wood_center_y},
                )
            )

            logger.info(f"🌲 Sent wood harvesting request for agent {agent.id[:8]}")
            return NodeStatus.SUCCESS

        return NodeStatus.FAILURE

    def stop_action(self, agent):
        """Stop harvesting action"""
        self.is_harvesting = False
        self.harvest_start_time = 0.0
        self.target_wood_pos = None

    def _find_nearby_wood(self, agent) -> Optional[Tuple[int, int]]:
        """Find nearby wood tiles"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        agent_x, agent_y = agent.x, agent.y
        wood_tiles = []
        search_radius = 5

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WOOD:
                        wood_center_x = check_x + 0.5
                        wood_center_y = check_y + 0.5
                        real_distance = (
                            (wood_center_x - agent_x) ** 2
                            + (wood_center_y - agent_y) ** 2
                        ) ** 0.5

                        if real_distance <= self.max_distance:
                            wood_tiles.append((check_x, check_y, real_distance))

        if not wood_tiles:
            return None

        # Return closest wood
        wood_tiles.sort(key=lambda t: t[2])
        return (wood_tiles[0][0], wood_tiles[0][1])

    def _is_in_harvest_range(self, agent, wood_pos: Tuple[int, int]) -> bool:
        """Check if agent is in harvesting range of wood"""
        wood_x, wood_y = wood_pos
        wood_center_x = wood_x + 0.5
        wood_center_y = wood_y + 0.5

        distance = (
            (wood_center_x - agent.x) ** 2 + (wood_center_y - agent.y) ** 2
        ) ** 0.5
        return distance <= 1.2  # MMO harvesting range

    def reset(self):
        """Reset the harvesting state"""
        super().reset()
        self.is_harvesting = False
        self.harvest_start_time = 0.0
        self.target_wood_pos = None


class MMOMoveToPosition(ActionNode):
    """MMO-compatible movement action"""

    def __init__(
        self,
        target_x: float,
        target_y: float,
        speed: float = 1.0,
        threshold: float = 0.5,
    ):
        super().__init__("MMOMoveToPosition")
        self.target_x = target_x
        self.target_y = target_y
        self.speed = speed
        self.threshold = threshold
        self.moving = False

    def start_action(self, agent) -> bool:
        """Start movement"""
        # Check if already at target
        distance = (
            (self.target_x - agent.x) ** 2 + (self.target_y - agent.y) ** 2
        ) ** 0.5
        if distance <= self.threshold:
            return True  # Already there

        # Request movement through MMO client
        if hasattr(agent, "mmo_client") and agent.mmo_client:
            asyncio.create_task(
                agent.mmo_client.move_to(self.target_x, self.target_y, self.speed)
            )
            self.moving = True
            logger.debug(
                f"Requested MMO movement to ({self.target_x:.2f}, {self.target_y:.2f}) for agent {agent.id[:8]}"
            )
            return True

        elif hasattr(agent, "action_manager") and agent.action_manager:
            asyncio.create_task(
                agent.action_manager.move_to(self.target_x, self.target_y, self.speed)
            )
            self.moving = True
            return True

        return False

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update movement"""
        if not self.moving:
            return NodeStatus.FAILURE

        # Check if we've reached the target
        distance = (
            (self.target_x - agent.x) ** 2 + (self.target_y - agent.y) ** 2
        ) ** 0.5

        if distance <= self.threshold:
            logger.debug(
                f"Agent {agent.id[:8]} reached target ({self.target_x:.2f}, {self.target_y:.2f})"
            )
            return NodeStatus.SUCCESS

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        """Stop movement"""
        self.moving = False

    def update_target(self, target_x: float, target_y: float):
        """Update movement target"""
        self.target_x = target_x
        self.target_y = target_y

    def reset(self):
        """Reset movement state"""
        super().reset()
        self.moving = False


# Condition nodes for MMO compatibility
class MMOWaterNearby(ConditionNode):
    """Check if water is nearby using MMO-compatible agent map"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("MMOWaterNearby")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if water is nearby"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return False

        agent_x, agent_y = agent.x, agent.y
        search_radius = 5

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WATER:
                        water_center_x = check_x + 0.5
                        water_center_y = check_y + 0.5
                        real_distance = (
                            (water_center_x - agent_x) ** 2
                            + (water_center_y - agent_y) ** 2
                        ) ** 0.5

                        if real_distance <= self.max_distance:
                            return True

        return False


class MMOWoodNearby(ConditionNode):
    """Check if wood is nearby using MMO-compatible agent map"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("MMOWoodNearby")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if wood is nearby"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return False

        agent_x, agent_y = agent.x, agent.y
        search_radius = 5

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent.x) + dx
                check_y = int(agent.y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WOOD:
                        wood_center_x = check_x + 0.5
                        wood_center_y = check_y + 0.5
                        real_distance = (
                            (wood_center_x - agent_x) ** 2
                            + (wood_center_y - agent_y) ** 2
                        ) ** 0.5

                        if real_distance <= self.max_distance:
                            return True

        return False


class MMOHasFishingRod(ConditionNode):
    """Check if agent has fishing rod in MMO system"""

    def __init__(self):
        super().__init__("MMOHasFishingRod")

    def check_condition(self, agent) -> bool:
        """Check if agent has fishing rod"""
        # For now, assume explorer agents have fishing rods
        # In a full implementation, this would check the actual inventory
        return agent.agent_type == "explorer"
