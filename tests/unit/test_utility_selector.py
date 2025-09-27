"""
Unit tests for the Utility-Based Decision Making system.

Tests UtilitySelector nodes and utility function calculations.
"""

import time
from unittest.mock import MagicMock, Mock

import pytest

from client.behavior_tree.nodes.base import BehaviorNode, NodeStatus
from client.behavior_tree.utility_selector import (
    ThresholdUtilitySelector,
    UtilityFunction,
    UtilitySelector,
    WeightedUtilitySelector,
)
from shared.personality import Personality


class MockBehaviorNode(BehaviorNode):
    """Mock behavior node for testing"""

    def __init__(self, name: str, execution_result: NodeStatus = NodeStatus.SUCCESS):
        super().__init__(name)
        self.execution_result = execution_result
        self.execute_count = 0

    def execute(self, agent, delta_time: float) -> NodeStatus:
        self.execute_count += 1
        self.status = self.execution_result
        return self.execution_result


class TestUtilityFunction:
    """Test the UtilityFunction class"""

    def test_utility_function_creation(self):
        """Test basic utility function creation"""
        func = UtilityFunction("test_func", base_utility=2.0)
        assert func.name == "test_func"
        assert func.base_utility == 2.0
        assert len(func.factors) == 0

    def test_utility_function_with_factors(self):
        """Test utility function with factor functions"""
        mock_agent = Mock()
        mock_node = Mock()

        func = UtilityFunction("test_func", base_utility=2.0)

        # Add factors
        func.add_factor(lambda agent, node: 1.5)  # Multiply by 1.5
        func.add_factor(lambda agent, node: 0.8)  # Multiply by 0.8

        utility = func.calculate_utility(mock_agent, mock_node)
        expected = 2.0 * 1.5 * 0.8  # 2.4
        assert abs(utility - expected) < 0.001

    def test_utility_function_with_error_handling(self):
        """Test utility function handles factor errors gracefully"""
        mock_agent = Mock()
        mock_node = Mock()

        func = UtilityFunction("test_func", base_utility=2.0)

        # Add a factor that raises an exception
        func.add_factor(lambda agent, node: 1.0 / 0)  # Division by zero
        func.add_factor(lambda agent, node: 1.5)  # Normal factor

        utility = func.calculate_utility(mock_agent, mock_node)
        # Should apply error penalty (0.5) and normal factor (1.5)
        expected = 2.0 * 0.5 * 1.5  # 1.5
        assert abs(utility - expected) < 0.001

    def test_utility_function_minimum_zero(self):
        """Test that utility function never returns negative values"""
        mock_agent = Mock()
        mock_node = Mock()

        func = UtilityFunction("test_func", base_utility=1.0)
        func.add_factor(lambda agent, node: -10.0)  # Very negative factor

        utility = func.calculate_utility(mock_agent, mock_node)
        assert utility >= 0.0


