"""
OOP base class for action tests that provides clean test infrastructure.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import Dict, Any

from shared.actions import ActionType, ActionResult, ActionRequest, harvest_wood_params, craft_item_params
from shared.items import create_wood, create_item
from server.action_processor import ActionProcessor
from server.agent_state import ServerAgentState
from server.database import DatabaseManager
from world.tiles import TileType


class ActionTestBase:
    """
    OOP base class for action tests that provides clean helper methods
    and consistent ActionRequest construction patterns.
    """

    @pytest.fixture
    def mock_server(self):
        """Create a properly structured mock server"""
        server = Mock()
        server.world = Mock()
        server.world.world_map = Mock()
        server.world.world_map.width = 100  # Set proper numeric values
        server.world.world_map.height = 100
        server.world.world_objects = Mock()
        server.world.server = server  # Set up the circular reference that ActionProcessor expects
        server.agent_registry = Mock()
        server.database_manager = AsyncMock(spec=DatabaseManager)
        return server

    @pytest.fixture
    def action_processor(self, mock_server):
        """Create ActionProcessor with proper dependencies"""
        from server.attack_system import AttackSystem
        attack_system = Mock(spec=AttackSystem)
        processor = ActionProcessor(mock_server.world, mock_server.agent_registry, attack_system)
        # Set database manager reference if it exists
        if hasattr(processor, 'database_manager'):
            processor.database_manager = mock_server.database_manager
        return processor

    def create_harvest_request(self, agent_id: str, x: float = 5.0, y: float = 5.0) -> ActionRequest:
        """Create a proper wood harvesting ActionRequest using OOP principles"""
        return ActionRequest(
            agent_id=agent_id,
            action_type=ActionType.HARVEST_WOOD,
            parameters=harvest_wood_params(x, y)
        )

    def create_craft_request(self, agent_id: str, recipe: str, x: float = 50.0, y: float = 50.0) -> ActionRequest:
        """Create a proper crafting ActionRequest using OOP principles"""
        return ActionRequest(
            agent_id=agent_id,
            action_type=ActionType.CRAFT_ITEM,
            parameters=craft_item_params(recipe, x, y)
        )

    def create_agent_with_wood(self, agent_id: str, wood_count: int = 5) -> ServerAgentState:
        """Create an agent with wood items in inventory"""
        agent = ServerAgentState(agent_id, "explorer")
        agent.position = (50.0, 50.0)  # Explicitly set position
        agent.add_starting_items()

        # Add wood items using correct lowercase item name
        wood_item = create_item("wood")  # Use lowercase to match crafting system expectations
        if wood_item:
            wood_item.name = "wood"  # Force lowercase name to match crafting expectations
            for _ in range(wood_count):
                agent.inventory.add_item(wood_item, 1)

        return agent

    def create_agent_near_forest(self, agent_id: str) -> ServerAgentState:
        """Create an agent positioned near a forest tile"""
        agent = ServerAgentState(agent_id, "explorer")
        agent.position = (5.0, 5.0)  # Explicitly set position
        agent.add_starting_items()
        return agent

    def setup_harvest_mocks(self, mock_server, agent: ServerAgentState):
        """Setup mocks for successful wood harvesting"""
        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD

    def setup_craft_mocks(self, mock_server, agent: ServerAgentState, fire_id: str = "fire_123"):
        """Setup mocks for successful crafting"""
        from server.world_objects import WorldObjectType
        from unittest.mock import Mock

        mock_server.agent_registry.get_agent.return_value = agent

        # Create a proper mock fire object with object_type attribute
        mock_fire = Mock()
        mock_fire.object_type = WorldObjectType.FIRE
        mock_fire.object_id = fire_id
        mock_server.world.world_objects.create_fire.return_value = mock_fire

    def assert_approved(self, response):
        """Assert that action was approved using OOP assertion pattern"""
        assert response.result == ActionResult.APPROVED, f"Expected APPROVED but got {response.result}: {response.message}"

    def assert_rejected(self, response):
        """Assert that action was rejected using OOP assertion pattern"""
        assert response.result == ActionResult.REJECTED, f"Expected REJECTED but got {response.result}: {response.message}"

    def assert_error(self, response):
        """Assert that action resulted in error using OOP assertion pattern"""
        assert response.result == ActionResult.ERROR, f"Expected ERROR but got {response.result}: {response.message}"

    def get_wood_count(self, agent: ServerAgentState) -> int:
        """Get wood count from agent inventory using consistent method"""
        # Try both cases since there might be inconsistency
        wood_count = agent.inventory.get_item_quantity("wood")
        if wood_count == 0:
            wood_count = agent.inventory.get_item_quantity("Wood")
        return wood_count