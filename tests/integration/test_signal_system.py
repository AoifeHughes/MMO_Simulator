"""
Integration tests for the Signal System.

Tests that signals work properly between agents through the server broadcaster,
including signal creation, broadcasting, filtering, and reception.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock

from client.agent import BaseAgent
from server.signal_broadcaster import SignalBroadcaster, SignalQueue
from shared.signals import (
    Signal, SignalType, SignalPriority, SignalFilter,
    create_help_request, create_resource_found, create_enemy_spotted,
    create_trade_offer, create_area_clear, create_gather_signal
)
from shared.personality import Personality


class MockSignalAgent(BaseAgent):
    """Simple test agent implementation for signal testing"""

    def __init__(self, agent_id, x, y, agent_type, personality=None):
        super().__init__(agent_id, x, y, agent_type, personality)
        self.received_signals = []
        # Let the base agent handle signal system initialization

    def update(self, delta_time: float):
        pass

    def perceive(self, visible_entities):
        self.visible_entities = visible_entities

    def decide(self):
        return None

    def receive_signal(self, signal: Signal):
        """Receive a signal from the broadcaster"""
        self.received_signals.append(signal)
        # Call the parent method to handle signal system properly
        super().receive_signal(signal)


class MockTestServer:
    """Mock server for testing signal broadcasting"""

    def __init__(self):
        self.agents = {}
        self.world = self

    def add_agent(self, agent):
        self.agents[agent.id] = agent

    def get_agent(self, agent_id):
        return self.agents.get(agent_id)

    def get_all_agents(self):
        return list(self.agents.values())

    def has_agent(self, agent_id):
        return agent_id in self.agents


class TestSignalSystemIntegration:
    """Test signal system integration"""

    def setup_method(self):
        """Set up test fixtures"""
        self.server = MockTestServer()
        self.broadcaster = SignalBroadcaster(self.server)

        # Create test agents
        self.agent1 = MockSignalAgent("agent1", 10.0, 10.0, "player",
                                     Personality(social=8.0, cooperativeness=7.0))
        self.agent2 = MockSignalAgent("agent2", 15.0, 15.0, "player",
                                     Personality(social=6.0, cooperativeness=9.0))
        self.agent3 = MockSignalAgent("agent3", 50.0, 50.0, "player",
                                     Personality(social=3.0, cooperativeness=4.0))

        # Add agents to server
        self.server.add_agent(self.agent1)
        self.server.add_agent(self.agent2)
        self.server.add_agent(self.agent3)

    def test_basic_signal_broadcasting(self):
        """Test basic signal broadcasting between agents"""
        # Create a help request signal
        signal = create_help_request("agent1", (10.0, 10.0), enemy_count=2)

        # Broadcast the signal
        success = self.broadcaster.broadcast_signal(signal)
        assert success is True

        # Check that nearby agents received the signal
        assert len(self.agent2.received_signals) == 1
        assert self.agent2.received_signals[0].signal_id == signal.signal_id

        # Agent3 should not receive it (too far away)
        assert len(self.agent3.received_signals) == 0

    def test_signal_range_limitations(self):
        """Test that signals respect range limitations"""
        # Create a signal with limited range
        signal = create_trade_offer("agent1", (10.0, 10.0),
                                  [{"item": "wood", "quantity": 5}],
                                  [{"item": "fish", "quantity": 3}])

        self.broadcaster.broadcast_signal(signal)

        # Agent2 is within range (distance ~7.07)
        assert len(self.agent2.received_signals) == 1

        # Agent3 is out of range (distance ~56.57, signal range is 25.0)
        assert len(self.agent3.received_signals) == 0

    def test_signal_filtering_by_personality(self):
        """Test that agents filter signals based on personality"""
        # Create a gather signal
        signal = create_gather_signal("agent1", (10.0, 10.0), "exploration")

        # Set up signal filters for agents
        # Initialize signal filters first
        filter2 = self.agent2.get_signal_filter()
        filter3 = self.agent3.get_signal_filter()

        filter2.set_signal_preference(SignalType.GATHER_HERE, 0.0)  # Reject
        filter3.set_signal_preference(SignalType.GATHER_HERE, 1.0)  # Accept

        # Move agent3 closer for this test
        self.agent3.x = 20.0
        self.agent3.y = 20.0

        self.broadcaster.broadcast_signal(signal)

        # Agent2 should filter out the signal despite being in range
        # (Note: filtering happens at agent level, not broadcaster level)
        # We need to test the filter directly
        agent2_filter = self.agent2.get_signal_filter()
        should_receive = agent2_filter.should_receive_signal(signal, self.agent2.personality)
        assert should_receive is False

        agent3_filter = self.agent3.get_signal_filter()
        should_receive = agent3_filter.should_receive_signal(signal, self.agent3.personality)
        assert should_receive is True

    def test_signal_priority_handling(self):
        """Test signal priority and emergency handling"""
        # Create signals with different priorities
        low_signal = create_area_clear("agent1", (10.0, 10.0), (10.0, 10.0, 20.0))
        urgent_signal = Signal(
            signal_id="urgent_test",
            signal_type=SignalType.DANGER_WARNING,
            sender_id="agent1",
            message="Urgent danger!",
            priority=SignalPriority.URGENT,
            sender_position=(10.0, 10.0),
            range_limit=80.0
        )

        # Broadcast both signals
        self.broadcaster.broadcast_signal(low_signal)
        self.broadcaster.broadcast_signal(urgent_signal)

        # Check that agent2 received both signals
        assert len(self.agent2.received_signals) == 2

        # Check signal queue prioritization
        signal_queue = self.agent2.signal_queue
        next_signal = signal_queue.get_next_signal()
        assert next_signal.priority == SignalPriority.URGENT

    def test_multiple_signal_types(self):
        """Test broadcasting multiple different signal types"""
        signals = [
            create_help_request("agent1", (10.0, 10.0)),
            create_resource_found("agent1", (10.0, 10.0), "wood", (12.0, 12.0), 3),
            create_enemy_spotted("agent1", (10.0, 10.0), (8.0, 8.0), 2)
        ]

        # Broadcast all signals
        for signal in signals:
            success = self.broadcaster.broadcast_signal(signal)
            assert success is True

        # Agent2 should receive all signals (within range)
        assert len(self.agent2.received_signals) == 3

        # Verify signal types
        received_types = {s.signal_type for s in self.agent2.received_signals}
        expected_types = {SignalType.HELP_REQUEST, SignalType.RESOURCE_FOUND, SignalType.ENEMY_SPOTTED}
        assert received_types == expected_types

    def test_signal_expiration(self):
        """Test that expired signals are properly handled"""
        # Create a signal with very short duration
        signal = Signal(
            signal_id="short_lived",
            signal_type=SignalType.HELP_REQUEST,
            sender_id="agent1",
            message="Quick help!",
            duration=0.01,  # 10ms duration
            sender_position=(10.0, 10.0)
        )

        self.broadcaster.broadcast_signal(signal)

        # Wait for signal to expire
        time.sleep(0.02)

        # Force cleanup by setting the last cleanup time to trigger it
        self.broadcaster.last_cleanup_time = time.time() - 31.0  # Force cleanup trigger
        self.broadcaster.process_signals()

        # Signal should be removed from active signals
        assert signal.signal_id not in self.broadcaster.active_signals

        # Signal queue should clean expired signals
        self.agent2.signal_queue.clear_expired()
        expired_signals = [s for s in self.agent2.signal_queue.signals if s.is_expired()]
        assert len(expired_signals) == 0

    def test_rate_limiting(self):
        """Test signal rate limiting"""
        # Try to send many signals quickly
        signals_sent = 0
        signals_accepted = 0

        for i in range(15):  # More than the limit (10 per minute)
            signal = Signal(
                signal_id=f"spam_{i}",
                signal_type=SignalType.HELP_REQUEST,
                sender_id="agent1",
                message=f"Spam signal {i}",
                sender_position=(10.0, 10.0)
            )

            success = self.broadcaster.broadcast_signal(signal)
            signals_sent += 1
            if success:
                signals_accepted += 1

        # Should have rejected some signals due to rate limiting
        assert signals_sent == 15
        assert signals_accepted <= 10  # Rate limit is 10 per minute

    def test_signal_statistics(self):
        """Test signal broadcasting statistics"""
        # Send several signals with unique IDs
        for i in range(3):
            signal = Signal(
                signal_id=f"stats_test_{i}",
                signal_type=SignalType.HELP_REQUEST,
                sender_id="agent1",
                message=f"Help request {i}",
                sender_position=(10.0, 10.0)
            )
            self.broadcaster.broadcast_signal(signal)

        # Get statistics
        stats = self.broadcaster.get_broadcast_statistics()

        assert stats["signals_sent"] >= 3
        assert stats["signals_delivered"] >= 0
        assert "delivery_rate" in stats
        assert "signal_types" in stats
        assert "top_senders" in stats

    def test_signal_data_payload(self):
        """Test signals with complex data payloads"""
        # Create signal with complex data
        trade_signal = create_trade_offer(
            "agent1", (10.0, 10.0),
            offering=[{"item": "wood", "quantity": 10}, {"item": "stone", "quantity": 5}],
            requesting=[{"item": "fish", "quantity": 8}]
        )

        self.broadcaster.broadcast_signal(trade_signal)

        # Verify agent2 received the signal with correct data
        assert len(self.agent2.received_signals) == 1
        received_signal = self.agent2.received_signals[0]

        assert "offering" in received_signal.data
        assert "requesting" in received_signal.data
        assert len(received_signal.data["offering"]) == 2
        assert received_signal.data["offering"][0]["item"] == "wood"

    def test_targeted_signals(self):
        """Test signals targeted to specific agents"""
        # Create targeted signal
        targeted_signal = create_trade_offer(
            "agent1", (10.0, 10.0),
            offering=[{"item": "wood", "quantity": 5}],
            requesting=[{"item": "fish", "quantity": 3}],
            target_agent="agent2"
        )

        self.broadcaster.broadcast_signal(targeted_signal)

        # Only agent2 should receive it (it's targeted)
        assert len(self.agent2.received_signals) == 1
        # But agent3 wouldn't receive it anyway due to range

        # Test targeting logic directly
        assert targeted_signal.is_targeted_to("agent2") is True
        assert targeted_signal.is_targeted_to("agent3") is False

    def test_signal_queue_management(self):
        """Test signal queue operations"""
        queue = SignalQueue("test_agent", max_size=3)

        # Add signals
        signals = [
            create_help_request("agent1", (10.0, 10.0)),
            create_resource_found("agent1", (10.0, 10.0), "wood", (12.0, 12.0)),
            Signal(
                signal_id="high_priority",
                signal_type=SignalType.DANGER_WARNING,
                sender_id="agent1",
                priority=SignalPriority.HIGH,
                sender_position=(10.0, 10.0)
            )
        ]

        for signal in signals:
            queue.add_signal(signal)

        # High priority signal should be first
        next_signal = queue.get_next_signal()
        assert next_signal.priority == SignalPriority.HIGH

        # Test queue info
        info = queue.get_queue_info()
        assert "total_signals" in info
        assert "by_priority" in info
        assert "by_type" in info

    def test_signal_system_with_agent_methods(self):
        """Test signal system through agent interface methods"""
        # Test creating and sending signal through agent
        signal = create_help_request("agent1", (10.0, 10.0))
        self.agent1.send_signal(signal)  # Agent stores the intent to send

        assert signal.sender_id == "agent1"
        assert signal.signal_type == SignalType.HELP_REQUEST

        # Test that agent processes received signals
        self.agent2.receive_signal(signal)
        assert len(self.agent2.received_signals) == 1

        # Test signal processing
        next_signal = self.agent2.get_next_signal()
        assert next_signal is not None
        assert next_signal.signal_id == signal.signal_id

    def test_broadcaster_error_handling(self):
        """Test error handling in signal broadcaster"""
        # Test invalid signal
        invalid_signal = Signal(
            signal_id="",  # Invalid empty ID
            signal_type=SignalType.HELP_REQUEST,
            sender_id="agent1",
            message="",  # Invalid empty message
            sender_position=(10.0, 10.0)
        )

        success = self.broadcaster.broadcast_signal(invalid_signal)
        assert success is False

        # Test signal from non-existent agent
        ghost_signal = Signal(
            signal_id="ghost_signal",
            signal_type=SignalType.HELP_REQUEST,
            sender_id="non_existent_agent",
            message="Help!",
            sender_position=(10.0, 10.0)
        )

        success = self.broadcaster.broadcast_signal(ghost_signal)
        assert success is False

    def test_signal_cleanup_process(self):
        """Test signal cleanup processes"""
        # Add some signals
        signal1 = create_help_request("agent1", (10.0, 10.0))
        signal2 = Signal(
            signal_id="short_lived",
            signal_type=SignalType.HELP_REQUEST,
            sender_id="agent1",
            message="Quick!",
            duration=0.01,
            sender_position=(10.0, 10.0)
        )

        self.broadcaster.broadcast_signal(signal1)
        self.broadcaster.broadcast_signal(signal2)

        initial_count = len(self.broadcaster.active_signals)
        assert initial_count >= 2

        # Wait for one signal to expire
        time.sleep(0.02)

        # Force cleanup
        self.broadcaster._cleanup_expired_signals()

        # Should have fewer active signals
        final_count = len(self.broadcaster.active_signals)
        assert final_count < initial_count

    def test_signal_range_calculation(self):
        """Test signal range calculation accuracy"""
        signal = create_help_request("agent1", (10.0, 10.0))

        # Test distance calculations
        assert signal.is_in_range_of(10.0, 10.0) is True  # Same position
        assert signal.is_in_range_of(15.0, 15.0) is True  # ~7 units away, within range
        assert signal.is_in_range_of(60.0, 60.0) is False  # ~70 units away, out of range

        # Test distance calculation
        distance = signal.get_distance_from(15.0, 15.0)
        expected_distance = ((15-10)**2 + (15-10)**2)**0.5  # ~7.07
        assert abs(distance - expected_distance) < 0.01


if __name__ == "__main__":
    pytest.main([__file__])