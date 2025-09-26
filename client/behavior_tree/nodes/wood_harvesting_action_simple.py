"""
Simplified OOP-Based Wood Harvesting Action Implementation

This module provides wood harvesting actions using clean OOP inheritance while maintaining
compatibility with the existing synchronous behavior tree system.
"""

import logging
from typing import Dict, Any

from shared.actions import ActionType
from world.tiles import TileType
from .base import ConditionNode, ActionNode, NodeStatus
from shared.action_constants import DISTANCES

logger = logging.getLogger(__name__)


class WoodNearbyCondition(ConditionNode):
    """Server-improved wood detection condition with better logging"""

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.WOOD_HARVESTING_RANGE
        super().__init__("WoodNearbyCondition")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check for nearby wood using local agent map with better logging"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            logger.debug(f"WoodNearby: Agent {agent.id[:8]} has no agent_map")
            return False

        agent_x, agent_y = agent.x, agent.y
        search_radius = int(self.max_distance) + 1

        wood_found = False
        closest_distance = float('inf')

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent_x) + dx
                check_y = int(agent_y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WOOD:
                        # Calculate real distance to wood tile center
                        wood_center_x = check_x + 0.5
                        wood_center_y = check_y + 0.5
                        real_distance = ((wood_center_x - agent_x) ** 2 + (wood_center_y - agent_y) ** 2) ** 0.5

                        if real_distance <= self.max_distance:
                            wood_found = True
                            if real_distance < closest_distance:
                                closest_distance = real_distance

        logger.info(f"🌲 WoodNearby: Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) wood within {self.max_distance}: {wood_found} (closest: {closest_distance:.2f})")
        return wood_found


class WoodHarvestingAction(ActionNode):
    """Simplified wood harvesting action that works with existing behavior tree system"""

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.WOOD_HARVESTING_RANGE
        super().__init__("WoodHarvestingAction")
        self.max_distance = max_distance
        self.is_harvesting = False
        self.harvesting_start_time = 0.0

    def start_action(self, agent) -> bool:
        """Start the wood harvesting action"""
        if not self._can_start_harvesting(agent):
            return False

        self.is_harvesting = True
        import time
        self.harvesting_start_time = time.time()
        logger.info(f"🌲 Agent {agent.id[:8]} started harvesting wood")

        # Send harvesting action to server via existing mechanism
        self._send_harvesting_action(agent)
        return True

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        """Update the wood harvesting action"""
        if not self.is_harvesting:
            return NodeStatus.FAILURE

        # Continue harvesting (let server handle the actual harvesting logic)
        import time
        elapsed = time.time() - self.harvesting_start_time

        # Timeout after 10 seconds
        if elapsed > 10.0:
            self.is_harvesting = False
            logger.info(f"🌲 Agent {agent.id[:8]} finished harvesting (timeout)")
            return NodeStatus.SUCCESS

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        """Stop the wood harvesting action"""
        if self.is_harvesting:
            self.is_harvesting = False
            logger.info(f"🌲 Agent {agent.id[:8]} stopped harvesting")

    def execute(self, agent, delta_time: float) -> NodeStatus:
        """Execute wood harvesting action (required by BehaviorNode)"""
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

    def _can_start_harvesting(self, agent) -> bool:
        """Check if agent can start harvesting"""
        # Check wood nearby
        wood_condition = WoodNearbyCondition(self.max_distance)
        if not wood_condition.check_condition(agent):
            logger.warning(f"🌲 Agent {agent.id[:8]} no wood within range")
            return False

        return True

    def _send_harvesting_action(self, agent):
        """Send harvesting action to server using existing action manager"""
        if hasattr(agent, 'action_manager') and agent.action_manager:
            import asyncio
            try:
                # Find nearest wood tile
                wood_pos = self._find_nearest_wood(agent)
                if wood_pos:
                    harvest_params = {
                        'target_x': wood_pos[0],
                        'target_y': wood_pos[1]
                    }
                    asyncio.create_task(agent.action_manager.request_action(ActionType.HARVEST_WOOD, harvest_params))
                    logger.debug(f"🌲 Agent {agent.id[:8]} sent wood harvesting request to server")
            except Exception as e:
                logger.error(f"🌲 Failed to send harvesting action for {agent.id[:8]}: {e}")

    def _find_nearest_wood(self, agent) -> tuple:
        """Find nearest wood tile"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            return None

        agent_x, agent_y = agent.x, agent.y
        search_radius = int(self.max_distance) + 1
        closest_wood = None
        closest_distance = float('inf')

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent_x) + dx
                check_y = int(agent_y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.WOOD:
                        wood_center_x = check_x + 0.5
                        wood_center_y = check_y + 0.5
                        distance = ((wood_center_x - agent_x) ** 2 + (wood_center_y - agent_y) ** 2) ** 0.5

                        if distance <= self.max_distance and distance < closest_distance:
                            closest_distance = distance
                            closest_wood = (wood_center_x, wood_center_y)

        return closest_wood

    def reset(self):
        """Reset harvesting action state"""
        super().reset()
        self.is_harvesting = False
        self.harvesting_start_time = 0.0


# Backward compatibility aliases
class WoodNearby(WoodNearbyCondition):
    """Backward compatibility alias"""
    pass


class HarvestWood(WoodHarvestingAction):
    """Backward compatibility alias"""
    pass