#!/usr/bin/env python3
"""
Pytest tests for Two-Phase Action System

Tests that the OOP solution eliminates distance validation errors
and provides reliable action execution.

Run with: pytest tests/test_two_phase_actions.py -v
"""

import pytest
import time
from unittest.mock import Mock, MagicMock
from typing import Tuple

# Import the classes we're testing
from client.behavior_tree.nodes.two_phase_action import (
    TwoPhaseActionNode, ResourceActionNode, ActionPhase
)
from client.behavior_tree.nodes.fishing_action import FishAtWater
from client.behavior_tree.nodes.wood_harvesting_action import HarvestWood
from client.behavior_tree.nodes.base import NodeStatus
from world.tiles import TileType


class TestTwoPhaseActionBase:
    """Test the base TwoPhaseActionNode functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.id = "test_agent_12345678"
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.speed = 5.0

    def test_distance_calculation(self):
        """Test distance calculation helper"""

        class TestAction(TwoPhaseActionNode):
            def find_action_target(self, agent): return (15.0, 10.0)
            def calculate_optimal_position(self, agent, target_pos): return (14.0, 10.0)
            def execute_action(self, agent, target_pos): return True
            def get_action_name(self): return "test"
            def get_resource_type(self): return "test"

        action = TestAction("TestAction")

        # Test distance calculation
        pos1 = (0.0, 0.0)
        pos2 = (3.0, 4.0)
        distance = action._distance(pos1, pos2)

        assert distance == 5.0  # 3-4-5 triangle

    def test_position_validation(self):
        """Test action position validation"""

        class TestAction(TwoPhaseActionNode):
            def find_action_target(self, agent): return (11.0, 10.0)
            def calculate_optimal_position(self, agent, target_pos): return (10.5, 10.0)
            def execute_action(self, agent, target_pos): return True
            def get_action_name(self): return "test"
            def get_resource_type(self): return "test"

        action = TestAction("TestAction", required_distance=1.2)
        action.target_position = (11.0, 10.0)

        # Agent at (10.0, 10.0), target at (11.0, 10.0) = distance 1.0
        assert action._validate_action_position(self.mock_agent) is True

        # Move agent further away
        self.mock_agent.x = 8.0  # Now distance is 3.0
        assert action._validate_action_position(self.mock_agent) is False

    def test_phase_progression(self):
        """Test that phases progress correctly"""

        class TestAction(TwoPhaseActionNode):
            def find_action_target(self, agent):
                return (12.0, 10.0)  # 2 units away

            def calculate_optimal_position(self, agent, target_pos):
                return (11.0, 10.0)  # 1 unit from target, 1 unit from agent

            def execute_action(self, agent, target_pos):
                return True

            def get_action_name(self): return "test"
            def get_resource_type(self): return "test"

        action = TestAction("TestAction", required_distance=1.5, positioning_tolerance=0.5)

        # Mock agent movement
        self.mock_agent.stop_movement = Mock()
        self.mock_agent.find_path_to = Mock(return_value=False)  # Force direct movement

        # Start action - should begin in PREPARATION phase
        result = action.start_action(self.mock_agent)
        assert result is True
        assert action.phase == ActionPhase.PREPARATION
        assert action.target_position == (12.0, 10.0)
        assert action.optimal_agent_position == (11.0, 10.0)

    def test_already_positioned_shortcut(self):
        """Test that already positioned agents skip to READY phase"""

        class TestAction(TwoPhaseActionNode):
            def find_action_target(self, agent):
                return (10.5, 10.0)  # Very close to agent

            def calculate_optimal_position(self, agent, target_pos):
                return (10.0, 10.0)  # Agent's current position

            def execute_action(self, agent, target_pos):
                return True

            def get_action_name(self): return "test"
            def get_resource_type(self): return "test"

        action = TestAction("TestAction", required_distance=1.0, positioning_tolerance=0.1)
        self.mock_agent.stop_movement = Mock()

        # Start action - should skip directly to READY
        result = action.start_action(self.mock_agent)
        assert result is True
        assert action.phase == ActionPhase.READY


class TestResourceActionNode:
    """Test ResourceActionNode functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.id = "test_agent_12345678"
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.speed = 5.0

        # Mock agent map
        self.mock_agent.agent_map = Mock()

    def test_resource_target_finding(self):
        """Test that ResourceActionNode finds nearest resources correctly"""

        # Mock map that has water at multiple locations
        def mock_is_tile_known(x, y):
            return True

        def mock_get_tile_type(x, y):
            if (x, y) in [(12, 10), (15, 10)]:  # Water at distance 2 and 5
                return TileType.WATER
            return TileType.GRASS

        self.mock_agent.agent_map.is_tile_known = mock_is_tile_known
        self.mock_agent.agent_map.get_tile_type = mock_get_tile_type

        action = ResourceActionNode("TestResource", TileType.WATER, max_search_distance=10.0)

        target = action.find_action_target(self.mock_agent)

        # Should find the closer water tile (12, 10) -> (12.5, 10.5)
        assert target == (12.5, 10.5)

    def test_optimal_position_calculation(self):
        """Test optimal position calculation for resources"""

        action = ResourceActionNode("TestResource", TileType.WATER, max_search_distance=10.0)
        action.required_distance = 1.0

        # Mock position validation to always return True
        action._is_position_valid = Mock(return_value=True)

        # Agent at (10, 10), target at (15, 10)
        target_pos = (15.0, 10.0)

        optimal = action.calculate_optimal_position(self.mock_agent, target_pos)

        # Should position agent 1.0 unit away from target
        # Direction: (10-15, 10-10) = (-5, 0), normalized = (-1, 0)
        # Optimal: (15, 10) + (-1, 0) * 1.0 = (14, 10)
        assert optimal == (14.0, 10.0)

    def test_position_validation_fallback(self):
        """Test that invalid positions trigger alternative positioning"""

        action = ResourceActionNode("TestResource", TileType.WATER, max_search_distance=10.0)
        action.required_distance = 1.0

        # Mock position validation - first position invalid, second valid
        validation_calls = [False, True]  # First call fails, second succeeds
        action._is_position_valid = Mock(side_effect=validation_calls)

        target_pos = (15.0, 10.0)
        optimal = action.calculate_optimal_position(self.mock_agent, target_pos)

        # Should have tried alternative positions
        assert action._is_position_valid.call_count >= 2