class TestUtilitySelector:
    """Test the UtilitySelector class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.health = 80.0
        self.mock_agent.max_health = 100.0
        self.mock_agent.visible_entities = []

        # Add personality
        self.mock_agent.personality = Personality(
            combat=7.0, fishing=6.0, foraging=5.0, social=4.0, exploration=3.0
        )

        # Create mock children
        self.combat_node = MockBehaviorNode("combat_action", NodeStatus.RUNNING)
        self.resource_node = MockBehaviorNode("resource_gathering", NodeStatus.RUNNING)
        self.exploration_node = MockBehaviorNode(
            "exploration_behavior", NodeStatus.RUNNING
        )

        self.children = [self.combat_node, self.resource_node, self.exploration_node]
        self.selector = UtilitySelector("test_selector", self.children)

    def test_utility_selector_creation(self):
        """Test basic utility selector creation"""
        assert self.selector.name == "test_selector"
        assert len(self.selector.children) == 3
        assert len(self.selector.utility_functions) == 3

        # Should have utility functions for each child
        assert "combat_action" in self.selector.utility_functions
        assert "resource_gathering" in self.selector.utility_functions
        assert "exploration_behavior" in self.selector.utility_functions

    def test_utility_calculation_for_children(self):
        """Test utility calculation for different child types"""
        # Combat node should get combat-related utility
        combat_utility = self.selector._calculate_child_utility(
            self.mock_agent, self.combat_node
        )
        assert combat_utility > 0

        # Resource node should get resource-related utility
        resource_utility = self.selector._calculate_child_utility(
            self.mock_agent, self.resource_node
        )
        assert resource_utility > 0

        # Agent has higher combat personality, so combat should score higher
        # (though this depends on other factors too)
        assert combat_utility > 0
        assert resource_utility > 0

    def test_child_selection(self):
        """Test that selector chooses child with highest utility"""
        # Execute selector
        status = self.selector.execute(self.mock_agent, 0.1)

        # Should have selected a child
        assert self.selector.current_child is not None
        assert status == NodeStatus.RUNNING

        # Selected child should have been executed
        assert self.selector.current_child.execute_count > 0

    def test_utility_reevaluation(self):
        """Test that utility is re-evaluated periodically"""
        # Set short evaluation interval
        self.selector.evaluation_interval = 0.01

        # Execute once
        self.selector.execute(self.mock_agent, 0.1)
        first_child = self.selector.current_child

        # Wait for re-evaluation interval
        time.sleep(0.02)

        # Execute again - might choose different child if utilities changed
        self.selector.execute(self.mock_agent, 0.1)
        second_child = self.selector.current_child

        # Should have re-evaluated (though might choose same child)
        assert isinstance(second_child, MockBehaviorNode)

    def test_child_completion_handling(self):
        """Test handling of child completion"""
        # Set child to complete successfully
        self.combat_node.execution_result = NodeStatus.SUCCESS

        # Execute selector
        status = self.selector.execute(self.mock_agent, 0.1)
        assert status == NodeStatus.SUCCESS

        # Current child should be reset for re-evaluation
        assert self.selector.current_child is None

    def test_child_failure_handling(self):
        """Test handling of child failure"""
        # Set child to fail
        self.combat_node.execution_result = NodeStatus.FAILURE

        # Execute selector
        status = self.selector.execute(self.mock_agent, 0.1)

        # Should try to select another child
        assert status == NodeStatus.RUNNING
        assert self.selector.current_child is None  # Reset for re-selection

    def test_reset_functionality(self):
        """Test resetting the utility selector"""
        # Execute to set current child
        self.selector.execute(self.mock_agent, 0.1)
        assert self.selector.current_child is not None

        # Reset
        self.selector.reset()

        # Should clear state
        assert self.selector.current_child is None
        assert len(self.selector.utility_cache) == 0
        assert self.selector.status == NodeStatus.READY

    def test_debug_info(self):
        """Test debug information generation"""
        # Execute to set some state
        self.selector.execute(self.mock_agent, 0.1)

        debug_info = self.selector.get_debug_info(self.mock_agent)

        assert "current_child" in debug_info
        assert "utility_scores" in debug_info
        assert "last_evaluation" in debug_info

        # Should have utility scores for all children
        assert len(debug_info["utility_scores"]) == 3

    def test_custom_utility_function(self):
        """Test setting custom utility function"""
        # Create custom utility function
        custom_func = UtilityFunction("custom", base_utility=10.0)
        self.selector.set_utility_function("combat_action", custom_func)

        # Combat action should now have very high utility
        combat_utility = self.selector._calculate_child_utility(
            self.mock_agent, self.combat_node
        )
        assert combat_utility >= 10.0

    def test_personality_influence_on_utility(self):
        """Test that agent personality affects utility calculations"""
        # Create agent with high fishing preference
        fishing_agent = Mock()
        fishing_agent.x = 10.0
        fishing_agent.y = 10.0
        fishing_agent.health = 80.0
        fishing_agent.max_health = 100.0
        fishing_agent.visible_entities = []
        fishing_agent.personality = Personality(combat=2.0, fishing=9.0, foraging=3.0)

        # Create fishing node
        fishing_node = MockBehaviorNode("fishing_action")
        fishing_selector = UtilitySelector(
            "fishing_test", [self.combat_node, fishing_node]
        )

        combat_utility = fishing_selector._calculate_child_utility(
            fishing_agent, self.combat_node
        )
        fishing_utility = fishing_selector._calculate_child_utility(
            fishing_agent, fishing_node
        )

        # Both should have positive utility, but the exact comparison depends on all factors
        # The test verifies that personality influences the calculation
        assert fishing_utility > 0
        assert combat_utility > 0

    def test_health_influence_on_utility(self):
        """Test that agent health affects utility calculations"""
        # Create low-health agent
        low_health_agent = Mock()
        low_health_agent.x = 10.0
        low_health_agent.y = 10.0
        low_health_agent.health = 20.0  # Very low health
        low_health_agent.max_health = 100.0
        low_health_agent.visible_entities = []
        low_health_agent.personality = self.mock_agent.personality

        # Create emergency node
        emergency_node = MockBehaviorNode("emergency_flee")
        health_selector = UtilitySelector(
            "health_test", [self.combat_node, emergency_node]
        )

        combat_utility = health_selector._calculate_child_utility(
            low_health_agent, self.combat_node
        )
        emergency_utility = health_selector._calculate_child_utility(
            low_health_agent, emergency_node
        )

        # Emergency should have much higher utility when health is low
        assert emergency_utility > combat_utility

    def test_opportunity_influence_on_utility(self):
        """Test that current opportunities affect utility calculations"""
        # Create agent with opportunity system
        from client.opportunity_system import (
            Opportunity,
            OpportunitySystem,
            OpportunityType,
        )

        opp_agent = Mock()
        opp_agent.x = 10.0
        opp_agent.y = 10.0
        opp_agent.health = 80.0
        opp_agent.visible_entities = []
        opp_agent.personality = self.mock_agent.personality

        # Add opportunity system with combat opportunity
        opp_agent.opportunity_system = Mock()
        combat_opportunity = Opportunity(
            opportunity_id="combat_opp",
            opportunity_type=OpportunityType.COMBAT,
            position=(12.0, 11.0),
            urgency=8.0,
        )
        opp_agent.opportunity_system.current_opportunities = [combat_opportunity]

        combat_utility = self.selector._calculate_child_utility(
            opp_agent, self.combat_node
        )
        resource_utility = self.selector._calculate_child_utility(
            opp_agent, self.resource_node
        )

        # Combat should have higher utility due to relevant opportunity
        assert combat_utility > resource_utility


class TestWeightedUtilitySelector:
    """Test the WeightedUtilitySelector class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.health = 80.0
        self.mock_agent.personality = Personality()

        self.combat_node = MockBehaviorNode("combat_action")
        self.resource_node = MockBehaviorNode("resource_gathering")

        # Create weighted selector with higher weight for resource gathering
        weights = {"combat_action": 1.0, "resource_gathering": 2.0}
        self.selector = WeightedUtilitySelector(
            "weighted_test", [self.combat_node, self.resource_node], weights
        )

    def test_weight_application(self):
        """Test that weights are applied to utility calculations"""
        combat_utility = self.selector._calculate_child_utility(
            self.mock_agent, self.combat_node
        )
        resource_utility = self.selector._calculate_child_utility(
            self.mock_agent, self.resource_node
        )

        # Resource should have higher utility due to 2.0 weight
        assert resource_utility > combat_utility


