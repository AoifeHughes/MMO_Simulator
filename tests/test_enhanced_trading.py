"""
Tests for Enhanced Trading System

Tests the new market-maker functionality including trade advertisements,
automatic matching, multi-item bartering, and trade negotiations.
"""

import asyncio
import time
from unittest.mock import MagicMock, Mock

import pytest

from server.action_processor import ActionProcessor
from shared.actions import (
    ActionRequest,
    ActionType,
    create_advertise_trade_action,
    create_cancel_trade_ad_action,
    create_negotiate_trade_action,
    create_search_trades_action,
    create_trade_request_action,
)
from shared.items import Item


class MockAgent:
    """Mock agent for testing trade functionality"""

    def __init__(self, agent_id: str, x: float = 0.0, y: float = 0.0):
        self.id = agent_id
        self.position = (x, y)
        self.inventory = MockInventory()


class MockInventory:
    """Mock inventory for testing"""

    def __init__(self):
        self.items = {}

    def add_item(self, item_id: str, item_type: str, quantity: int = 1):
        """Add item to inventory"""
        self.items[item_id] = MockItem(item_id, item_type, quantity)

    def get_item_by_id(self, item_id: str):
        """Get item by ID"""
        return self.items.get(item_id)


class MockItem:
    """Mock item for testing"""

    def __init__(self, item_id: str, item_type: str, quantity: int = 1):
        self.id = item_id
        self.type = item_type
        self.quantity = quantity


class MockAgentRegistry:
    """Mock agent registry for testing"""

    def __init__(self):
        self.agents = {}

    def add_agent(self, agent: MockAgent):
        self.agents[agent.id] = agent

    def get_agent(self, agent_id: str) -> MockAgent:
        return self.agents.get(agent_id)