class TestFishingActionIntegration:
    """Test the updated FishAtWater action"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.id = "fisher_agent_12345678"
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.speed = 5.0
        self.mock_agent.agent_type = "explorer"
        self.mock_agent.stop_movement = Mock()

        # Mock agent map with water
        self.mock_agent.agent_map = Mock()

        def mock_is_tile_known(x, y):
            return True

        def mock_get_tile_type(x, y):
            if x == 12 and y == 10:  # Water 2 units away
                return TileType.WATER
            return TileType.GRASS

        self.mock_agent.agent_map.is_tile_known = mock_is_tile_known
        self.mock_agent.agent_map.get_tile_type = mock_get_tile_type

    def test_fishing_inheritance_behavior(self):
        """Test that FishAtWater properly uses ResourceActionNode"""

        fish_action = FishAtWater(max_distance=5.0)

        # Verify it inherited correctly
        assert isinstance(fish_action, ResourceActionNode)
        assert fish_action.resource_tile_type == TileType.WATER
        assert fish_action.get_action_name() == "fishing"
        assert fish_action.get_resource_type() == "water"

    def test_fishing_target_finding(self):
        """Test fishing target finding"""

        fish_action = FishAtWater(max_distance=5.0)

        target = fish_action.find_action_target(self.mock_agent)

        # Should find water at (12.5, 10.5)
        assert target == (12.5, 10.5)

    def test_fishing_execution_call(self):
        """Test that fishing execution is called correctly"""

        fish_action = FishAtWater(max_distance=5.0)

        # Mock the internal fishing request method
        fish_action._request_fishing = Mock()
        fish_action._has_fishing_rod = Mock(return_value=True)

        # Execute action
        result = fish_action.execute_action(self.mock_agent, (12.5, 10.5))

        assert result is True
        fish_action._request_fishing.assert_called_once_with(self.mock_agent, 12.5, 10.5)


class TestWoodHarvestingIntegration:
    """Test the updated HarvestWood action"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.id = "woodcutter_agent_12345678"
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.speed = 5.0
        self.mock_agent.stop_movement = Mock()
        self.mock_agent.agent_type = "woodcutter"

        # Mock inventory with hatchet for wood harvesting
        self.mock_agent.inventory = Mock()
        from shared.items import create_hatchet
        hatchet = create_hatchet()
        self.mock_agent.inventory.get_items_by_type = Mock(return_value=[hatchet])

        # Mock agent map with wood
        self.mock_agent.agent_map = Mock()

        def mock_is_tile_known(x, y):
            return True

        def mock_get_tile_type(x, y):
            if x == 13 and y == 10:  # Wood 3 units away
                return TileType.WOOD
            return TileType.GRASS

        self.mock_agent.agent_map.is_tile_known = mock_is_tile_known
        self.mock_agent.agent_map.get_tile_type = mock_get_tile_type

    def test_wood_harvesting_inheritance(self):
        """Test that HarvestWood properly uses ResourceActionNode"""

        harvest_action = HarvestWood(max_distance=5.0)

        # Verify inheritance
        assert isinstance(harvest_action, ResourceActionNode)
        assert harvest_action.resource_tile_type == TileType.WOOD
        assert harvest_action.get_action_name() == "wood_harvesting"
        assert harvest_action.get_resource_type() == "wood"

    def test_wood_target_finding(self):
        """Test wood target finding"""

        harvest_action = HarvestWood(max_distance=5.0)

        target = harvest_action.find_action_target(self.mock_agent)

        # Should find wood at (13.5, 10.5)
        assert target == (13.5, 10.5)

    def test_wood_execution_call(self):
        """Test wood harvesting execution"""

        harvest_action = HarvestWood(max_distance=5.0)

        # Mock the internal harvesting request method
        harvest_action._request_wood_harvest = Mock()

        # Execute action
        result = harvest_action.execute_action(self.mock_agent, (13.5, 10.5))

        assert result is True
        harvest_action._request_wood_harvest.assert_called_once_with(self.mock_agent, 13.5, 10.5)


