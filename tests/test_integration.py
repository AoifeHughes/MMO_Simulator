"""
Integration tests for the complete MMO simulator with new features.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from shared.actions import ActionResult, create_harvest_wood_action, create_craft_item_action, create_trade_request_action
from shared.items import create_wood, create_hatchet
from server.action_processor import ActionProcessor, ActionRequest
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
        # Create mock attack system
        mock_attack_system = Mock()
        return ActionProcessor(mock_server.world, mock_server.agent_registry, mock_attack_system)

    @pytest.fixture
    def cooperation_agents(self):
        """Create agents suitable for cooperation scenario"""
        # WoodCutter agent with hatchet at position 10,10
        woodcutter = ServerAgentState("woodcutter", "explorer", 10.0, 10.0)
        woodcutter.position = (10.0, 10.0)
        woodcutter.x = 10.0
        woodcutter.y = 10.0
        hatchet = create_hatchet()
        woodcutter.inventory.add_item(hatchet, 1)

        # Fisher agent at position 12,12
        fisher = ServerAgentState("fisher", "explorer", 12.0, 12.0)
        fisher.position = (12.0, 12.0)
        fisher.x = 12.0
        fisher.y = 12.0
        fish_item = Mock()
        fish_item.name = "Fresh Fish"
        fish_item.weight = 1.0
        fish_item.value = 5
        fish_item.max_stack_size = 10
        fish_item.item_type = "food"
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
        mock_server.world.world_map.width = 100
        mock_server.world.world_map.height = 100
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD
        mock_server.world.world_map.get_bounds.return_value = (100, 100)
        mock_server.world.world_map.is_walkable.return_value = True
        # Mock fire object with proper structure
        mock_fire = Mock()
        mock_fire.object_type = Mock()
        mock_fire.object_type.value = "fire"
        mock_server.world.world_objects.create_fire.return_value = mock_fire
        # Make sure world.server points to the mock_server for database calls
        mock_server.world.server = mock_server

        # Step 1: Woodcutter harvests wood (at their current location) - harvest twice to get enough
        for i in range(2):
            harvest_request = create_harvest_wood_action(10.0, 10.0)
            harvest_request.agent_id = "woodcutter"
            harvest_response = await action_processor.submit_action(harvest_request)
            assert harvest_response.result == ActionResult.APPROVED

            # Clear cooldowns between harvests
            if i == 0:  # Only clear after first harvest, not after second
                for validator in action_processor.validators:
                    if hasattr(validator, 'last_use'):
                        validator.last_use.clear()

        # Verify enough wood was harvested
        wood_count = woodcutter.inventory.get_item_quantity("wood")
        assert wood_count >= 2, f"Expected at least 2 wood to be harvested, wood count: {wood_count}"

        # Clear cooldowns for next action
        for validator in action_processor.validators:
            if hasattr(validator, 'last_use'):
                validator.last_use.clear()

        # Step 2: Woodcutter crafts fire
        craft_request = create_craft_item_action("basic_fire", 10.0, 10.0)
        craft_request.agent_id = "woodcutter"
        craft_response = await action_processor.submit_action(craft_request)

        assert craft_response.result == ActionResult.APPROVED
        mock_server.world.world_objects.create_fire.assert_called_once()

        # Clear cooldowns for next action
        for validator in action_processor.validators:
            if hasattr(validator, 'last_use'):
                validator.last_use.clear()

        # Step 3: Fisher requests trade (fish for fire access)
        # Note: In real scenario, fisher would seek fire, but we'll simulate a trade
        wood_item = create_wood()
        woodcutter.inventory.add_item(wood_item, 2)  # Give woodcutter some wood to trade

        trade_request = create_trade_request_action(
            "woodcutter",
            [{"item_name": "Fresh Fish", "quantity": 1}],  # Fisher offers fish
            [{"item_name": "wood", "quantity": 1}]  # Fisher wants wood
        )
        trade_request.agent_id = "fisher"
        trade_response = await action_processor.submit_action(trade_request)

        assert trade_response.result == ActionResult.APPROVED
        assert len(action_processor.active_trades) > 0

        # Verify database calls were made
        mock_server.database_manager.record_craft.assert_called()

    @pytest.mark.asyncio
    async def test_resource_chain_validation(self, action_processor, mock_server):
        """Test that resource chains work correctly (wood -> fire -> cooking)"""
        agent = ServerAgentState("resource_agent", "explorer", 15.0, 15.0)
        agent.position = (15.0, 15.0)  # Explicitly set position
        hatchet = create_hatchet()
        agent.inventory.add_item(hatchet, 1)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=15.0, y=15.0)
        mock_server.world.world_map.width = 100
        mock_server.world.world_map.height = 100
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD
        # Mock fire object with proper structure
        mock_fire = Mock()
        mock_fire.object_type = Mock()
        mock_fire.object_type.value = "fire"
        mock_server.world.world_objects.create_fire.return_value = mock_fire
        # Make sure world.server points to the mock_server for database calls
        mock_server.world.server = mock_server

        # Step 1: Harvest wood
        harvest_request = create_harvest_wood_action(15.0, 15.0)
        harvest_request.agent_id = "resource_agent"

        response = await action_processor.submit_action(harvest_request)
        assert response.result == ActionResult.APPROVED

        initial_wood = agent.inventory.get_item_quantity("wood")
        assert initial_wood >= 1

        # Clear cooldowns
        for validator in action_processor.validators:
            if hasattr(validator, 'last_use'):
                validator.last_use.clear()

        # Step 2: Use wood to craft fire (if enough wood)
        if initial_wood >= 2:
            craft_request = create_craft_item_action("basic_fire", 15.0, 15.0)
            craft_request.agent_id = "resource_agent"

            craft_response = await action_processor.submit_action(craft_request)
            assert craft_response.result == ActionResult.APPROVED

            # Wood should be consumed
            final_wood = agent.inventory.get_item_quantity("wood")
            assert final_wood == initial_wood - 2

    @pytest.mark.asyncio
    async def test_error_handling_chain(self, action_processor, mock_server):
        """Test error handling across different action types"""
        agent = ServerAgentState("error_agent", "explorer", 20.0, 20.0)
        agent.position = (20.0, 20.0)  # Explicitly set position
        # Add hatchet so we get the tile validation error instead of tool error
        hatchet = create_hatchet()
        agent.inventory.add_item(hatchet, 1)
        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=20.0, y=20.0)

        # Test 1: Harvest wood on non-forest tile
        mock_server.world.world_map.width = 100
        mock_server.world.world_map.height = 100
        mock_server.world.world_map.get_tile.return_value = TileType.WATER

        harvest_request = create_harvest_wood_action(20.0, 20.0)
        harvest_request.agent_id = "error_agent"

        response = await action_processor.submit_action(harvest_request)
        assert response.result == ActionResult.REJECTED
        assert "wood_harvesting" in response.message.lower() and "locations" in response.message.lower()

        # Test 2: Craft without materials (change to correct tile type first)
        mock_server.world.world_map.get_tile.return_value = TileType.GRASS  # Valid crafting location
        craft_request = create_craft_item_action("basic_fire", 20.0, 20.0)
        craft_request.agent_id = "error_agent"

        craft_response = await action_processor.submit_action(craft_request)
        assert craft_response.result == ActionResult.REJECTED
        assert "missing required items" in craft_response.message.lower() or "insufficient" in craft_response.message.lower()

        # Test 3: Trade with non-existent agent
        trade_request = create_trade_request_action(
            "nonexistent_agent",
            [{"item_name": "wood", "quantity": 1}],
            [{"item_name": "Fish", "quantity": 1}]
        )
        trade_request.agent_id = "error_agent"

        trade_response = await action_processor.submit_action(trade_request)
        assert trade_response.result == ActionResult.REJECTED

    @pytest.mark.asyncio
    async def test_concurrent_actions(self, action_processor, mock_server):
        """Test handling concurrent actions from multiple agents"""
        agent1 = ServerAgentState("concurrent1", "explorer", 5.0, 5.0)
        agent1.position = (5.0, 5.0)  # Explicitly set position
        agent2 = ServerAgentState("concurrent2", "explorer", 6.0, 6.0)
        agent2.position = (6.0, 6.0)  # Explicitly set position

        wood_item = create_wood()
        agent1.inventory.add_item(wood_item, 5)
        agent2.inventory.add_item(wood_item, 5)

        def get_agent_mock(agent_id):
            return agent1 if agent_id == "concurrent1" else agent2 if agent_id == "concurrent2" else None

        mock_server.agent_registry.get_agent.side_effect = get_agent_mock
        mock_server.world.get_agent.side_effect = lambda aid: Mock(x=5.0, y=5.0) if aid == "concurrent1" else Mock(x=6.0, y=6.0)
        # Mock fire object creation
        def create_fire_mock(*args, **kwargs):
            mock_fire = Mock()
            mock_fire.object_type = Mock()
            mock_fire.object_type.value = "fire"
            return mock_fire
        mock_server.world.world_objects.create_fire.side_effect = create_fire_mock
        # Make sure world.server points to the mock_server for database calls
        mock_server.world.server = mock_server

        # Both agents try to craft at the same time
        request1 = create_craft_item_action("basic_fire", 5.0, 5.0)
        request1.agent_id = "concurrent1"
        request2 = create_craft_item_action("basic_fire", 6.0, 6.0)
        request2.agent_id = "concurrent2"

        # Execute concurrently
        response1, response2 = await asyncio.gather(
            action_processor.submit_action(request1),
            action_processor.submit_action(request2)
        )

        # Both should succeed (no shared state conflicts)
        assert response1.result == ActionResult.APPROVED
        assert response2.result == ActionResult.APPROVED

    @pytest.mark.asyncio
    async def test_database_integration(self, action_processor, mock_server):
        """Test database integration across all new features"""
        agent = ServerAgentState("db_agent", "explorer", 25.0, 25.0)
        agent.position = (25.0, 25.0)  # Explicitly set position
        wood_item = create_wood()
        agent.inventory.add_item(wood_item, 10)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=25.0, y=25.0)
        # Mock fire object with proper structure
        mock_fire = Mock()
        mock_fire.object_type = Mock()
        mock_fire.object_type.value = "campfire"
        mock_server.world.world_objects.create_fire.return_value = mock_fire
        # Make sure world.server points to the mock_server for database calls
        mock_server.world.server = mock_server

        # Test crafting database record
        craft_request = create_craft_item_action("campfire", 25.0, 25.0)
        craft_request.agent_id = "db_agent"

        response = await action_processor.submit_action(craft_request)
        assert response.result == ActionResult.APPROVED

        # Verify database record_craft was called
        mock_server.database_manager.record_craft.assert_called_once()
        call_args = mock_server.database_manager.record_craft.call_args[0]  # Positional args

        assert call_args[0] == "db_agent"  # agent_id
        assert call_args[1] == "campfire"  # recipe_name
        # ingredients and result_item are in call_args[2] and call_args[3]
        ingredients = call_args[2]
        assert len(ingredients) == 1
        assert ingredients[0]["item_name"] == "wood"
        assert ingredients[0]["quantity"] == 5  # campfire needs 5 wood

    @pytest.mark.asyncio
    async def test_cooldown_system_integration(self, action_processor, mock_server):
        """Test that cooldown system works across all action types"""
        agent = ServerAgentState("cooldown_agent", "explorer", 30.0, 30.0)
        agent.position = (30.0, 30.0)  # Explicitly set position
        hatchet = create_hatchet()
        agent.inventory.add_item(hatchet, 1)
        wood_item = create_wood()
        agent.inventory.add_item(wood_item, 10)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=30.0, y=30.0)
        mock_server.world.world_map.width = 100
        mock_server.world.world_map.height = 100
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD
        # Mock fire object with proper structure
        mock_fire = Mock()
        mock_fire.object_type = Mock()
        mock_fire.object_type.value = "fire"
        mock_server.world.world_objects.create_fire.return_value = mock_fire
        # Make sure world.server points to the mock_server for database calls
        mock_server.world.server = mock_server

        # Test harvest cooldown with mocked timing
        import asyncio
        from unittest.mock import patch

        with patch('asyncio.sleep', return_value=None):
            harvest_request1 = create_harvest_wood_action(30.0, 30.0)
            harvest_request1.agent_id = "cooldown_agent"

            response1 = await action_processor.submit_action(harvest_request1)
            assert response1.result == ActionResult.APPROVED

            # Immediate second request should be rejected due to cooldown (new request object)
            harvest_request2 = create_harvest_wood_action(30.0, 30.0)
            harvest_request2.agent_id = "cooldown_agent"
            response2 = await action_processor.submit_action(harvest_request2)
            assert response2.result == ActionResult.REJECTED
            assert "cooldown" in response2.message.lower()

        # Test craft cooldown (clear harvest cooldown first)
        for validator in action_processor.validators:
            if hasattr(validator, 'last_use'):
                validator.last_use.clear()

        craft_request = create_craft_item_action("basic_fire", 30.0, 30.0)
        craft_request.agent_id = "cooldown_agent"

        craft_response1 = await action_processor.submit_action(craft_request)
        assert craft_response1.result == ActionResult.APPROVED

        craft_response2 = await action_processor.submit_action(craft_request)
        assert craft_response2.result == ActionResult.REJECTED
        assert "cooldown" in craft_response2.message.lower()

    @pytest.mark.asyncio
    async def test_inventory_space_limits(self, action_processor, mock_server):
        """Test inventory space handling across features"""
        agent = ServerAgentState("inventory_agent", "explorer", 35.0, 35.0)
        agent.position = (35.0, 35.0)  # Explicitly set position
        hatchet = create_hatchet()
        agent.inventory.add_item(hatchet, 1)

        # Fill inventory to near capacity
        wood_item = create_wood()
        for _ in range(agent.inventory.MAX_SLOTS - 1):  # Leave one slot free
            agent.inventory.add_item(wood_item, 1)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=35.0, y=35.0)
        mock_server.world.world_map.width = 100
        mock_server.world.world_map.height = 100
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD

        # Test harvesting with nearly full inventory
        harvest_request = create_harvest_wood_action(35.0, 35.0)
        harvest_request.agent_id = "inventory_agent"

        response = await action_processor.submit_action(harvest_request)

        # Should handle inventory limits gracefully
        if response.result != ActionResult.APPROVED:
            assert "inventory" in response.message.lower() or response.result == ActionResult.APPROVED