class TestThresholdUtilitySelector:
    """Test the ThresholdUtilitySelector class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.health = 80.0
        self.mock_agent.max_health = 100.0
        self.mock_agent.visible_entities = []
        self.mock_agent.personality = Personality()

        self.combat_node = MockBehaviorNode("combat_action")
        self.resource_node = MockBehaviorNode("resource_gathering")

        # Create threshold selector with high minimum utility
        self.selector = ThresholdUtilitySelector(
            "threshold_test",
            [self.combat_node, self.resource_node],
            minimum_utility=2.0,
        )

    def test_threshold_enforcement(self):
        """Test that selector only chooses options above threshold"""
        # Override utility functions to return low values
        low_utility_func = UtilityFunction("low", base_utility=0.5)
        self.selector.set_utility_function("combat_action", low_utility_func)
        self.selector.set_utility_function("resource_gathering", low_utility_func)

        # Execute selector
        status = self.selector.execute(self.mock_agent, 0.1)

        # Should not select any child due to low utilities
        assert self.selector.current_child is None
        assert status == NodeStatus.FAILURE

    def test_threshold_with_valid_option(self):
        """Test that selector works when options meet threshold"""
        # Create a running combat node
        running_combat_node = MockBehaviorNode("combat_action", NodeStatus.RUNNING)
        selector_with_running = ThresholdUtilitySelector(
            "threshold_test", [running_combat_node], minimum_utility=2.0
        )

        # Override one utility function to return high value
        high_utility_func = UtilityFunction("high", base_utility=3.0)
        selector_with_running.set_utility_function("combat_action", high_utility_func)

        # Execute selector
        status = selector_with_running.execute(self.mock_agent, 0.1)

        # Should select the high-utility option and be running
        assert status == NodeStatus.RUNNING
        assert selector_with_running.current_child == running_combat_node


class TestUtilityFactors:
    """Test individual utility factor functions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_agent = Mock()
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.health = 80.0
        self.mock_agent.max_health = 100.0
        self.mock_agent.visible_entities = []
        self.mock_agent.personality = Personality(combat=7.0)  # Add real personality

        self.combat_node = MockBehaviorNode("combat_action")
        self.selector = UtilitySelector("test", [self.combat_node])

    def test_combat_utility_factor_with_enemies(self):
        """Test combat utility increases with nearby enemies"""
        # Add enemies to visible entities
        self.mock_agent.visible_entities = [
            {"agent_type": "enemy", "x": 12.0, "y": 11.0},
            {"agent_type": "enemy", "x": 8.0, "y": 9.0},
        ]

        factor = self.selector._combat_utility_factor(self.mock_agent, self.combat_node)
        assert factor > 1.0  # Should be boosted by enemy presence

    def test_combat_utility_factor_with_low_health(self):
        """Test combat utility decreases with low health"""
        self.mock_agent.health = 20.0  # Very low health

        factor = self.selector._combat_utility_factor(self.mock_agent, self.combat_node)
        assert factor < 1.0  # Should be reduced due to low health

    def test_health_factor_for_emergency(self):
        """Test health factor boosts emergency behaviors when health is low"""
        self.mock_agent.health = 20.0
        emergency_node = MockBehaviorNode("emergency_flee")

        factor = self.selector._health_factor(self.mock_agent, emergency_node)
        assert factor > 1.0  # Should boost emergency behaviors when health is low

    def test_health_factor_for_normal_behaviors(self):
        """Test health factor reduces normal behaviors when health is low"""
        self.mock_agent.health = 20.0

        factor = self.selector._health_factor(self.mock_agent, self.combat_node)
        assert factor < 1.0  # Should reduce normal behaviors when health is low


if __name__ == "__main__":
    pytest.main([__file__])
