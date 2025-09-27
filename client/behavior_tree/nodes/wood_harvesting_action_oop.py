"""
OOP-Based Wood Harvesting Action Implementation

This module provides wood harvesting actions using the new OOP hierarchy, replacing
the old monolithic wood_harvesting_action.py implementation with clean inheritance.

Classes:
- WoodHarvestingAction: Main wood harvesting action using server-authoritative positioning
- WoodNearbyCondition: Server-authoritative wood/forest detection
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


class WoodHarvestingAction(ResourceActionBase):
    """
    Modern wood harvesting action using OOP inheritance and server-authoritative positioning.

    This replaces the old HarvestWood class with:
    - Server-first environment queries
    - Clean OOP inheritance
    - Proper distance validation
    - Inventory management
    """

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.WOOD_HARVESTING_RANGE

        super().__init__(
            name="WoodHarvestingAction",
            resource_type=ResourceType.WOOD,
            target_tile_types={TileType.WOOD},
            max_action_distance=max_distance,
            required_tool="axe",
            action_duration_range=(2.0, 4.0),
            success_rate=0.9
        )

    def get_action_type(self) -> ActionType:
        """Get the ActionType for wood harvesting"""
        return ActionType.HARVEST_WOOD

    def get_result_item_name(self) -> str:
        """Get the name of the item produced by wood harvesting"""
        return "wood"

    def get_additional_parameters(self) -> Dict[str, Any]:
        """Get additional parameters for wood harvesting action"""
        return {
            'action_name': 'wood_harvesting',
            'tool_type': 'woodcutting'
        }

    def check_required_tools(self, agent, tool_type: str) -> bool:
        """Check if agent has required tools for wood harvesting"""
        if tool_type == "woodcutting":
            # Check for hatchet in agent's inventory
            hatchets = [item for item in agent.inventory.get_items_by_type("tool")
                        if hasattr(item, 'tool_type') and item.tool_type == "woodcutting"]
            return len(hatchets) > 0
        return super().check_required_tools(agent, tool_type)

    async def start_action(self, agent) -> bool:
        """Start wood harvesting with enhanced logging"""
        logger.info(f"🌲 Initiating wood harvesting action for agent {agent.id[:8]}")

        # Call parent implementation
        success = await super().start_action(agent)

        if success:
            logger.info(f"🌲 Agent {agent.id[:8]} started harvesting wood at {self.current_target['position']}")
            print(f"🌲 Agent {agent.id[:8]} chopping down trees...")
        else:
            logger.warning(f"🌲 Failed to start wood harvesting for agent {agent.id[:8]}")

        return success

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update wood harvesting action with progress logging"""
        if not self.is_executing:
            return NodeStatus.FAILURE

        import time
        elapsed_time = time.time() - self.action_start_time

        # Log harvesting progress occasionally
        if elapsed_time > 1.0 and int(elapsed_time) % 2 == 0:  # Every 2 seconds after first second
            logger.debug(f"🌲 Agent {agent.id[:8]} harvesting wood... ({elapsed_time:.1f}s elapsed)")

        return super().update_action(agent, dt)

    def stop_action(self, agent):
        """Stop wood harvesting with cleanup"""
        if self.is_executing:
            logger.info(f"🌲 Agent {agent.id[:8]} stopped harvesting wood")

        super().stop_action(agent)


class WoodNearbyCondition(ResourceConditionBase):
    """
    Server-authoritative wood/forest detection condition.

    This replaces the old WoodNearby class with server-first queries.
    """

    def __init__(self, max_distance: float = None):
        if max_distance is None:
            max_distance = DISTANCES.WOOD_HARVESTING_RANGE

        super().__init__(
            name="WoodNearbyCondition",
            resource_type=ResourceType.WOOD,
            max_distance=max_distance
        )

    def check_condition(self, agent) -> bool:
        """Check for nearby wood using fresh server data"""
        try:
            # Use synchronous fallback method since async isn't supported in behavior trees yet
            result = self._fallback_wood_check(agent)

            # Enhanced logging for wood harvesting
            if result:
                logger.info(f"🌲 Wood detected within {self.max_distance} units for agent {agent.id[:8]}")
            else:
                logger.info(f"🌲 No wood found within {self.max_distance} units for agent {agent.id[:8]}")

            return result

        except Exception as e:
            logger.error(f"Error in wood detection for agent {agent.id[:8]}: {e}")
            # Final fallback
            return False

    def _fallback_wood_check(self, agent) -> bool:
        """Fallback wood detection using local agent map"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            logger.debug(f"WoodNearby fallback: Agent {agent.id[:8]} has no agent_map")
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

        logger.info(f"🌲 WoodNearby fallback: Agent {agent.id[:8]} at ({agent_x:.2f}, {agent_y:.2f}) wood within {self.max_distance}: {wood_found} (closest: {closest_distance:.2f})")
        return wood_found


# For backward compatibility, provide aliases to the old names
# This allows existing behavior trees to work without modification

class WoodNearby(WoodNearbyCondition):
    """Backward compatibility alias"""
    pass


class HarvestWood(WoodHarvestingAction):
    """Backward compatibility alias"""
    pass


# Factory function for easy creation
def create_wood_harvesting_behavior_nodes(max_distance: float = None):
    """
    Factory function to create a complete set of wood harvesting behavior nodes.

    Returns:
        Dictionary of wood harvesting-related nodes
    """
    if max_distance is None:
        max_distance = DISTANCES.WOOD_HARVESTING_RANGE

    return {
        'wood_harvesting_action': WoodHarvestingAction(max_distance),
        'wood_nearby_check': WoodNearbyCondition(max_distance),
        'hatchet_check': HatchetRequirement(),

        # Backward compatibility
        'harvest_wood': HarvestWood(max_distance),
        'wood_nearby': WoodNearby(max_distance),
        'axe_check': AxeRequirement(),
    }


# Additional helper class for tool requirements
class ToolRequirement(ConditionNode):
    """
    Generic tool requirement checker.

    This can be used for any tool-based action requirement.
    """

    def __init__(self, tool_type: str, name: str = None):
        if name is None:
            name = f"{tool_type.title()}Requirement"
        super().__init__(name)
        self.tool_type = tool_type

    def check_condition(self, agent) -> bool:
        """Check if agent has the required tool"""
        # Check for the specific tool in agent's inventory
        if self.tool_type == "woodcutting":
            tools = [item for item in agent.inventory.get_items_by_type("tool")
                    if hasattr(item, 'tool_type') and item.tool_type == "woodcutting"]
            has_tool = len(tools) > 0
        elif self.tool_type == "fishing":
            tools = [item for item in agent.inventory.get_items_by_type("tool")
                    if hasattr(item, 'tool_type') and item.tool_type == "fishing"]
            has_tool = len(tools) > 0
        else:
            # For now, assume explorer agents have all other tools
            has_tool = agent.agent_type == "explorer"

        logger.info(f"🔧 Tool check: Agent {agent.id[:8]} type '{agent.agent_type}' has {self.tool_type}: {has_tool}")

        return has_tool


class HatchetRequirement(ToolRequirement):
    """Specific hatchet requirement for wood harvesting"""

    def __init__(self):
        super().__init__("woodcutting", "HatchetRequirement")


class AxeRequirement(ToolRequirement):
    """Backward compatibility alias for hatchet requirement"""

    def __init__(self):
        super().__init__("woodcutting", "AxeRequirement")