def test_integration_eliminates_distance_errors():
    """Integration test - verify the system eliminates distance validation errors"""

    # This test simulates the original problem scenario
    mock_agent = Mock()
    mock_agent.id = "problem_agent_12345678"
    mock_agent.x = 5.0  # Agent starts far from resource
    mock_agent.y = 5.0
    mock_agent.speed = 5.0
    mock_agent.stop_movement = Mock()
    mock_agent.find_path_to = Mock(return_value=False)  # Force direct movement

    # Mock agent map with water at distance > 1.5 (the old failure case)
    mock_agent.agent_map = Mock()

    def mock_is_tile_known(x, y):
        return True

    def mock_get_tile_type(x, y):
        if x == 10 and y == 10:  # Water at distance ~7 units (would fail old system)
            return TileType.WATER
        return TileType.GRASS

    mock_agent.agent_map.is_tile_known = mock_is_tile_known
    mock_agent.agent_map.get_tile_type = mock_get_tile_type

    # Create fishing action
    fish_action = FishAtWater(max_distance=10.0)

    # Start the action
    result = fish_action.start_action(mock_agent)

    # Should succeed even with large initial distance
    assert result is True
    assert fish_action.phase == ActionPhase.PREPARATION
    assert fish_action.target_position == (10.5, 10.5)

    # The optimal position should be exactly 1.0 unit from target
    optimal_pos = fish_action.optimal_agent_position
    assert optimal_pos is not None

    target_pos = fish_action.target_position
    distance = ((target_pos[0] - optimal_pos[0]) ** 2 + (target_pos[1] - optimal_pos[1]) ** 2) ** 0.5

    # Distance should be exactly the required distance (1.0)
    assert abs(distance - 1.0) < 0.1

    print(f"✅ Integration test passed: Agent will be positioned at distance {distance:.2f} from target")
    print(f"   This eliminates the 'distance to target: 4.47 > 1.5 limit' errors!")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])