"""
Tests for the wood harvesting system implementation.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from server.action_processor import ActionContext, ActionProcessor
from server.agent_state import ServerAgentState
from server.database import DatabaseManager
from shared.actions import ActionRequest, ActionResult, ActionType, harvest_wood_params
from shared.items import create_wood
from tests.action_test_base import ActionTestBase
from world.tiles import TileType


class TestWoodHarvesting(ActionTestBase):
    @pytest.fixture
    def agent_near_forest(self):
        """Create agent positioned near a forest tile"""
        agent = ServerAgentState("harvester1", "explorer")
        agent.position = (5.0, 5.0)  # Explicitly set position
        # Add starting items including hatchet
        agent.add_starting_items()
        return agent

    @pytest.mark.asyncio
    async def test_harvest_wood_success(
        self, action_processor, mock_server, agent_near_forest
    ):
        """Test successful wood harvesting from forest tile"""
        agent = agent_near_forest

        # Setup mocks using OOP helper method
        self.setup_harvest_mocks(mock_server, agent)

        request = self.create_harvest_request("harvester1", 5.0, 5.0)
        initial_wood_count = self.get_wood_count(agent)

        response = await action_processor.submit_action(request)

        self.assert_approved(response)
        assert "harvested" in response.message.lower()
        assert "wood" in response.message.lower()

        # Verify wood was added to inventory (1-3 pieces based on random)
        final_wood_count = self.get_wood_count(agent)
        assert final_wood_count > initial_wood_count
        assert final_wood_count <= initial_wood_count + 3

    @pytest.mark.asyncio
    async def test_harvest_wood_not_on_forest(
        self, action_processor, mock_server, agent_near_forest
    ):
        """Test wood harvesting failure when not on forest tile"""
        agent = agent_near_forest

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        # Not a forest tile
        mock_server.world.world_map.get_tile.return_value = TileType.GRASS

        request = self.create_harvest_request("harvester1", 5.0, 5.0)

        response = await action_processor.submit_action(request)

        self.assert_rejected(response)
        assert (
            "wood" in response.message.lower() or "forest" in response.message.lower()
        )

    @pytest.mark.asyncio
    async def test_harvest_wood_full_inventory(
        self, action_processor, mock_server, agent_near_forest
    ):
        """Test wood harvesting when inventory is full"""
        agent = agent_near_forest

        # Fill inventory to capacity
        wood_item = create_wood()
        from shared.inventory import Inventory

        slots_to_fill = Inventory.MAX_SLOTS
        for i in range(slots_to_fill):
            agent.inventory.add_item(wood_item, 1)

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD

        request = self.create_harvest_request("harvester1", 5.0, 5.0)
        initial_wood_count = self.get_wood_count(agent)

        response = await action_processor.submit_action(request)

        # Should still succeed if wood can stack
        if response.result == ActionResult.APPROVED:
            assert self.get_wood_count(agent) > initial_wood_count
        else:
            assert "inventory" in response.message.lower()

    @pytest.mark.asyncio
    async def test_harvest_wood_cooldown(
        self, action_processor, mock_server, agent_near_forest
    ):
        """Test wood harvesting cooldown prevents rapid harvesting"""
        agent = agent_near_forest

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD

        # Mock asyncio.sleep to make timing deterministic
        import asyncio
        from unittest.mock import patch

        with patch("asyncio.sleep", return_value=None) as mock_sleep:
            request1 = self.create_harvest_request("harvester1", 5.0, 5.0)

            # First harvest should succeed
            response1 = await action_processor.submit_action(request1)
            self.assert_approved(response1)

            # Immediate second harvest should fail due to cooldown (new request object)
            request2 = self.create_harvest_request("harvester1", 5.0, 5.0)
            response2 = await action_processor.submit_action(request2)
            self.assert_rejected(response2)
            assert "cooldown" in response2.message.lower()

    @pytest.mark.asyncio
    async def test_harvest_wood_agent_not_found(self, action_processor, mock_server):
        """Test wood harvesting failure when agent not found"""
        mock_server.agent_registry.get_agent.return_value = None

        request = self.create_harvest_request("nonexistent_agent", 5.0, 5.0)

        response = await action_processor.submit_action(request)

        self.assert_rejected(response)
        assert "not found" in response.message.lower()

    @pytest.mark.asyncio
    async def test_harvest_wood_random_amounts(
        self, action_processor, mock_server, agent_near_forest
    ):
        """Test that harvesting produces random amounts of wood (1-3)"""
        agent = agent_near_forest

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.0, y=5.0)
        mock_server.world.world_map.get_tile.return_value = TileType.WOOD

        # Test multiple harvests to verify randomness
        wood_amounts = set()

        for i in range(10):
            # Reset agent for each test
            agent = ServerAgentState(f"harvester_{i}", "explorer")
            agent.position = (5.0, 5.0)  # Explicitly set position
            # Add starting items including hatchet
            agent.add_starting_items()
            mock_server.agent_registry.get_agent.return_value = agent

            # Reset cooldowns for this test
            if hasattr(action_processor, "action_cooldowns"):
                action_processor.action_cooldowns.clear()

            request = self.create_harvest_request(f"harvester_{i}", 5.0, 5.0)

            response = await action_processor.submit_action(request)

            if response.result == ActionResult.APPROVED:
                wood_count = self.get_wood_count(agent)
                wood_amounts.add(wood_count)

        # Should have gotten different amounts (1, 2, or 3)
        assert len(wood_amounts) > 1  # Some variation in amounts
        assert all(1 <= amount <= 3 for amount in wood_amounts)

    @pytest.mark.asyncio
    async def test_harvest_wood_tile_proximity(self, action_processor, mock_server):
        """Test that harvesting checks the tile the agent is actually on"""
        agent = ServerAgentState("harvester_proximity", "explorer")  # Between tiles
        agent.position = (5.7, 5.3)  # Explicitly set position
        # Add starting items including hatchet
        agent.add_starting_items()

        mock_server.agent_registry.get_agent.return_value = agent
        mock_server.world.get_agent.return_value = Mock(x=5.7, y=5.3)

        # Mock get_tile to return different tiles for different coordinates
        def mock_get_tile(x, y):
            if x == 5 and y == 5:  # int(5.7) = 5, int(5.3) = 5
                return TileType.WOOD
            else:
                return TileType.GRASS

        mock_server.world.world_map.get_tile.side_effect = mock_get_tile

        request = self.create_harvest_request("harvester_proximity", 5.0, 5.0)

        response = await action_processor.submit_action(request)

        # Should succeed because agent is on tile (5,5) which is forest
        self.assert_approved(response)

        # Verify get_tile was called with the correct coordinates (int conversion)
        mock_server.world.world_map.get_tile.assert_called_with(5, 5)
