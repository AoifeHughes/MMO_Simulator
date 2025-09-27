"""
OOP Base Classes for Resource Actions

This module provides a clean inheritance hierarchy for resource gathering actions
like fishing, wood harvesting, mining, etc. It eliminates code duplication and
provides a scalable foundation for new action types.

Architecture:
- ResourceActionBase: Core functionality for all resource actions
- DistanceValidatedAction: Mixin for actions requiring distance validation
- InventoryManagedAction: Mixin for actions that interact with inventory
- ServerQueryMixin: Mixin for actions that need fresh server data
"""

import logging
import time
import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import Enum

from shared.actions import ActionRequest, ActionType
from world.tiles import TileType
from .base import ActionNode, ConditionNode, NodeStatus
from shared.action_constants import DISTANCES, THRESHOLDS

try:
    from debug_tracker import track_resource_event, track_agent_position
except ImportError:
    def track_resource_event(*args, **kwargs): pass
    def track_agent_position(*args, **kwargs): pass

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources that can be gathered"""
    WATER = "water"
    WOOD = "wood"
    STONE = "stone"
    ORE = "ore"
    FOOD = "food"


class ActionValidationResult:
    """Result of validating whether an action can be performed"""

    def __init__(self, valid: bool, reason: str = "", suggested_position: Optional[Tuple[float, float]] = None):
        self.valid = valid
        self.reason = reason
        self.suggested_position = suggested_position


class ServerQueryMixin:
    """Mixin for actions that need fresh server data before execution"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_server_query_time = 0.0
        self.server_data_cache_duration = 1.0  # Cache server data for 1 second
        self.cached_server_data = {}

    async def get_fresh_position_data(self, agent) -> Optional[Tuple[float, float]]:
        """
        Get fresh position data from server for action validation.

        Returns:
            (x, y) position if available, None if server query fails
        """
        current_time = time.time()

        # Use cached data if recent enough
        if (current_time - self.last_server_query_time) < self.server_data_cache_duration:
            cached_pos = self.cached_server_data.get('position')
            if cached_pos:
                logger.debug(f"Using cached server position for {agent.id[:8]}: ({cached_pos[0]:.3f}, {cached_pos[1]:.3f})")
                return cached_pos

        # Query server for fresh position using new client query method
        if hasattr(agent, 'client') and agent.client:
            try:
                logger.debug(f"Querying server for fresh position data for {agent.id[:8]}")
                response_data = await agent.client.query_position(timeout=1.0)

                if response_data and response_data.get("success"):
                    position_data = response_data.get("position", {})
                    server_pos = (position_data.get("x"), position_data.get("y"))

                    if server_pos[0] is not None and server_pos[1] is not None:
                        self.last_server_query_time = current_time
                        self.cached_server_data['position'] = server_pos
                        logger.info(f"✅ Retrieved fresh server position for {agent.id[:8]}: ({server_pos[0]:.3f}, {server_pos[1]:.3f})")
                        return server_pos
                    else:
                        logger.warning(f"Invalid position data from server for {agent.id[:8]}")
                else:
                    logger.warning(f"Server position query failed for {agent.id[:8]}")

            except Exception as e:
                logger.error(f"Failed to query server position for {agent.id[:8]}: {e}")

        # Fallback to position authority system
        try:
            from shared.position_authority import get_server_position_for_action
            server_pos = get_server_position_for_action(agent.id)

            if server_pos:
                self.last_server_query_time = current_time
                self.cached_server_data['position'] = server_pos
                logger.debug(f"Retrieved position authority data for {agent.id[:8]}: ({server_pos[0]:.3f}, {server_pos[1]:.3f})")
                return server_pos

        except Exception as e:
            logger.debug(f"Position authority fallback failed for {agent.id[:8]}: {e}")

        # Final fallback to client position
        logger.warning(f"Using client position as final fallback for {agent.id[:8]}: ({agent.x:.3f}, {agent.y:.3f})")
        return (agent.x, agent.y)

    async def get_fresh_environment_data(self, agent, scan_radius: float = 5.0) -> Dict[str, Any]:
        """
        Get fresh environment data from server (resources, terrain, etc.)

        Args:
            agent: The agent requesting data
            scan_radius: Radius to scan around agent

        Returns:
            Dictionary containing environment data
        """
        current_time = time.time()
        cache_key = f'environment_{scan_radius}'

        # Use cached data if recent enough
        if (current_time - self.last_server_query_time) < self.server_data_cache_duration:
            cached_env = self.cached_server_data.get(cache_key)
            if cached_env:
                logger.debug(f"Using cached environment data for {agent.id[:8]}")
                return cached_env

        # Try server environment query first
        if hasattr(agent, 'client') and agent.client:
            try:
                logger.debug(f"Querying server for fresh environment data for {agent.id[:8]} (radius: {scan_radius})")
                response_data = await agent.client.query_environment(scan_radius=scan_radius, timeout=1.5)

                if response_data and response_data.get("success"):
                    env_data = {
                        'timestamp': current_time,
                        'agent_position': tuple(response_data.get("agent_position", [agent.x, agent.y])),
                        'visible_resources': response_data.get("resources", []),
                        'scan_radius': scan_radius,
                        'server_timestamp': response_data.get("server_timestamp", current_time)
                    }

                    self.cached_server_data[cache_key] = env_data
                    self.last_server_query_time = current_time

                    logger.info(f"✅ Retrieved fresh environment data for {agent.id[:8]}: {len(env_data['visible_resources'])} resources")
                    return env_data
                else:
                    logger.warning(f"Server environment query failed for {agent.id[:8]}")

            except Exception as e:
                logger.error(f"Failed to query server environment for {agent.id[:8]}: {e}")

        # Fallback to local scanning
        logger.debug(f"Using local environment scanning fallback for {agent.id[:8]}")
        env_data = {
            'timestamp': current_time,
            'agent_position': await self.get_fresh_position_data(agent),
            'visible_resources': self._scan_local_resources(agent, scan_radius),
            'scan_radius': scan_radius
        }

        self.cached_server_data[cache_key] = env_data
        self.last_server_query_time = current_time

        return env_data

    def _scan_local_resources(self, agent, scan_radius: float) -> List[Dict[str, Any]]:
        """Scan for resources using local agent map data"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            return []

        resources = []
        agent_x, agent_y = agent.x, agent.y
        search_radius = int(scan_radius)

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent_x) + dx
                check_y = int(agent_y) + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)

                    # Map tile types to resource types
                    resource_type = self._tile_to_resource_type(tile_type)
                    if resource_type:
                        tile_center_x = check_x + 0.5
                        tile_center_y = check_y + 0.5
                        distance = math.sqrt((tile_center_x - agent_x)**2 + (tile_center_y - agent_y)**2)

                        if distance <= scan_radius:
                            resources.append({
                                'type': resource_type.value,
                                'tile_type': tile_type.value,
                                'position': (tile_center_x, tile_center_y),
                                'tile_coordinates': (check_x, check_y),
                                'distance': distance
                            })

        return sorted(resources, key=lambda r: r['distance'])

    def _tile_to_resource_type(self, tile_type: TileType) -> Optional[ResourceType]:
        """Convert tile type to resource type"""
        mapping = {
            TileType.WATER: ResourceType.WATER,
            TileType.WOOD: ResourceType.WOOD,
            TileType.STONE: ResourceType.STONE,
        }
        return mapping.get(tile_type)


class DistanceValidatedAction:
    """Mixin for actions that require distance validation"""

    def __init__(self, max_action_distance: float, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_action_distance = max_action_distance
        self.validation_buffer = THRESHOLDS.VALIDATION_BUFFER

    def validate_distance(self, agent_pos: Tuple[float, float], target_pos: Tuple[float, float]) -> ActionValidationResult:
        """
        Validate if the agent is close enough to perform the action.

        Args:
            agent_pos: Current agent position (x, y)
            target_pos: Target position (x, y)

        Returns:
            ActionValidationResult with validation status and suggestions
        """
        dx = target_pos[0] - agent_pos[0]
        dy = target_pos[1] - agent_pos[1]
        distance = math.sqrt(dx * dx + dy * dy)

        # Check if within action range
        if distance <= self.max_action_distance + self.validation_buffer:
            return ActionValidationResult(
                valid=True,
                reason=f"Within action range: {distance:.2f} ≤ {self.max_action_distance:.2f}"
            )
        else:
            # Calculate suggested position
            if distance > 0:
                # Position agent slightly closer than max distance to ensure validation passes
                target_distance = self.max_action_distance * 0.9  # 10% safety margin
                factor = target_distance / distance
                suggested_x = target_pos[0] - dx * factor
                suggested_y = target_pos[1] - dy * factor
                suggested_position = (suggested_x, suggested_y)
            else:
                suggested_position = None

            return ActionValidationResult(
                valid=False,
                reason=f"Too far from target: {distance:.2f} > {self.max_action_distance:.2f}. Move closer.",
                suggested_position=suggested_position
            )

    def find_optimal_action_position(self, agent_pos: Tuple[float, float], target_pos: Tuple[float, float]) -> Tuple[float, float]:
        """
        Find the optimal position for the agent to perform the action.

        Args:
            agent_pos: Current agent position
            target_pos: Target resource position

        Returns:
            Optimal position (x, y) for the agent
        """
        dx = target_pos[0] - agent_pos[0]
        dy = target_pos[1] - agent_pos[1]
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 0.1:  # Agent is on top of target
            # Default to positioning east of target
            return (target_pos[0] + self.max_action_distance * 0.9, target_pos[1])

        # Position agent at optimal distance from target
        target_distance = self.max_action_distance * 0.9  # 10% safety margin
        factor = target_distance / distance

        optimal_x = target_pos[0] - dx * factor
        optimal_y = target_pos[1] - dy * factor

        return (optimal_x, optimal_y)


class InventoryManagedAction:
    """Mixin for actions that interact with inventory"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def check_inventory_space(self, agent, item_name: str, quantity: int = 1) -> bool:
        """
        Check if agent has inventory space for items.

        Args:
            agent: Agent to check inventory for
            item_name: Name of item to add
            quantity: Quantity of items to add

        Returns:
            True if agent has space, False otherwise
        """
        if not hasattr(agent, 'inventory'):
            return True  # Assume space if no inventory system

        try:
            # Check if inventory has space for the specified quantity
            available_space = agent.inventory.get_available_space()
            total_space_needed = quantity

            # If item is stackable, check if we can stack with existing items
            if hasattr(agent.inventory, 'can_stack_item'):
                existing_quantity = agent.inventory.get_item_count(item_name)
                if existing_quantity > 0 and agent.inventory.can_stack_item(item_name):
                    max_stack = getattr(agent.inventory, 'max_stack_size', 64)
                    space_in_existing_stacks = max_stack - (existing_quantity % max_stack)
                    if space_in_existing_stacks >= quantity:
                        return True  # Can fit in existing stacks
                    total_space_needed = quantity - space_in_existing_stacks

            return available_space >= total_space_needed

        except (AttributeError, TypeError):
            # Fallback for basic inventory systems
            if hasattr(agent.inventory, 'is_full'):
                return not agent.inventory.is_full()
            elif hasattr(agent.inventory, 'slots'):
                used_slots = len([slot for slot in agent.inventory.slots if slot is not None])
                total_slots = len(agent.inventory.slots)
                return used_slots < total_slots
            else:
                # No known inventory interface, assume space available
                return True

    def check_required_tools(self, agent, tool_type: str) -> bool:
        """
        Check if agent has required tools for the action.

        Args:
            agent: Agent to check tools for
            tool_type: Type of tool required (e.g., 'fishing_rod', 'axe')

        Returns:
            True if agent has the required tool, False otherwise
        """
        if not hasattr(agent, 'inventory'):
            # Fallback: assume tools are available based on agent type
            if tool_type == "fishing_rod":
                return agent.agent_type == "explorer"
            elif tool_type == "axe":
                return agent.agent_type == "explorer"
            return True

        try:
            # Check if tool is in inventory
            if hasattr(agent.inventory, 'has_item'):
                return agent.inventory.has_item(tool_type)

            # Check equipped tools if equipment system exists
            if hasattr(agent.inventory, 'get_equipped_item'):
                equipped_tool = agent.inventory.get_equipped_item('tool')
                if equipped_tool and equipped_tool.item_type == tool_type:
                    return True

            # Check all inventory slots for the tool
            if hasattr(agent.inventory, 'items'):
                for item in agent.inventory.items:
                    if item and hasattr(item, 'item_type') and item.item_type == tool_type:
                        return True
            elif hasattr(agent.inventory, 'slots'):
                for slot in agent.inventory.slots:
                    if slot and hasattr(slot, 'item') and slot.item:
                        if hasattr(slot.item, 'item_type') and slot.item.item_type == tool_type:
                            return True

            # Tool not found in inventory
            return False

        except (AttributeError, TypeError):
            # Fallback for basic systems - use agent type heuristics
            if tool_type == "fishing_rod":
                return agent.agent_type in ["explorer", "fisher"]
            elif tool_type == "axe":
                return agent.agent_type in ["explorer", "lumberjack"]
            elif tool_type == "pickaxe":
                return agent.agent_type in ["explorer", "miner"]
            return True  # Assume available for unknown tools

    def get_tool_efficiency(self, agent, tool_type: str) -> float:
        """
        Get efficiency multiplier based on equipped tools.

        Args:
            agent: Agent to check tools for
            tool_type: Type of tool to check efficiency for

        Returns:
            Efficiency multiplier (1.0 = normal, >1.0 = better, <1.0 = worse)
        """
        if not hasattr(agent, 'inventory'):
            return 1.0  # Default efficiency without inventory

        try:
            # Check for equipped tools with efficiency ratings
            if hasattr(agent.inventory, 'get_equipped_item'):
                equipped_tool = agent.inventory.get_equipped_item('tool')
                if equipped_tool and hasattr(equipped_tool, 'item_type') and equipped_tool.item_type == tool_type:
                    # Check for efficiency attribute
                    if hasattr(equipped_tool, 'efficiency'):
                        return equipped_tool.efficiency
                    elif hasattr(equipped_tool, 'quality'):
                        # Convert quality to efficiency (basic mapping)
                        quality_map = {
                            'poor': 0.8,
                            'common': 1.0,
                            'good': 1.2,
                            'excellent': 1.5,
                            'legendary': 2.0
                        }
                        return quality_map.get(equipped_tool.quality.lower(), 1.0)

            # Search inventory for best tool of this type
            best_efficiency = 1.0
            found_tool = False

            if hasattr(agent.inventory, 'items'):
                for item in agent.inventory.items:
                    if item and hasattr(item, 'item_type') and item.item_type == tool_type:
                        found_tool = True
                        efficiency = 1.0
                        if hasattr(item, 'efficiency'):
                            efficiency = item.efficiency
                        elif hasattr(item, 'quality'):
                            quality_map = {
                                'poor': 0.8,
                                'common': 1.0,
                                'good': 1.2,
                                'excellent': 1.5,
                                'legendary': 2.0
                            }
                            efficiency = quality_map.get(item.quality.lower(), 1.0)
                        best_efficiency = max(best_efficiency, efficiency)

            # Agent type efficiency modifiers
            if found_tool:
                agent_bonus = self._get_agent_type_efficiency_bonus(agent.agent_type, tool_type)
                return best_efficiency * agent_bonus
            else:
                # No tool found - check if agent type can work without tools
                return self._get_agent_type_efficiency_bonus(agent.agent_type, tool_type)

        except (AttributeError, TypeError):
            # Fallback to agent type efficiency
            return self._get_agent_type_efficiency_bonus(agent.agent_type, tool_type)

    def _get_agent_type_efficiency_bonus(self, agent_type: str, tool_type: str) -> float:
        """Get efficiency bonus based on agent type and tool type."""
        # Agent type specialization bonuses
        specializations = {
            "explorer": {
                "fishing_rod": 1.1,  # Explorers are versatile
                "axe": 1.1,
                "pickaxe": 1.1
            },
            "fisher": {
                "fishing_rod": 1.5,  # Fishers excel at fishing
                "axe": 0.8,
                "pickaxe": 0.8
            },
            "lumberjack": {
                "fishing_rod": 0.8,
                "axe": 1.5,  # Lumberjacks excel at woodcutting
                "pickaxe": 0.9
            },
            "miner": {
                "fishing_rod": 0.8,
                "axe": 0.9,
                "pickaxe": 1.5  # Miners excel at mining
            }
        }

        return specializations.get(agent_type, {}).get(tool_type, 1.0)


