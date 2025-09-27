"""
Unit tests for action validation system

These tests focus on individual validators in isolation for speed and precision.
"""

import pytest
import time
from unittest.mock import MagicMock

from server.action_processor import (
    ActionContext, RateLimitValidator, CooldownValidator,
    MovementValidator, CombatValidator, FishingValidator
)
from shared.actions import ActionRequest, ActionType
from tests.fixtures.mock_server import MockWorld, MockGameServer
from tests.fixtures.test_maps import TestMaps
from world.tiles import TileType


class TestRateLimitValidator:
    """Test rate limiting validation"""

    def test_allows_normal_rate(self):
        """Should allow actions within rate limits"""
        validator = RateLimitValidator(actions_per_second=5.0, burst_size=3)
        context = MagicMock()

        request = ActionRequest(
            action_id="test1",
            agent_id="agent1",
            action_type=ActionType.MOVE_TO,
            parameters={}
        )

        # First few actions should pass
        for i in range(3):
            is_valid, message = validator.validate(request, context)
            assert is_valid, f"Action {i+1} should be valid"
            assert message == ""

    def test_blocks_excessive_rate(self):
        """Should block actions exceeding burst rate"""
        validator = RateLimitValidator(actions_per_second=5.0, burst_size=2)
        context = MagicMock()

        request = ActionRequest(
            action_id="test1",
            agent_id="agent1",
            action_type=ActionType.MOVE_TO,
            parameters={}
        )

        # First 2 should pass
        for i in range(2):
            is_valid, message = validator.validate(request, context)
            assert is_valid, f"Action {i+1} should be valid within burst"

        # Third should fail
        is_valid, message = validator.validate(request, context)
        assert not is_valid, "Third action should be rate limited"
        assert "Rate limit exceeded" in message

    def test_different_agents_separate_limits(self):
        """Different agents should have separate rate limits"""
        validator = RateLimitValidator(actions_per_second=2.0, burst_size=1)
        context = MagicMock()

        request1 = ActionRequest(
            action_id="test1", agent_id="agent1",
            action_type=ActionType.MOVE_TO, parameters={}
        )
        request2 = ActionRequest(
            action_id="test2", agent_id="agent2",
            action_type=ActionType.MOVE_TO, parameters={}
        )

        # Both agents should be able to make their first action
        is_valid1, _ = validator.validate(request1, context)
        is_valid2, _ = validator.validate(request2, context)

        assert is_valid1, "Agent 1 first action should be valid"
        assert is_valid2, "Agent 2 first action should be valid"

        # Both agents' second action should be blocked
        is_valid1, msg1 = validator.validate(request1, context)
        is_valid2, msg2 = validator.validate(request2, context)

        assert not is_valid1, "Agent 1 second action should be blocked"
        assert not is_valid2, "Agent 2 second action should be blocked"


class TestCooldownValidator:
    """Test action cooldown validation"""

    def test_respects_cooldowns(self):
        """Should enforce action cooldowns"""
        validator = CooldownValidator()
        context = MagicMock()

        request = ActionRequest(
            action_id="test1",
            agent_id="agent1",
            action_type=ActionType.ATTACK_TARGET,
            parameters={}
        )

        # First action should pass
        is_valid, message = validator.validate(request, context)
        assert is_valid, "First action should be valid"

        # Immediate second action should fail
        is_valid, message = validator.validate(request, context)
        assert not is_valid, "Second action should be on cooldown"
        assert "cooldown" in message.lower()

    def test_different_action_types_separate_cooldowns(self):
        """Different action types should have separate cooldowns"""
        validator = CooldownValidator()
        context = MagicMock()

        attack_request = ActionRequest(
            action_id="attack", agent_id="agent1",
            action_type=ActionType.ATTACK_TARGET, parameters={}
        )
        move_request = ActionRequest(
            action_id="move", agent_id="agent1",
            action_type=ActionType.MOVE_TO, parameters={}
        )

        # Attack action
        is_valid, _ = validator.validate(attack_request, context)
        assert is_valid, "First attack should be valid"

        # Move action should still work (different cooldown)
        is_valid, _ = validator.validate(move_request, context)
        assert is_valid, "Move action should be valid (separate cooldown)"

    def test_no_cooldown_for_unconfigured_actions(self):
        """Actions without configured cooldowns should always pass"""
        validator = CooldownValidator()
        context = MagicMock()

        # Use an action type that's not in the cooldowns dict
        request = ActionRequest(
            action_id="test", agent_id="agent1",
            action_type=ActionType.QUERY_INVENTORY, parameters={}
        )

        # Should pass multiple times since no cooldown configured
        for i in range(5):
            is_valid, message = validator.validate(request, context)
            assert is_valid, f"Unconfigured action {i+1} should always be valid"
            assert message == ""


