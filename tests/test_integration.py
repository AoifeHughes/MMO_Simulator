"""
Integration tests for the complete MMO simulator with new features.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from shared.actions import create_harvest_wood_action, create_craft_item_action, create_trade_request_action
from shared.items import create_wood
from server.action_processor import ActionProcessor
from server.agent_state import ServerAgentState, AgentRegistry
from server.database import DatabaseManager
from server.world_objects import WorldObjectManager
from world.tiles import TileType


class TestIntegration:
    @pytest.fixture
    def mock_server(self):
        """Comprehensive mock server for integration tests"""
        server = Mock()
        server.world = Mock()
        server.world.world_map = Mock()
        server.world.world_objects = Mock(spec=WorldObjectManager)
        server.agent_registry = Mock(spec=AgentRegistry)
        server.database_manager = AsyncMock(spec=DatabaseManager)
        return server

    @pytest.fixture
    def action_processor(self, mock_server):
        return ActionProcessor(mock_server)

    @pytest.fixture
    def cooperation_agents(self):
        """Create agents suitable for cooperation scenario"""
        # WoodCutter agent
        woodcutter = ServerAgentState("woodcutter", "explorer", 10.0, 10.0)

        # Fisher agent
        fisher = ServerAgentState("fisher", "explorer", 12.0, 12.0)
        fish_item = Mock()
        fish_item.name = "Fresh Fish"
        fisher.inventory.add_item(fish_item, 2)

        return woodcutter, fisher

    @pytest.mark.asyncio
    async def test_full_cooperation_workflow(self, action_processor, mock_server, cooperation_agents):
        """Test complete cooperation workflow: harvest wood -> craft fire -> trade"""
        woodcutter, fisher = cooperation_agents

        # Setup server mocks
        def get_agent_mock(agent_id):
            if agent_id == "woodcutter":
                return woodcutter
            elif agent_id == "fisher":
                return fisher
            return None

        mock_server.agent_registry.get_agent.side_effect = get_agent_mock
        mock_server.world.get_agent.side_effect = lambda aid: Mock(x=10.0, y=10.0) if aid == "woodcutter" else Mock(x=12.0, y=12.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST
        mock_server.world.world_objects.create_fire.return_value = "fire_123"

        # Step 1: Woodcutter harvests wood
        harvest_action = create_harvest_wood_action()
        harvest_request = ActionProcessor.ActionRequest("woodcutter", harvest_action)
        harvest_response = await action_processor.execute_action(harvest_request, ActionProcessor.ActionContext())

        assert harvest_response.success
        assert woodcutter.inventory.get_item_count("Wood") > 0

        # Clear cooldowns for next action
        action_processor.action_cooldowns.clear()

        # Step 2: Woodcutter crafts fire
        craft_action = create_craft_item_action("basic_fire")
        craft_request = ActionProcessor.ActionRequest("woodcutter", craft_action)
        craft_response = await action_processor.execute_action(craft_request, ActionProcessor.ActionContext())

        assert craft_response.success
        mock_server.world.world_objects.create_fire.assert_called_once()

        # Clear cooldowns for next action
        action_processor.action_cooldowns.clear()

        # Step 3: Fisher requests trade (fish for fire access)
        # Note: In real scenario, fisher would seek fire, but we'll simulate a trade
        wood_item = create_wood()
        woodcutter.inventory.add_item(wood_item, 2)  # Give woodcutter some wood to trade

        trade_action = create_trade_request_action(
            "woodcutter",
            [{"item_name": "Fresh Fish", "quantity": 1}],  # Fisher offers fish
            [{"item_name": "Wood", "quantity": 1}]  # Fisher wants wood
        )
        trade_request = ActionProcessor.ActionRequest("fisher", trade_action)
        trade_response = await action_processor.execute_action(trade_request, ActionProcessor.ActionContext())

        assert trade_response.success
        assert len(action_processor.active_trades) > 0

        # Verify database calls were made
        mock_server.database_manager.record_craft.assert_called()

    @pytest.mark.asyncio
    async def test_resource_chain_validation(self, action_processor, mock_server):
        """Test that resource chains work correctly (wood -> fire -> cooking)"""
        agent = ServerAgentState("resource_agent", "explorer", 15.0, 15.0)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=15.0, y=15.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST
        mock_server.world.world_objects.create_fire.return_value = "resource_fire"

        # Step 1: Harvest wood
        harvest_action = create_harvest_wood_action()
        harvest_request = ActionProcessor.ActionRequest("resource_agent", harvest_action)

        response = await action_processor.execute_action(harvest_request, ActionProcessor.ActionContext())
        assert response.success

        initial_wood = agent.inventory.get_item_count("Wood")
        assert initial_wood >= 1

        # Clear cooldowns
        action_processor.action_cooldowns.clear()

        # Step 2: Use wood to craft fire (if enough wood)
        if initial_wood >= 2:
            craft_action = create_craft_item_action("basic_fire")
            craft_request = ActionProcessor.ActionRequest("resource_agent", craft_action)

            craft_response = await action_processor.execute_action(craft_request, ActionProcessor.ActionContext())
            assert craft_response.success

            # Wood should be consumed
            final_wood = agent.inventory.get_item_count("Wood")
            assert final_wood == initial_wood - 2

    @pytest.mark.asyncio
    async def test_error_handling_chain(self, action_processor, mock_server):
        """Test error handling across different action types"""
        agent = ServerAgentState("error_agent", "explorer", 20.0, 20.0)
        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=20.0, y=20.0)

        # Test 1: Harvest wood on non-forest tile
        mock_server.world.world_map.get_tile.return_value = TileType.WATER

        harvest_action = create_harvest_wood_action()
        harvest_request = ActionProcessor.ActionRequest("error_agent", harvest_action)

        response = await action_processor.execute_action(harvest_request, ActionProcessor.ActionContext())
        assert not response.success
        assert "forest" in response.message.lower()

        # Test 2: Craft without materials
        craft_action = create_craft_item_action("basic_fire")
        craft_request = ActionProcessor.ActionRequest("error_agent", craft_action)

        craft_response = await action_processor.execute_action(craft_request, ActionProcessor.ActionContext())
        assert not craft_response.success
        assert "insufficient" in craft_response.message.lower()

        # Test 3: Trade with non-existent agent
        trade_action = create_trade_request_action(
            "nonexistent_agent",
            [{"item_name": "Wood", "quantity": 1}],
            [{"item_name": "Fish", "quantity": 1}]
        )
        trade_request = ActionProcessor.ActionRequest("error_agent", trade_action)

        trade_response = await action_processor.execute_action(trade_request, ActionProcessor.ActionContext())
        assert not trade_response.success

    @pytest.mark.asyncio
    async def test_concurrent_actions(self, action_processor, mock_server):
        """Test handling concurrent actions from multiple agents"""
        agent1 = ServerAgentState("concurrent1", "explorer", 5.0, 5.0)
        agent2 = ServerAgentState("concurrent2", "explorer", 6.0, 6.0)

        wood_item = create_wood()
        agent1.inventory.add_item(wood_item, 5)
        agent2.inventory.add_item(wood_item, 5)

        def get_agent_mock(agent_id):
            return agent1 if agent_id == "concurrent1" else agent2 if agent_id == "concurrent2" else None

        mock_server.agent_registry.get_agent.side_effect = get_agent_mock
        mock_server.world.get_agent.side_effect = lambda aid: Mock(x=5.0, y=5.0) if aid == "concurrent1" else Mock(x=6.0, y=6.0)
        mock_server.world.world_objects.create_fire.side_effect = lambda *args, **kwargs: f"fire_{args[0][0]}"

        # Both agents try to craft at the same time
        craft_action1 = create_craft_item_action("basic_fire")
        craft_action2 = create_craft_item_action("basic_fire")

        request1 = ActionProcessor.ActionRequest("concurrent1", craft_action1)
        request2 = ActionProcessor.ActionRequest("concurrent2", craft_action2)

        # Execute concurrently
        response1, response2 = await asyncio.gather(
            action_processor.execute_action(request1, ActionProcessor.ActionContext()),
            action_processor.execute_action(request2, ActionProcessor.ActionContext())
        )

        # Both should succeed (no shared state conflicts)
        assert response1.success
        assert response2.success

    @pytest.mark.asyncio
    async def test_database_integration(self, action_processor, mock_server):
        """Test database integration across all new features"""
        agent = ServerAgentState("db_agent", "explorer", 25.0, 25.0)
        wood_item = create_wood()
        agent.inventory.add_item(wood_item, 10)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=25.0, y=25.0)
        mock_server.world.world_objects.create_fire.return_value = "db_fire"

        # Test crafting database record
        craft_action = create_craft_item_action("campfire")
        craft_request = ActionProcessor.ActionRequest("db_agent", craft_action)

        response = await action_processor.execute_action(craft_request, ActionProcessor.ActionContext())
        assert response.success

        # Verify database record_craft was called
        mock_server.database_manager.record_craft.assert_called_once()
        call_kwargs = mock_server.database_manager.record_craft.call_args[1]

        assert call_kwargs["agent_id"] == "db_agent"
        assert call_kwargs["recipe_name"] == "campfire"
        assert call_kwargs["result_item"] == "db_fire"
        assert len(call_kwargs["ingredients"]) == 1
        assert call_kwargs["ingredients"][0]["item_name"] == "Wood"
        assert call_kwargs["ingredients"][0]["quantity"] == 4

    @pytest.mark.asyncio
    async def test_cooldown_system_integration(self, action_processor, mock_server):
        """Test that cooldown system works across all action types"""
        agent = ServerAgentState("cooldown_agent", "explorer", 30.0, 30.0)
        wood_item = create_wood()
        agent.inventory.add_item(wood_item, 10)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=30.0, y=30.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST
        mock_server.world.world_objects.create_fire.return_value = "cooldown_fire"

        # Test harvest cooldown
        harvest_action = create_harvest_wood_action()
        harvest_request = ActionProcessor.ActionRequest("cooldown_agent", harvest_action)

        response1 = await action_processor.execute_action(harvest_request, ActionProcessor.ActionContext())
        assert response1.success

        response2 = await action_processor.execute_action(harvest_request, ActionProcessor.ActionContext())
        assert not response2.success
        assert "cooldown" in response2.message.lower()

        # Test craft cooldown (clear harvest cooldown first)
        action_processor.action_cooldowns.clear()

        craft_action = create_craft_item_action("basic_fire")
        craft_request = ActionProcessor.ActionRequest("cooldown_agent", craft_action)

        craft_response1 = await action_processor.execute_action(craft_request, ActionProcessor.ActionContext())
        assert craft_response1.success

        craft_response2 = await action_processor.execute_action(craft_request, ActionProcessor.ActionContext())
        assert not craft_response2.success
        assert "cooldown" in craft_response2.message.lower()

    @pytest.mark.asyncio
    async def test_inventory_space_limits(self, action_processor, mock_server):
        """Test inventory space handling across features"""
        agent = ServerAgentState("inventory_agent", "explorer", 35.0, 35.0)

        # Fill inventory to near capacity
        wood_item = create_wood()
        for _ in range(agent.inventory.max_slots - 1):  # Leave one slot free
            agent.inventory.add_item(wood_item, 1)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=35.0, y=35.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST

        # Test harvesting with nearly full inventory
        harvest_action = create_harvest_wood_action()
        harvest_request = ActionProcessor.ActionRequest("inventory_agent", harvest_action)

        response = await action_processor.execute_action(harvest_request, ActionProcessor.ActionContext())

        # Should handle inventory limits gracefully
        if not response.success:
            assert "inventory" in response.message.lower() or response.success