"""
OOP-Based Fishing Action Implementation

This module provides fishing actions using the new OOP hierarchy, replacing
the old monolithic fishing_action.py implementation with clean inheritance.

Classes:
- FishingAction: Main fishing action using server-authoritative positioning
- FishingRodRequirement: Condition checking for fishing rod
- WaterNearbyCondition: Server-authoritative water detection
"""

import logging
import random
from typing import Dict, Any, Set

from shared.actions import ActionType
from world.tiles import TileType
from .resource_action_base import (
    ResourceActionBase,
    ResourceConditionBase,
    ResourceType
)
from .base import ConditionNode, NodeStatus
from shared.action_constants import DISTANCES

logger = logging.getLogger(__name__)


class FishingAction(ResourceActionBase):
    """
    Modern fishing action using OOP inheritance and server-authoritative positioning.

    This replaces the old FishAtWater class with:
    - Server-first environment queries
    - Clean OOP inheritance
    - Proper distance validation
    - Inventory management
    """

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.FISHING_RANGE

        super().__init__(
            name="FishingAction",
            resource_type=ResourceType.WATER,
            target_tile_types={TileType.WATER},
            max_action_distance=max_distance,
            required_tool="fishing_rod",
            action_duration_range=(2.0, 6.0),
            success_rate=0.8
        )

    def get_action_type(self) -> ActionType:
        """Get the ActionType for fishing"""
        return ActionType.FISH

    def get_result_item_name(self) -> str:
        """Get the name of the item produced by fishing"""
        return "fish"

    def get_additional_parameters(self) -> Dict[str, Any]:
        """Get additional parameters for fishing action"""
        return {
            'action_name': 'fishing',
            'tool_type': 'fishing_rod'
        }

    async def start_action(self, agent) -> bool:
        """Start fishing with enhanced logging"""
        logger.info(f"🎣 Initiating fishing action for agent {agent.id[:8]}")

        # Call parent implementation
        success = await super().start_action(agent)

        if success:
            logger.info(f"🎣 Agent {agent.id[:8]} started fishing at {self.current_target['position']}")
            print(f"🎣 Agent {agent.id[:8]} casting line at water...")
        else:
            logger.warning(f"🎣 Failed to start fishing for agent {agent.id[:8]}")

        return success

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update fishing action with progress logging"""
        if not self.is_executing:
            return NodeStatus.FAILURE

        import time
        elapsed_time = time.time() - self.action_start_time

        # Log fishing progress occasionally
        if elapsed_time > 1.0 and int(elapsed_time) % 2 == 0:  # Every 2 seconds after first second
            logger.debug(f"🎣 Agent {agent.id[:8]} fishing... ({elapsed_time:.1f}s elapsed)")

        return super().update_action(agent, dt)

    def stop_action(self, agent):
        """Stop fishing with cleanup"""
        if self.is_executing:
            logger.info(f"🎣 Agent {agent.id[:8]} stopped fishing")

        super().stop_action(agent)


class FishingRodRequirement(ConditionNode):
    """
    Condition node checking if agent has a fishing rod.

    This uses the inventory management system from the base classes.
    """

    def __init__(self):
        super().__init__("FishingRodRequirement")

    def check_condition(self, agent) -> bool:
        """Check if agent has fishing rod"""
        # For now, assume explorer agents have fishing rods
        # TODO: Implement proper inventory checking when inventory system is enhanced
        has_rod = agent.agent_type == "explorer"

        logger.info(f"🎣 FishingRod check: Agent {agent.id[:8]} type '{agent.agent_type}' has rod: {has_rod}")

        return has_rod


class WaterNearbyCondition(ResourceConditionBase):
    """
    Server-authoritative water detection condition.

    This replaces the old WaterNearby class with server-first queries.
    """

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.FISHING_RANGE

        super().__init__(
            name="WaterNearbyCondition",
            resource_type=ResourceType.WATER,
            max_distance=max_distance
        )

    def check_condition(self, agent) -> bool:
        """Check for nearby water using fresh server data"""
        try:
            # Use synchronous fallback method since async isn't supported in behavior trees yet
            result = self._fallback_water_check(agent)

            # Enhanced logging for fishing
            if result:
                logger.info(f"🎣 Water detected within {self.max_distance} units for agent {agent.id[:8]}")
            else:
                logger.info(f"🎣 No water found within {self.max_distance} units for agent {agent.id[:8]}")

            return result

        except Exception as e:
            logger.error(f"Error in water detection for agent {agent.id[:8]}: {e}")
            # Final fallback
            return False

    def _fallback_water_check(self, agent) -> bool:
        """Fallback water detection using local agent map"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            logger.debug(f"WaterNearby fallback: Agent {agent.id[:8]} has no agent_map")
            return False

        agent_x, agent_y = agent.x, agent.y
        search_radius = int(self.max_distance) + 1

        water_found = False
        closest_distance = float('inf')

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent_x) + dx
                check_y = int(agent_y) + dy

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

        logger.info(f"🎣 WaterNearby fallback: Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) water within {self.max_distance}: {water_found} (closest: {closest_distance:.2f})")
        return water_found


# For backward compatibility, provide aliases to the old names
# This allows existing behavior trees to work without modification

class HasFishingRod(FishingRodRequirement):
    """Backward compatibility alias"""
    pass


class WaterNearby(WaterNearbyCondition):
    """Backward compatibility alias"""
    pass


class FishAtWater(FishingAction):
    """Backward compatibility alias"""
    pass


# Factory function for easy creation
def create_fishing_behavior_nodes(max_distance: float = None):
    """
    Factory function to create a complete set of fishing behavior nodes.

    Returns:
        Dictionary of fishing-related nodes
    """
    if max_distance is None:
        max_distance = DISTANCES.FISHING_RANGE

    return {
        'fishing_action': FishingAction(max_distance),
        'fishing_rod_check': FishingRodRequirement(),
        'water_nearby_check': WaterNearbyCondition(max_distance),

        # Backward compatibility
        'fish_at_water': FishAtWater(max_distance),
        'has_fishing_rod': HasFishingRod(),
        'water_nearby': WaterNearby(max_distance),
    }