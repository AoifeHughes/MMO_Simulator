"""
Tests for the crafting system implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from shared.actions import ActionType, create_craft_item_action
from shared.items import create_wood
from server.action_processor import ActionProcessor, ActionRequest, ActionContext
from server.agent_state import ServerAgentState
from server.database import DatabaseManager
from server.world_objects import WorldObjectManager, WorldObjectType


class TestCraftingSystem:
    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.world = Mock()
        server.world.world_objects = Mock(spec=WorldObjectManager)
        server.agent_registry = Mock()
        server.database_manager = AsyncMock(spec=DatabaseManager)
        return server

    @pytest.fixture
    def action_processor(self, mock_server):
        return ActionProcessor(mock_server)

    @pytest.fixture
    def agent_with_wood(self):
        """Create agent with sufficient wood for crafting"""
        agent = ServerAgentState("crafter1", "explorer", 15.0, 15.0)
        wood_item = create_wood()
        agent.inventory.add_item(wood_item, 5)  # 5 pieces of wood
        return agent

    @pytest.mark.asyncio
    async def test_craft_basic_fire_success(self, action_processor, mock_server, agent_with_wood):
        """Test successful basic fire crafting"""
        agent = agent_with_wood

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.world_objects.create_fire.return_value = "fire_123"

        # Create craft action for basic fire (requires 2 wood)
        action = create_craft_item_action("basic_fire")
        request = ActionRequest("crafter1", action)
        context = ActionContext()

        initial_wood_count = agent.inventory.get_item_count("Wood")

        response = await action_processor.execute_action(request, context)

        assert response.success
        assert "fire created" in response.message.lower()

        # Verify wood was consumed (2 pieces)
        assert agent.inventory.get_item_count("Wood") == initial_wood_count - 2

        # Verify fire was created in world
        mock_server.world.world_objects.create_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_craft_campfire_success(self, action_processor, mock_server, agent_with_wood):
        """Test successful campfire crafting"""
        agent = agent_with_wood

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.world_objects.create_fire.return_value = "campfire_456"

        # Create craft action for campfire (requires 4 wood)
        action = create_craft_item_action("campfire")
        request = ActionRequest("crafter1", action)
        context = ActionContext()

        initial_wood_count = agent.inventory.get_item_count("Wood")

        response = await action_processor.execute_action(request, context)

        assert response.success
        assert "campfire created" in response.message.lower()

        # Verify wood was consumed (4 pieces)
        assert agent.inventory.get_item_count("Wood") == initial_wood_count - 4

        # Verify campfire was created
        mock_server.world.world_objects.create_fire.assert_called_once()

    @pytest.mark.asyncio
    async def test_craft_insufficient_materials(self, action_processor, mock_server):
        """Test crafting failure due to insufficient materials"""
        # Agent with only 1 wood (needs 2 for basic fire)
        agent = ServerAgentState("crafter2", "explorer", 20.0, 20.0)
        wood_item = create_wood()
        agent.inventory.add_item(wood_item, 1)

        mock_server.agent_registry.get_agent.return_value = agent

        action = create_craft_item_action("basic_fire")
        request = ActionRequest("crafter2", action)
        context = ActionContext()

        response = await action_processor.execute_action(request, context)

        assert not response.success
        assert "insufficient materials" in response.message.lower()

        # Verify no wood was consumed
        assert agent.inventory.get_item_count("Wood") == 1

    @pytest.mark.asyncio
    async def test_craft_unknown_recipe(self, action_processor, mock_server, agent_with_wood):
        """Test crafting failure with unknown recipe"""
        agent = agent_with_wood

        mock_server.agent_registry.get_agent.return_value = agent

        action = create_craft_item_action("unknown_recipe")
        request = ActionRequest("crafter1", action)
        context = ActionContext()

        response = await action_processor.execute_action(request, context)

        assert not response.success
        assert "unknown recipe" in response.message.lower()

    @pytest.mark.asyncio
    async def test_database_craft_recording(self, action_processor, mock_server, agent_with_wood):
        """Test that crafting activities are recorded in database"""
        agent = agent_with_wood

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.world_objects.create_fire.return_value = "fire_789"

        action = create_craft_item_action("basic_fire")
        request = ActionRequest("crafter1", action)
        context = ActionContext()

        await action_processor.execute_action(request, context)

        # Verify database recording was called
        mock_server.database_manager.record_craft.assert_called_once()
        call_args = mock_server.database_manager.record_craft.call_args

        assert call_args[1]["agent_id"] == "crafter1"
        assert call_args[1]["recipe_name"] == "basic_fire"
        assert call_args[1]["result_item"] == "fire_789"
        assert len(call_args[1]["ingredients"]) == 1
        assert call_args[1]["ingredients"][0]["item_name"] == "Wood"
        assert call_args[1]["ingredients"][0]["quantity"] == 2

    @pytest.mark.asyncio
    async def test_craft_cooldown(self, action_processor, mock_server, agent_with_wood):
        """Test crafting cooldown prevents rapid crafting"""
        agent = agent_with_wood

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.world_objects.create_fire.return_value = "fire_cooldown"

        action = create_craft_item_action("basic_fire")
        request = ActionRequest("crafter1", action)
        context = ActionContext()

        # First craft should succeed
        response1 = await action_processor.execute_action(request, context)
        assert response1.success

        # Immediate second craft should fail due to cooldown
        response2 = await action_processor.execute_action(request, context)
        assert not response2.success
        assert "cooldown" in response2.message.lower()

    def test_recipe_requirements(self, action_processor):
        """Test that recipe requirements are correctly defined"""
        recipes = action_processor._get_crafting_recipes()

        # Basic fire recipe
        assert "basic_fire" in recipes
        basic_fire = recipes["basic_fire"]
        assert basic_fire["ingredients"] == [{"item_name": "Wood", "quantity": 2}]
        assert basic_fire["duration"] == 300.0  # 5 minutes
        assert basic_fire["object_type"] == WorldObjectType.FIRE

        # Campfire recipe
        assert "campfire" in recipes
        campfire = recipes["campfire"]
        assert campfire["ingredients"] == [{"item_name": "Wood", "quantity": 4}]
        assert campfire["duration"] == 600.0  # 10 minutes
        assert campfire["object_type"] == WorldObjectType.CAMPFIRE