class TestMovementValidator:
    """Test movement validation"""

    def setup_method(self):
        """Set up test fixtures"""
        self.world = MockWorld(20, 20)
        self.context = MagicMock()
        self.context.world = self.world
        self.validator = MovementValidator()

        # Add a test agent
        self.agent_id = self.world.spawn_agent("player", 10, 10)

    def test_validates_basic_movement(self):
        """Should validate basic movement within bounds"""
        request = ActionRequest(
            action_id="move1",
            agent_id=self.agent_id,
            action_type=ActionType.MOVE_TO,
            parameters={"target_x": 15.0, "target_y": 15.0}
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert is_valid, f"Valid movement should pass: {message}"

    def test_rejects_out_of_bounds(self):
        """Should reject movement outside world bounds"""
        request = ActionRequest(
            action_id="move1",
            agent_id=self.agent_id,
            action_type=ActionType.MOVE_TO,
            parameters={"target_x": 25.0, "target_y": 15.0}  # X out of bounds
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert not is_valid, "Out of bounds movement should be rejected"
        assert "out of bounds" in message.lower()

    def test_rejects_dead_agent_movement(self):
        """Should reject movement from dead agents"""
        agent = self.world.get_agent(self.agent_id)
        agent.is_alive = False

        request = ActionRequest(
            action_id="move1",
            agent_id=self.agent_id,
            action_type=ActionType.MOVE_TO,
            parameters={"target_x": 12.0, "target_y": 12.0}
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert not is_valid, "Dead agent movement should be rejected"
        assert "dead" in message.lower()

    def test_ignores_non_movement_actions(self):
        """Should ignore actions that aren't movement related"""
        request = ActionRequest(
            action_id="attack1",
            agent_id=self.agent_id,
            action_type=ActionType.ATTACK_TARGET,
            parameters={"target_id": "other_agent"}
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert is_valid, "Non-movement actions should pass through"
        assert message == ""


class TestFishingValidator:
    """Test fishing action validation"""

    def setup_method(self):
        """Set up test environment with fishing pond"""
        # Create world with water for fishing
        terrain = TestMaps.get_fishing_pond(25, 25)
        self.world = MockWorld(25, 25)
        self.world.terrain = terrain

        # Mock world map for validator
        world_map = MagicMock()
        world_map.width = 25
        world_map.height = 25
        world_map.get_tile = lambda x, y: terrain.get((x, y), TileType.WALL)
        self.world.world_map = world_map

        self.context = MagicMock()
        self.context.world = self.world

        # Mock agent registry
        agent_registry = MagicMock()
        agent_state = MagicMock()
        agent_state.position = (12, 12)  # Near water
        agent_state.is_alive = True

        # Mock inventory with fishing rod
        inventory = MagicMock()
        fishing_rod = MagicMock()
        fishing_rod.tool_type = "fishing"
        inventory.get_items_by_type.return_value = [fishing_rod]
        agent_state.inventory = inventory

        agent_registry.get_agent.return_value = agent_state
        self.context.agent_registry = agent_registry

        self.validator = FishingValidator()

    def test_allows_fishing_at_water(self):
        """Should allow fishing at water tiles"""
        request = ActionRequest(
            action_id="fish1",
            agent_id="agent1",
            action_type=ActionType.FISH,
            parameters={"target_x": 12, "target_y": 12}  # Water tile in test map
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert is_valid, f"Fishing at water should be valid: {message}"

    def test_rejects_fishing_on_land(self):
        """Should reject fishing on non-water tiles"""
        request = ActionRequest(
            action_id="fish1",
            agent_id="agent1",
            action_type=ActionType.FISH,
            parameters={"target_x": 2, "target_y": 2}  # Land tile
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert not is_valid, "Fishing on land should be rejected"
        assert "fishing" in message.lower()

    def test_rejects_fishing_without_rod(self):
        """Should reject fishing without fishing equipment"""
        # Remove fishing rod from inventory
        agent_state = self.context.agent_registry.get_agent.return_value
        agent_state.inventory.get_items_by_type.return_value = []

        request = ActionRequest(
            action_id="fish1",
            agent_id="agent1",
            action_type=ActionType.FISH,
            parameters={"target_x": 12, "target_y": 12}
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert not is_valid, "Fishing without rod should be rejected"
        assert "fishing rod" in message.lower()

    def test_ignores_non_fishing_actions(self):
        """Should ignore actions that aren't fishing"""
        request = ActionRequest(
            action_id="move1",
            agent_id="agent1",
            action_type=ActionType.MOVE_TO,
            parameters={"target_x": 10, "target_y": 10}
        )

        is_valid, message = self.validator.validate(request, self.context)
        assert is_valid, "Non-fishing actions should pass through"
        assert message == ""


@pytest.mark.asyncio
class TestActionContext:
    """Test action context creation and usage"""

    async def test_context_provides_access_to_components(self):
        """Action context should provide access to all needed components"""
        server = MockGameServer()
        context = ActionContext(server)

        assert context.processor is server
        assert context.world is server.world
        assert context.agent_registry is server.agent_registry
        assert context.start_time > 0


if __name__ == "__main__":
    # Run tests quickly for development
    pytest.main([__file__, "-v", "--tb=short", "-x"])