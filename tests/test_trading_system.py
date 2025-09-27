"""
Tests for the trading system implementation.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from shared.actions import ActionType, ActionResult, create_trade_request_action, create_trade_accept_action, create_trade_decline_action
from shared.items import create_wood, create_fish, ItemType
from server.action_processor import ActionProcessor, ActionRequest, ActionContext
from server.agent_state import ServerAgentState
from shared.inventory import Inventory, InventorySlot
from server.database import DatabaseManager


class TestTradingSystem:
    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.world = Mock()
        server.agent_registry = Mock()
        server.database_manager = AsyncMock(spec=DatabaseManager)
        return server

    @pytest.fixture
    def action_processor(self, mock_server):
        # Create mock attack system
        mock_attack_system = Mock()
        return ActionProcessor(mock_server.world, mock_server.agent_registry, mock_attack_system)

    @pytest.fixture
    def agent_states(self):
        """Create two test agent states for trading"""
        # Agent 1 - has wood
        agent1 = ServerAgentState("agent1", "explorer", 10.0, 10.0)
        wood_item = create_wood()
        agent1.inventory.add_item(wood_item, 5)

        # Agent 2 - has fish
        agent2 = ServerAgentState("agent2", "explorer", 11.0, 11.0)
        fish_item = create_fish()
        agent2.inventory.add_item(fish_item, 3)

        return agent1, agent2

    @pytest.mark.asyncio
    async def test_trade_request_success(self, action_processor, mock_server, agent_states):
        """Test successful trade request creation"""
        agent1, agent2 = agent_states

        # Setup mock server responses
        mock_server.agent_registry.get_agent.side_effect = lambda aid: agent1 if aid == "agent1" else agent2
        mock_server.world.get_agent.side_effect = lambda aid: Mock(x=10.0, y=10.0) if aid == "agent1" else Mock(x=11.0, y=11.0)

        # Create trade request action
        request = create_trade_request_action(
            "agent2",  # target agent
            [{"item_name": "wood", "quantity": 2}],  # offering
            [{"item_name": "Fresh Fish", "quantity": 1}]  # requesting
        )
        request.agent_id = "agent1"

        response = await action_processor.submit_action(request)

        assert response.result == ActionResult.APPROVED
        assert "trade request sent" in response.message.lower()
        assert len(action_processor.active_trades) == 1

    @pytest.mark.asyncio
    async def test_trade_request_insufficient_items(self, action_processor, mock_server, agent_states):
        """Test trade request with insufficient items"""
        agent1, agent2 = agent_states

        mock_server.agent_registry.get_agent.side_effect = lambda aid: agent1 if aid == "agent1" else agent2
        mock_server.world.get_agent.side_effect = lambda aid: Mock(x=10.0, y=10.0) if aid == "agent1" else Mock(x=11.0, y=11.0)

        # Request more wood than agent1 has (has 5, requesting 10)
        request = create_trade_request_action(
            "agent2",
            [{"item_name": "wood", "quantity": 10}],
            [{"item_name": "Fresh Fish", "quantity": 1}]
        )
        request.agent_id = "agent1"

        response = await action_processor.submit_action(request)

        assert response.result == ActionResult.REJECTED
        assert "insufficient" in response.message.lower()

    @pytest.mark.asyncio
    async def test_trade_accept_success(self, action_processor, mock_server, agent_states):
        """Test successful trade acceptance and completion"""
        agent1, agent2 = agent_states

        mock_server.agent_registry.get_agent.side_effect = lambda aid: agent1 if aid == "agent1" else agent2
        mock_server.world.get_agent.side_effect = lambda aid: Mock(x=10.0, y=10.0) if aid == "agent1" else Mock(x=11.0, y=11.0)

        # First create a trade request
        trade_id = "test_trade_123"
        action_processor.active_trades[trade_id] = {
            "initiator_id": "agent1",
            "target_id": "agent2",
            "initiator_items": [{"item_name": "wood", "quantity": 2}],
            "target_items": [{"item_name": "Fresh Fish", "quantity": 1}],
            "created_time": 1000.0
        }

        # Record initial inventories
        initial_agent1_wood = agent1.inventory.get_item_quantity("wood")
        initial_agent1_fish = agent1.inventory.get_item_quantity("Fresh Fish")
        initial_agent2_wood = agent2.inventory.get_item_quantity("wood")
        initial_agent2_fish = agent2.inventory.get_item_quantity("Fresh Fish")

        # Accept the trade
        request = create_trade_accept_action(trade_id)
        request.agent_id = "agent2"

        response = await action_processor.submit_action(request)

        assert response.result == ActionResult.APPROVED
        assert "trade completed" in response.message.lower()

        # Verify inventory changes
        assert agent1.inventory.get_item_quantity("wood") == initial_agent1_wood - 2
        assert agent1.inventory.get_item_quantity("Fresh Fish") == initial_agent1_fish + 1
        assert agent2.inventory.get_item_quantity("wood") == initial_agent2_wood + 2
        assert agent2.inventory.get_item_quantity("Fresh Fish") == initial_agent2_fish - 1

        # Verify trade is removed from active trades
        assert trade_id not in action_processor.active_trades

    @pytest.mark.asyncio
    async def test_trade_decline(self, action_processor, mock_server, agent_states):
        """Test trade decline removes trade session"""
        agent1, agent2 = agent_states

        mock_server.agent_registry.get_agent.side_effect = lambda aid: agent1 if aid == "agent1" else agent2

        # Create active trade
        trade_id = "test_trade_456"
        action_processor.active_trades[trade_id] = {
            "initiator_id": "agent1",
            "target_id": "agent2",
            "initiator_items": [{"item_name": "wood", "quantity": 1}],
            "target_items": [{"item_name": "Fresh Fish", "quantity": 1}],
            "created_time": 1000.0
        }

        # Decline the trade
        request = create_trade_decline_action(trade_id)
        request.agent_id = "agent2"

        response = await action_processor.submit_action(request)

        assert response.result == ActionResult.APPROVED
        assert "declined" in response.message.lower()
        assert trade_id not in action_processor.active_trades

    @pytest.mark.asyncio
    async def test_trade_distance_validation(self, action_processor, mock_server, agent_states):
        """Test that trades are rejected when agents are too far apart"""
        agent1, agent2 = agent_states

        mock_server.agent_registry.get_agent.side_effect = lambda aid: agent1 if aid == "agent1" else agent2
        # Agents too far apart (distance > 5)
        mock_server.world.get_agent.side_effect = lambda aid: Mock(x=0.0, y=0.0) if aid == "agent1" else Mock(x=10.0, y=10.0)

        request = create_trade_request_action(
            "agent2",
            [{"item_name": "wood", "quantity": 1}],
            [{"item_name": "Fresh Fish", "quantity": 1}]
        )
        request.agent_id = "agent1"

        response = await action_processor.submit_action(request)

        assert response.result == ActionResult.REJECTED
        assert "too far" in response.message.lower()

    @pytest.mark.asyncio
    async def test_trade_cleanup_expired(self, action_processor, mock_server):
        """Test that expired trades are cleaned up"""
        import time

        # Add expired trade (older than 60 seconds)
        old_time = time.time() - 120  # 2 minutes ago
        action_processor.active_trades["expired_trade"] = {
            "initiator_id": "agent1",
            "target_id": "agent2",
            "initiator_items": [],
            "target_items": [],
            "created_time": old_time
        }

        # Add recent trade
        recent_time = time.time() - 30  # 30 seconds ago
        action_processor.active_trades["recent_trade"] = {
            "initiator_id": "agent1",
            "target_id": "agent2",
            "initiator_items": [],
            "target_items": [],
            "created_time": recent_time
        }

        # Call cleanup
        action_processor._cleanup_expired_trades()

        # Only recent trade should remain
        assert "expired_trade" not in action_processor.active_trades
        assert "recent_trade" in action_processor.active_trades