class ResourceActionBase(ServerQueryMixin, DistanceValidatedAction, InventoryManagedAction, ActionNode, ABC):
    """
    Base class for all resource gathering actions.

    This class provides the common infrastructure for resource actions like fishing,
    wood harvesting, mining, etc. It handles:
    - Server position queries
    - Distance validation
    - Inventory management
    - Action execution flow
    """

    def __init__(self,
                 name: str,
                 resource_type: ResourceType,
                 target_tile_types: Set[TileType],
                 max_action_distance: float,
                 required_tool: Optional[str] = None,
                 action_duration_range: Tuple[float, float] = (2.0, 5.0),
                 success_rate: float = 0.8):
        super().__init__(max_action_distance=max_action_distance)
        ActionNode.__init__(self, name)

        self.resource_type = resource_type
        self.target_tile_types = target_tile_types
        self.required_tool = required_tool
        self.action_duration_range = action_duration_range
        self.success_rate = success_rate

        # Action state
        self.current_target = None
        self.action_start_time = 0.0
        self.is_executing = False

    async def start_action(self, agent) -> bool:
        """Start the resource gathering action"""
        logger.info(f"🎯 Starting {self.resource_type.value} gathering for agent {agent.id[:8]}")

        # Check required tools
        if self.required_tool and not self.check_required_tools(agent, self.required_tool):
            logger.warning(f"Agent {agent.id[:8]} missing required tool: {self.required_tool}")
            return False

        # Get fresh server data
        try:
            agent_pos = await self.get_fresh_position_data(agent)
            env_data = await self.get_fresh_environment_data(agent)
        except Exception as e:
            logger.error(f"Failed to get server data for {agent.id[:8]}: {e}")
            return False

        if not agent_pos:
            logger.error(f"Could not determine agent position for {agent.id[:8]}")
            return False

        # Find suitable target
        target = self._find_best_target(agent_pos, env_data)
        if not target:
            logger.debug(f"No suitable {self.resource_type.value} target found for agent {agent.id[:8]}")
            return False

        self.current_target = target

        # Validate distance
        validation = self.validate_distance(agent_pos, target['position'])
        if not validation.valid:
            logger.debug(f"Distance validation failed for {agent.id[:8]}: {validation.reason}")
            # TODO: Implement movement to optimal position
            return False

        # Check inventory space
        if not self.check_inventory_space(agent, self.get_result_item_name()):
            logger.warning(f"Agent {agent.id[:8]} has no inventory space for {self.resource_type.value}")
            return False

        # Start action execution
        self.is_executing = True
        self.action_start_time = time.time()

        # Send action request to server
        await self._send_action_request(agent)

        # Track action start
        track_resource_event(agent.id, "start", self.resource_type.value,
                           target['position'], agent_pos, self.name)

        logger.info(f"✅ Started {self.resource_type.value} action for agent {agent.id[:8]} at {target['position']}")
        return True

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update the ongoing action"""
        if not self.is_executing:
            return NodeStatus.FAILURE

        elapsed_time = time.time() - self.action_start_time
        max_duration = self.action_duration_range[1]

        # Check for timeout
        if elapsed_time > max_duration:
            logger.info(f"⏰ {self.resource_type.value} action timed out for agent {agent.id[:8]}")
            self.is_executing = False
            return NodeStatus.SUCCESS  # Consider timeout as completion

        # Action is still in progress
        return NodeStatus.RUNNING

    def stop_action(self, agent):
        """Stop the current action"""
        if self.is_executing:
            logger.info(f"🛑 Stopping {self.resource_type.value} action for agent {agent.id[:8]}")
            self.is_executing = False

        # Stop agent movement if moving
        if hasattr(agent, 'stop_movement'):
            agent.stop_movement()

    def reset(self):
        """Reset action state"""
        super().reset()
        self.current_target = None
        self.action_start_time = 0.0
        self.is_executing = False
        self.cached_server_data.clear()

    def _find_best_target(self, agent_pos: Tuple[float, float], env_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find the best target for this resource action.

        Args:
            agent_pos: Current agent position
            env_data: Environment data from server query

        Returns:
            Target information dict or None if no suitable target
        """
        resources = env_data.get('visible_resources', [])

        # Filter for our resource type
        suitable_resources = [
            r for r in resources
            if r['type'] == self.resource_type.value and r['distance'] <= self.max_action_distance
        ]

        if not suitable_resources:
            return None

        # Return closest suitable resource
        return suitable_resources[0]  # Already sorted by distance

    async def _send_action_request(self, agent):
        """Send action request to server"""
        if not self.current_target:
            return

        # Get the action type for this resource
        action_type = self.get_action_type()

        # Prepare parameters
        parameters = {
            'target_x': self.current_target['position'][0],
            'target_y': self.current_target['position'][1],
        }

        # Add any action-specific parameters
        additional_params = self.get_additional_parameters()
        parameters.update(additional_params)

        # Send request via action manager
        if hasattr(agent, 'action_manager') and agent.action_manager:
            try:
                action_id = await agent.action_manager.request_action(
                    action_type=action_type,
                    parameters=parameters,
                    predict=False  # Don't predict resource actions
                )
                logger.debug(f"Sent {action_type.value} request for agent {agent.id[:8]}: {action_id}")
            except Exception as e:
                logger.error(f"Failed to send action request for {agent.id[:8]}: {e}")

    # Abstract methods that subclasses must implement

    @abstractmethod
    def get_action_type(self) -> ActionType:
        """Get the ActionType for this resource action"""
        pass

    @abstractmethod
    def get_result_item_name(self) -> str:
        """Get the name of the item produced by this action"""
        pass

    def get_additional_parameters(self) -> Dict[str, Any]:
        """Get additional parameters for the action request"""
        return {}


class ResourceConditionBase(ServerQueryMixin, ConditionNode, ABC):
    """
    Base class for conditions that check for nearby resources.

    This replaces the old WaterNearby, WoodNearby, etc. pattern with a unified
    server-authoritative approach.
    """

    def __init__(self,
                 name: str,
                 resource_type: ResourceType,
                 max_distance: float):
        ServerQueryMixin.__init__(self)
        ConditionNode.__init__(self, name)

        self.resource_type = resource_type
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if the resource is nearby using server data (synchronous fallback for now)"""
        try:
            # For now, use local scanning until we can implement async server queries properly
            resources = self._scan_local_resources(agent, self.max_distance)

            # Check for resources of our type
            suitable_resources = [
                r for r in resources
                if r['type'] == self.resource_type.value and r['distance'] <= self.max_distance
            ]

            found = len(suitable_resources) > 0
            closest_distance = suitable_resources[0]['distance'] if suitable_resources else float('inf')

            logger.info(f"🔍 {self.name}: Agent {agent.id[:8]} {self.resource_type.value} within {self.max_distance}: {found} (closest: {closest_distance:.2f})")

            return found

        except Exception as e:
            logger.error(f"Error checking {self.resource_type.value} condition for {agent.id[:8]}: {e}")
            return False