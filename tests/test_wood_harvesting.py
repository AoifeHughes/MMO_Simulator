"""
Tests for the wood harvesting system implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from shared.actions import ActionType, create_harvest_wood_action
from shared.items import create_wood
from server.action_processor import ActionProcessor, ActionRequest, ActionContext
from server.agent_state import ServerAgentState
from server.database import DatabaseManager
from world.tiles import TileType


class TestWoodHarvesting:
    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.world = Mock()
        server.world.world_map = Mock()
        server.agent_registry = Mock()
        server.database_manager = AsyncMock(spec=DatabaseManager)
        return server

    @pytest.fixture
    def action_processor(self, mock_server):
        return ActionProcessor(mock_server)

    @pytest.fixture
    def agent_near_forest(self):
        """Create agent positioned near a forest tile"""
        agent = ServerAgentState("harvester1", "explorer", 5.0, 5.0)
        # Add starting items including hatchet
        agent.add_starting_items()
        return agent

    @pytest.mark.asyncio
    async def test_harvest_wood_success(self, action_processor, mock_server, agent_near_forest):
        """Test successful wood harvesting from forest tile"""
        agent = agent_near_forest

        # Setup mocks for forest tile at agent's position
        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST

        action = create_harvest_wood_action()
        request = ActionRequest("harvester1", action)
        context = ActionContext()

        initial_wood_count = agent.inventory.get_item_count("Wood")

        response = await action_processor.execute_action(request, context)

        assert response.success
        assert "harvested" in response.message.lower()
        assert "wood" in response.message.lower()

        # Verify wood was added to inventory (1-3 pieces based on random)
        final_wood_count = agent.inventory.get_item_count("Wood")
        assert final_wood_count > initial_wood_count
        assert final_wood_count <= initial_wood_count + 3

    @pytest.mark.asyncio
    async def test_harvest_wood_not_on_forest(self, action_processor, mock_server, agent_near_forest):
        """Test wood harvesting failure when not on forest tile"""
        agent = agent_near_forest

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        # Not a forest tile
        mock_server.world.world_map.get_tile.return_value = TileType.GRASSLAND

        action = create_harvest_wood_action()
        request = ActionRequest("harvester1", action)
        context = ActionContext()

        response = await action_processor.execute_action(request, context)

        assert not response.success
        assert "forest" in response.message.lower()

    @pytest.mark.asyncio
    async def test_harvest_wood_full_inventory(self, action_processor, mock_server, agent_near_forest):
        """Test wood harvesting when inventory is full"""
        agent = agent_near_forest

        # Fill inventory to capacity
        wood_item = create_wood()
        slots_to_fill = agent.inventory.max_slots
        for i in range(slots_to_fill):
            agent.inventory.add_item(wood_item, 1)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST

        action = create_harvest_wood_action()
        request = ActionRequest("harvester1", action)
        context = ActionContext()

        initial_wood_count = agent.inventory.get_item_count("Wood")

        response = await action_processor.execute_action(request, context)

        # Should still succeed if wood can stack
        if response.success:
            assert agent.inventory.get_item_count("Wood") > initial_wood_count
        else:
            assert "inventory" in response.message.lower()

    @pytest.mark.asyncio
    async def test_harvest_wood_cooldown(self, action_processor, mock_server, agent_near_forest):
        """Test wood harvesting cooldown prevents rapid harvesting"""
        agent = agent_near_forest

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST

        action = create_harvest_wood_action()
        request = ActionRequest("harvester1", action)
        context = ActionContext()

        # First harvest should succeed
        response1 = await action_processor.execute_action(request, context)
        assert response1.success

        # Immediate second harvest should fail due to cooldown
        response2 = await action_processor.execute_action(request, context)
        assert not response2.success
        assert "cooldown" in response2.message.lower()

    @pytest.mark.asyncio
    async def test_harvest_wood_agent_not_found(self, action_processor, mock_server):
        """Test wood harvesting failure when agent not found"""
        mock_server.agent_registry.get_agent.return_value = None

        action = create_harvest_wood_action()
        request = ActionRequest("nonexistent_agent", action)
        context = ActionContext()

        response = await action_processor.execute_action(request, context)

        assert not response.success
        assert "not found" in response.message.lower()

    @pytest.mark.asyncio
    async def test_harvest_wood_random_amounts(self, action_processor, mock_server, agent_near_forest):
        """Test that harvesting produces random amounts of wood (1-3)"""
        agent = agent_near_forest

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        mock_server.world.world_map.get_tile.return_value = TileType.FOREST

        # Test multiple harvests to verify randomness
        wood_amounts = set()

        for i in range(10):
            # Reset agent for each test
            agent = ServerAgentState(f"harvester_{i}", "explorer", 5.0, 5.0)
            # Add starting items including hatchet
            agent.add_starting_items()
            mock_server.agent_registry.get_agent.return_value = agent

            # Reset cooldowns for this test
            if hasattr(action_processor, 'action_cooldowns'):
                action_processor.action_cooldowns.clear()

            action = create_harvest_wood_action()
            request = ActionRequest(f"harvester_{i}", action)
            context = ActionContext()

            response = await action_processor.execute_action(request, context)

            if response.success:
                wood_count = agent.inventory.get_item_count("Wood")
                wood_amounts.add(wood_count)

        # Should have gotten different amounts (1, 2, or 3)
        assert len(wood_amounts) > 1  # Some variation in amounts
        assert all(1 <= amount <= 3 for amount in wood_amounts)

    @pytest.mark.asyncio
    async def test_harvest_wood_tile_proximity(self, action_processor, mock_server):
        """Test that harvesting checks the tile the agent is actually on"""
        agent = ServerAgentState("harvester_proximity", "explorer", 5.7, 5.3)  # Between tiles
        # Add starting items including hatchet
        agent.add_starting_items()

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.7, y=5.3)

        # Mock get_tile to return different tiles for different coordinates
        def mock_get_tile(x, y):
            if x == 5 and y == 5:  # int(5.7) = 5, int(5.3) = 5
                return TileType.FOREST
            else:
                return TileType.GRASSLAND

        mock_server.world.world_map.get_tile.side_effect = mock_get_tile

        action = create_harvest_wood_action()
        request = ActionRequest("harvester_proximity", action)
        context = ActionContext()

        response = await action_processor.execute_action(request, context)

        # Should succeed because agent is on tile (5,5) which is forest
        assert response.success

        # Verify get_tile was called with the correct coordinates (int conversion)
        mock_server.world.world_map.get_tile.assert_called_with(5, 5)