"""
MMO Architecture Adapter for Behavior Trees

This module provides an adapter layer that allows existing behavior trees
to work with the new MMO client architecture while maintaining compatibility.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from client.mmo_client import MMOClientAdapter
from shared.actions import ActionType, ActionResult
from shared.actions import fish_params, harvest_wood_params, move_to_params

logger = logging.getLogger(__name__)


class BehaviorTreeMMOAgent:
    """
    Agent wrapper that provides behavior tree compatibility with MMO architecture.

    This class acts as a bridge between the existing behavior tree system
    and the new MMO client, maintaining the same interface while using
    the new backend.
    """

    def __init__(self, agent_id: str = None):
        self.id = agent_id  # Will be set after connection
        self.mmo_client = MMOClientAdapter()
        self.connected = False

        # Agent state for behavior tree compatibility
        self._agent_map = None
        self.agent_type = "explorer"  # Default type

        # Position tracking
        self._x = 0.0
        self._y = 0.0
        self._rotation = 0.0

        # Action manager compatibility
        self.action_manager = self

    async def connect(self, agent_type: str = "explorer") -> bool:
        """Connect to MMO server"""
        self.agent_type = agent_type
        success = await self.mmo_client.connect(agent_type)

        if success:
            self.connected = True
            self.id = self.mmo_client.get_agent_id()
            self._update_position_from_client()
            logger.info(f"BehaviorTree agent {self.id} connected as {agent_type}")

        return success

    async def disconnect(self):
        """Disconnect from server"""
        await self.mmo_client.disconnect()
        self.connected = False

    async def update(self):
        """Update agent state - called by behavior tree systems"""
        if not self.connected:
            return

        # Update position from client state
        self._update_position_from_client()

        # Small delay to prevent overwhelming the system
        await asyncio.sleep(0.016)  # ~60 FPS

    def _update_position_from_client(self):
        """Update internal position from MMO client state"""
        pos = self.mmo_client.get_agent_position()
        self._x = pos[0]
        self._y = pos[1]
        self._rotation = self.mmo_client.state.rotation

    @property
    def x(self) -> float:
        """Get current X position"""
        return self._x

    @property
    def y(self) -> float:
        """Get current Y position"""
        return self._y

    @property
    def rotation(self) -> float:
        """Get current rotation"""
        return self._rotation

    @property
    def position(self) -> tuple:
        """Get current position as tuple"""
        return (self._x, self._y)

    @property
    def client(self):
        """Provide client compatibility for legacy systems"""
        return self

    @property
    def agent_map(self):
        """Agent map compatibility - could be enhanced later"""
        return self._agent_map

    async def request_action(self, action_type: ActionType, parameters: Dict[str, Any]):
        """Request action through MMO client"""
        if not self.connected:
            logger.warning(f"Cannot request action {action_type}, not connected")
            return

        try:
            response = await self.mmo_client.request_action(action_type, parameters)

            if response.result == ActionResult.APPROVED:
                logger.debug(f"Action {action_type} approved: {response.message}")
            else:
                logger.warning(f"Action {action_type} failed: {response.message}")

            return response

        except Exception as e:
            logger.error(f"Error requesting action {action_type}: {e}")

    async def move_to_position(self, target_x: float, target_y: float, speed: float = 1.0):
        """Move to target position through MMO client"""
        await self.mmo_client.move_to(target_x, target_y, speed)

    # Action-specific methods for behavior tree compatibility
    async def fish_at_location(self, target_x: float, target_y: float):
        """Fish at specific location"""
        return await self.request_action(ActionType.FISH, fish_params(target_x, target_y))

    async def harvest_wood_at_location(self, target_x: float, target_y: float):
        """Harvest wood at specific location"""
        return await self.request_action(ActionType.HARVEST_WOOD, harvest_wood_params(target_x, target_y))

    def get_world_state(self) -> Dict[str, Any]:
        """Get world state for behavior tree compatibility"""
        return self.mmo_client.get_world_state()


class MMOActionManager:
    """
    Action manager that works with the MMO architecture.

    Provides the same interface as the original action manager but
    routes through the new MMO client system.
    """

    def __init__(self, mmo_agent: BehaviorTreeMMOAgent):
        self.mmo_agent = mmo_agent

    async def request_action(self, action_type: ActionType, parameters: Dict[str, Any]):
        """Request action through MMO system"""
        return await self.mmo_agent.request_action(action_type, parameters)

    async def move_to(self, target_x: float, target_y: float, speed: float = 1.0):
        """Move to target position"""
        await self.mmo_agent.move_to_position(target_x, target_y, speed)

    async def fish(self, target_x: float = None, target_y: float = None):
        """Fish action"""
        params = {}
        if target_x is not None and target_y is not None:
            params = fish_params(target_x, target_y)
        return await self.request_action(ActionType.FISH, params)

    async def harvest_wood(self, target_x: float, target_y: float):
        """Harvest wood action"""
        return await self.request_action(ActionType.HARVEST_WOOD, harvest_wood_params(target_x, target_y))


def create_mmo_behavior_tree_agent(agent_type: str = "explorer") -> BehaviorTreeMMOAgent:
    """
    Factory function to create a behavior tree compatible agent
    that uses the MMO architecture.
    """
    agent = BehaviorTreeMMOAgent()
    agent.agent_type = agent_type

    # Set up action manager
    agent.action_manager = MMOActionManager(agent)

    return agent


async def connect_behavior_tree_agent(agent_type: str = "explorer") -> Optional[BehaviorTreeMMOAgent]:
    """
    Create and connect a behavior tree agent to the MMO server.

    Returns None if connection fails.
    """
    agent = create_mmo_behavior_tree_agent(agent_type)

    try:
        success = await agent.connect(agent_type)
        if success:
            return agent
        else:
            logger.error(f"Failed to connect behavior tree agent as {agent_type}")
            return None
    except Exception as e:
        logger.error(f"Error connecting behavior tree agent: {e}")
        return None


class MMOAgentMap:
    """
    Simple agent map implementation for behavior tree compatibility.

    This provides basic map functionality that behavior trees expect.
    Could be enhanced with actual map data from the server in the future.
    """

    def __init__(self, width: int = 100, height: int = 100):
        self.width = width
        self.height = height
        self.known_tiles: Dict[tuple, str] = {}

    def is_tile_known(self, x: int, y: int) -> bool:
        """Check if tile is known"""
        return (x, y) in self.known_tiles

    def get_tile_type(self, x: int, y: int):
        """Get tile type"""
        return self.known_tiles.get((x, y), "unknown")

    def set_tile_type(self, x: int, y: int, tile_type):
        """Set tile type"""
        self.known_tiles[(x, y)] = tile_type

    def discover_tile(self, x: int, y: int, tile_type):
        """Discover a new tile"""
        self.set_tile_type(x, y, tile_type)


def setup_mmo_agent_with_map(agent: BehaviorTreeMMOAgent, world_width: int = 100, world_height: int = 100):
    """Set up an MMO agent with basic map functionality"""
    agent._agent_map = MMOAgentMap(world_width, world_height)
    return agent