class TestEnhancedTradingSystem:
    """Test enhanced trading functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.world = Mock()
        self.agent_registry = MockAgentRegistry()
        self.attack_system = Mock()

        self.processor = ActionProcessor(
            self.world, self.agent_registry, self.attack_system
        )

        # Create test agents
        self.agent1 = MockAgent("agent1", 10.0, 10.0)
        self.agent1.inventory.add_item("wood_1", "wood", 5)
        self.agent1.inventory.add_item("stone_1", "stone", 3)

        self.agent2 = MockAgent("agent2", 12.0, 12.0)  # Closer to agent1 for trading
        self.agent2.inventory.add_item("fish_1", "fish", 8)
        self.agent2.inventory.add_item("iron_1", "iron", 2)

        self.agent3 = MockAgent("agent3", 100.0, 100.0)  # Far away agent
        self.agent3.inventory.add_item("gold_1", "gold", 1)

        self.agent_registry.add_agent(self.agent1)
        self.agent_registry.add_agent(self.agent2)
        self.agent_registry.add_agent(self.agent3)

    @pytest.mark.asyncio
    async def test_advertise_trade_success(self):
        """Test successful trade advertisement creation"""
        # Create advertisement action
        action = create_advertise_trade_action(
            offering_items=[{"item_id": "wood_1", "quantity": 3}],
            requesting_items=[{"item_type": "fish", "quantity": 2}],
            duration=300.0,
            max_distance=50.0,
        )
        action.agent_id = "agent1"

        # Execute action
        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_advertise_trade(action, context)

        # Verify response
        assert response.result.value == "approved"
        assert "ad_id" in response.approved_parameters
        assert len(self.processor.trade_advertisements) == 1
        assert len(self.processor.agent_advertisements["agent1"]) == 1

    @pytest.mark.asyncio
    async def test_advertise_trade_insufficient_items(self):
        """Test advertisement rejection for insufficient items"""
        # Try to advertise more items than available
        action = create_advertise_trade_action(
            offering_items=[{"item_id": "wood_1", "quantity": 10}],  # Agent only has 5
            requesting_items=[{"item_type": "fish", "quantity": 2}],
        )
        action.agent_id = "agent1"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_advertise_trade(action, context)

        # Verify rejection
        assert response.result.value == "rejected"
        assert "Insufficient quantity" in response.message
        assert len(self.processor.trade_advertisements) == 0

    @pytest.mark.asyncio
    async def test_search_trades_with_matches(self):
        """Test searching for trades with matching advertisements"""
        # First, create some advertisements
        await self._create_test_advertisement(
            "agent1",
            [{"item_id": "wood_1", "quantity": 3}],
            [{"item_type": "fish", "quantity": 2}],
        )

        await self._create_test_advertisement(
            "agent3",
            [{"item_id": "gold_1", "quantity": 1}],
            [{"item_type": "wood", "quantity": 5}],
        )

        # Agent2 searches for trades (has fish, wants wood)
        action = create_search_trades_action(
            desired_items=[{"item_type": "wood"}],
            available_items=[{"item_type": "fish"}],
            max_distance=50.0,
        )
        action.agent_id = "agent2"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_search_trades(action, context)

        # Verify results
        assert response.result.value == "approved"
        assert "matching_ads" in response.approved_parameters
        matching_ads = response.approved_parameters["matching_ads"]

        # Should find agent1's ad (within distance) but not agent3's (too far)
        assert len(matching_ads) == 1
        assert matching_ads[0]["advertiser"] == "agent1"
        assert matching_ads[0]["match_score"] > 0

    @pytest.mark.asyncio
    async def test_search_trades_no_matches(self):
        """Test searching for trades with no matching advertisements"""
        # Create advertisement that doesn't match search
        await self._create_test_advertisement(
            "agent1",
            [{"item_type": "stone"}],  # Offering stone
            [{"item_type": "iron"}],  # Wanting iron
        )

        # Agent2 searches for trades - no overlap with agent1's ad
        action = create_search_trades_action(
            desired_items=[{"item_type": "gold"}],  # Want gold (agent1 not offering)
            available_items=[{"item_type": "fish"}],  # Have fish (agent1 not wanting)
            max_distance=50.0,
        )
        action.agent_id = "agent2"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_search_trades(action, context)

        # Verify no matches
        assert response.result.value == "approved"
        assert response.approved_parameters["total_matches"] == 0
        assert len(response.approved_parameters["matching_ads"]) == 0

    @pytest.mark.asyncio
    async def test_negotiate_trade_success(self):
        """Test successful trade negotiation"""
        # First create a trade
        trade_id = await self._create_test_trade("agent1", "agent2")

        # Agent2 makes a counter-offer
        counter_offer = {
            "offering_items": [{"item_id": "fish_1", "quantity": 4}],
            "requesting_items": [{"item_id": "wood_1", "quantity": 2}],
        }

        action = create_negotiate_trade_action(trade_id, counter_offer)
        action.agent_id = "agent2"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_negotiate_trade(action, context)

        # Verify negotiation
        assert response.result.value == "approved"
        assert trade_id in self.processor.trade_negotiations
        assert len(self.processor.trade_negotiations[trade_id]["offers"]) == 1
        assert self.processor.active_trades[trade_id]["status"] == "negotiating"

    @pytest.mark.asyncio
    async def test_negotiate_trade_insufficient_items(self):
        """Test negotiation rejection for insufficient items"""
        # Create a trade
        trade_id = await self._create_test_trade("agent1", "agent2")

        # Agent2 tries to offer more fish than they have
        counter_offer = {
            "offering_items": [{"item_id": "fish_1", "quantity": 20}],  # Only has 8
            "requesting_items": [{"item_id": "wood_1", "quantity": 2}],
        }

        action = create_negotiate_trade_action(trade_id, counter_offer)
        action.agent_id = "agent2"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_negotiate_trade(action, context)

        # Verify rejection
        assert response.result.value == "rejected"
        assert "Insufficient quantity" in response.message

    @pytest.mark.asyncio
    async def test_negotiate_trade_not_participant(self):
        """Test negotiation rejection for non-participants"""
        # Create a trade between agent1 and agent2
        trade_id = await self._create_test_trade("agent1", "agent2")

        # Agent3 tries to negotiate (not part of trade)
        counter_offer = {
            "offering_items": [{"item_id": "gold_1", "quantity": 1}],
            "requesting_items": [{"item_id": "wood_1", "quantity": 2}],
        }

        action = create_negotiate_trade_action(trade_id, counter_offer)
        action.agent_id = "agent3"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_negotiate_trade(action, context)

        # Verify rejection
        assert response.result.value == "rejected"
        assert "not part of this trade" in response.message

    @pytest.mark.asyncio
    async def test_cancel_trade_ad_success(self):
        """Test successful trade advertisement cancellation"""
        # Create advertisement
        ad_id = await self._create_test_advertisement(
            "agent1",
            [{"item_id": "wood_1", "quantity": 3}],
            [{"item_type": "fish", "quantity": 2}],
        )

        # Cancel advertisement
        action = create_cancel_trade_ad_action(ad_id)
        action.agent_id = "agent1"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_cancel_trade_ad(action, context)

        # Verify cancellation
        assert response.result.value == "approved"
        assert self.processor.trade_advertisements[ad_id]["status"] == "cancelled"
        assert ad_id not in self.processor.agent_advertisements["agent1"]

    @pytest.mark.asyncio
    async def test_cancel_trade_ad_not_owner(self):
        """Test trade advertisement cancellation by non-owner"""
        # Create advertisement by agent1
        ad_id = await self._create_test_advertisement(
            "agent1",
            [{"item_id": "wood_1", "quantity": 3}],
            [{"item_type": "fish", "quantity": 2}],
        )

        # Agent2 tries to cancel agent1's advertisement
        action = create_cancel_trade_ad_action(ad_id)
        action.agent_id = "agent2"

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_cancel_trade_ad(action, context)

        # Verify rejection
        assert response.result.value == "rejected"
        assert "only cancel your own" in response.message

    def test_cleanup_expired_trade_ads(self):
        """Test cleanup of expired trade advertisements"""
        # Create advertisement with very short duration
        current_time = time.time()
        ad_data = {
            "ad_id": "test_ad",
            "advertiser": "agent1",
            "offering_items": [],
            "requesting_items": [],
            "created_time": current_time - 100,
            "expires_time": current_time - 50,  # Expired 50 seconds ago
            "location": (10.0, 10.0),
            "max_distance": 50.0,
            "status": "active",
        }

        self.processor.trade_advertisements["test_ad"] = ad_data
        self.processor.agent_advertisements["agent1"].append("test_ad")

        # Run cleanup
        self.processor._cleanup_expired_trade_ads()

        # Verify cleanup
        assert self.processor.trade_advertisements["test_ad"]["status"] == "expired"
        assert "test_ad" not in self.processor.agent_advertisements["agent1"]

    def test_get_active_trade_ads_for_agent(self):
        """Test getting active trade advertisements for agent"""
        current_time = time.time()

        # Create active advertisement
        active_ad = {
            "ad_id": "active_ad",
            "advertiser": "agent1",
            "expires_time": current_time + 300,
            "status": "active",
        }

        # Create expired advertisement
        expired_ad = {
            "ad_id": "expired_ad",
            "advertiser": "agent1",
            "expires_time": current_time - 300,
            "status": "active",
        }

        self.processor.trade_advertisements["active_ad"] = active_ad
        self.processor.trade_advertisements["expired_ad"] = expired_ad
        self.processor.agent_advertisements["agent1"] = ["active_ad", "expired_ad"]

        # Get active ads
        active_ads = self.processor.get_active_trade_ads_for_agent("agent1")

        # Should only return active, non-expired ad
        assert len(active_ads) == 1
        assert active_ads[0]["ad_id"] == "active_ad"

    def test_get_trade_market_stats(self):
        """Test trade market statistics"""
        current_time = time.time()

        # Create various advertisements
        ads = {
            "active_ad": {
                "status": "active",
                "expires_time": current_time + 300,
                "offering_items": [{"item": "wood"}],
                "requesting_items": [{"item": "fish"}],
            },
            "expired_ad": {
                "status": "expired",
                "expires_time": current_time - 300,
                "offering_items": [],
                "requesting_items": [],
            },
            "cancelled_ad": {
                "status": "cancelled",
                "expires_time": current_time + 300,
                "offering_items": [],
                "requesting_items": [],
            },
        }

        self.processor.trade_advertisements.update(ads)

        # Add a negotiation
        self.processor.trade_negotiations["trade_1"] = {"offers": []}

        # Get stats
        stats = self.processor.get_trade_market_stats()

        # Verify stats
        assert stats["active_advertisements"] == 1
        assert stats["expired_advertisements"] == 1
        assert stats["cancelled_advertisements"] == 1
        assert stats["total_advertisements"] == 3
        assert stats["active_negotiations"] == 1
        assert stats["estimated_market_value"] == 2  # 1 offering + 1 requesting

    def test_trade_advertisement_distance_filtering(self):
        """Test that trade search respects distance limits"""
        # This test would require setting up advertisements at different distances
        # and verifying that search results are filtered correctly
        pass

    def test_multiple_concurrent_negotiations(self):
        """Test multiple negotiations on the same trade"""
        # This test would verify that multiple counter-offers can be made
        # and that negotiation history is tracked correctly
        pass

    async def _create_test_advertisement(
        self, agent_id: str, offering_items: list, requesting_items: list
    ) -> str:
        """Helper to create a test trade advertisement"""
        action = create_advertise_trade_action(offering_items, requesting_items)
        action.agent_id = agent_id

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_advertise_trade(action, context)

        if response.result.value == "approved":
            return response.approved_parameters["ad_id"]
        else:
            raise Exception(f"Failed to create advertisement: {response.message}")

    async def _create_test_trade(self, initiator_id: str, target_id: str) -> str:
        """Helper to create a test trade"""
        action = create_trade_request_action(
            target_id,
            [{"item_id": "wood_1", "quantity": 2}],
            [{"item_id": "fish_1", "quantity": 3}],
        )
        action.agent_id = initiator_id

        context = Mock()
        context.agent_registry = self.agent_registry
        response = await self.processor._execute_trade_request(action, context)

        if response.result.value == "approved":
            return response.approved_parameters["trade_id"]
        else:
            raise Exception(f"Failed to create trade: {response.message}")


class TestTradeMatching:
    """Test automatic trade matching algorithms"""

    def setup_method(self):
        """Set up test fixtures"""
        self.processor = ActionProcessor(Mock(), MockAgentRegistry(), Mock())

    def test_item_type_matching(self):
        """Test matching by item type"""
        # Test would verify that items are matched by type correctly
        pass

    def test_item_id_matching(self):
        """Test matching by specific item ID"""
        # Test would verify that specific items are matched correctly
        pass

    def test_quantity_matching(self):
        """Test matching with quantity considerations"""
        # Test would verify that quantity requirements are considered
        pass

    def test_match_scoring(self):
        """Test the match scoring algorithm"""
        # Test would verify that matches are scored and ranked correctly
        pass


class TestTradeNegotiation:
    """Test trade negotiation functionality"""

    def test_negotiation_history_tracking(self):
        """Test that negotiation history is properly tracked"""
        pass

    def test_negotiation_timeout(self):
        """Test that negotiations can timeout"""
        pass

    def test_complex_multi_item_negotiation(self):
        """Test negotiations with multiple items"""
        pass


if __name__ == "__main__":
    pytest.main([__file__])
