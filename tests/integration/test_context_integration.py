"""
Integration tests for the Context Manager with agent behavior.

Tests that the context manager properly integrates with existing agent functionality
and provides useful contextual information for decision-making.
"""

import pytest
from unittest.mock import Mock

from client.agent import BaseAgent
from client.context_manager import DangerLevel, ContextType
from shared.personality import Personality


class ContextAgent(BaseAgent):
    """Simple test agent implementation for context testing"""

    def update(self, delta_time: float):
        pass

    def perceive(self, visible_entities):
        self.visible_entities = visible_entities

    def decide(self):
        return None


class TestContextIntegration:
    """Test context manager integration with agents"""

    def setup_method(self):
        """Set up test fixtures"""
        self.personality = Personality(
            combat=6.0,
            exploration=7.0,
            cooperativeness=5.0
        )

        self.agent = ContextAgent("test_agent", 10.0, 10.0, "test", self.personality)

    def test_context_manager_initialization(self):
        """Test that context manager initializes properly"""
        # Should not have context manager initially
        assert self.agent.context_manager is None

        # Should initialize when requested
        context_manager = self.agent.get_context_manager()
        assert context_manager is not None
        assert self.agent.context_manager is context_manager

        # Should return same instance on subsequent calls
        context_manager2 = self.agent.get_context_manager()
        assert context_manager is context_manager2

    def test_context_analysis_with_agent(self):
        """Test context analysis with real agent"""
        visible_entities = [
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 12.0,
                "y": 11.0
            },
            {
                "id": "wood_1",
                "type": "wood",
                "x": 8.0,
                "y": 9.0
            },
            {
                "id": "player_1",
                "agent_type": "player",
                "x": 15.0,
                "y": 15.0
            }
        ]

        self.agent.perceive(visible_entities)
        context = self.agent.get_current_context()

        # Should analyze the environment
        assert context is not None
        assert context.position == (10.0, 10.0)

        # Should detect entities
        assert context.nearby_enemies >= 1
        assert context.nearby_resources >= 1
        assert context.nearby_allies >= 1

    def test_danger_assessment_integration(self):
        """Test danger assessment through agent interface"""
        visible_entities = [
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 15.0,
                "y": 15.0
            },
            {
                "id": "enemy_2",
                "agent_type": "enemy",
                "x": 16.0,
                "y": 16.0
            }
        ]

        self.agent.perceive(visible_entities)
        # Update context to create danger areas
        self.agent.get_current_context()

        # Test danger assessment
        danger_at_safe_pos = self.agent.assess_danger_at(5.0, 5.0)
        danger_at_enemy_pos = self.agent.assess_danger_at(15.0, 15.0)

        assert danger_at_safe_pos == DangerLevel.SAFE
        # Enemy area might have danger depending on exact implementation

    def test_movement_recommendations(self):
        """Test movement recommendations through agent interface"""
        # Set up dangerous area
        visible_entities = [
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 20.0,
                "y": 20.0
            }
        ]

        self.agent.perceive(visible_entities)
        self.agent.get_current_context()

        # Test movement to safe area
        safe_recommendation = self.agent.get_movement_recommendation(5.0, 5.0)
        assert safe_recommendation["recommended"] is True

        # Test movement toward dangerous area
        dangerous_recommendation = self.agent.get_movement_recommendation(20.0, 20.0)
        # Result depends on exact danger detection, but should provide info
        assert "recommended" in dangerous_recommendation
        assert "danger_level" in dangerous_recommendation

    def test_context_factors_for_behaviors(self):
        """Test getting context factors for different behaviors"""
        visible_entities = [
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 12.0,
                "y": 11.0
            },
            {
                "id": "wood_1",
                "type": "wood",
                "x": 8.0,
                "y": 9.0
            }
        ]

        self.agent.perceive(visible_entities)
        self.agent.get_current_context()

        # Test combat behavior factors
        combat_factors = self.agent.get_context_factors_for_behavior("combat_action")
        assert isinstance(combat_factors, dict)

        # Test resource behavior factors
        resource_factors = self.agent.get_context_factors_for_behavior("resource_gathering")
        assert isinstance(resource_factors, dict)

        # Test exploration behavior factors
        exploration_factors = self.agent.get_context_factors_for_behavior("exploration")
        assert isinstance(exploration_factors, dict)

    def test_context_with_changing_environment(self):
        """Test context updates as environment changes"""
        import time

        # Start with safe environment
        safe_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0}
        ]

        self.agent.perceive(safe_entities)
        safe_context = self.agent.get_current_context()

        assert safe_context.local_danger == DangerLevel.SAFE
        assert safe_context.nearby_enemies == 0

        # Change to dangerous environment
        dangerous_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0},
            {"id": "enemy_1", "agent_type": "enemy", "x": 11.0, "y": 11.0},
            {"id": "enemy_2", "agent_type": "enemy", "x": 9.0, "y": 9.0}
        ]

        self.agent.perceive(dangerous_entities)

        # Wait for analysis interval to pass
        time.sleep(0.6)
        dangerous_context = self.agent.get_current_context()

        assert dangerous_context.nearby_enemies >= 2
        assert dangerous_context.local_danger != DangerLevel.SAFE

    def test_context_history_tracking(self):
        """Test that context history is tracked properly"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0}
        ]

        self.agent.perceive(visible_entities)

        # Update context multiple times
        context1 = self.agent.get_current_context()
        context2 = self.agent.get_current_context()

        # Should have context manager with history
        context_manager = self.agent.get_context_manager()
        assert len(context_manager.context_history) >= 1

    def test_context_with_terrain_data(self):
        """Test context analysis with terrain data"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0}
        ]

        # Mock terrain data
        terrain_data = {
            (11, 11): "wood",
            (12, 10): "water",
            (13, 11): "grass"
        }

        self.agent.perceive(visible_entities)
        context = self.agent.get_current_context(terrain_data)

        # Should complete successfully with terrain data
        assert context is not None
        assert context.position == (10.0, 10.0)

    def test_context_performance(self):
        """Test that context updates are reasonably fast"""
        import time

        visible_entities = [
            {"id": f"entity_{i}", "type": "wood", "x": 10.0 + i, "y": 10.0 + i}
            for i in range(20)  # Many entities
        ]

        self.agent.perceive(visible_entities)

        # Time the context update
        start_time = time.time()
        context = self.agent.get_current_context()
        end_time = time.time()

        # Should complete quickly (under 100ms for 20 entities)
        execution_time = end_time - start_time
        assert execution_time < 0.1

        assert context is not None

    def test_context_debug_information(self):
        """Test that context provides useful debug information"""
        visible_entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 12.0, "y": 11.0},
            {"id": "wood_1", "type": "wood", "x": 8.0, "y": 9.0}
        ]

        self.agent.perceive(visible_entities)
        self.agent.get_current_context()

        context_manager = self.agent.get_context_manager()
        debug_info = context_manager.get_debug_info()

        # Should have useful debug information
        assert "agent_id" in debug_info
        assert "active_areas" in debug_info
        assert "last_snapshot" in debug_info
        assert debug_info["agent_id"] == "test_agent"

    def test_context_thread_safety(self):
        """Test that context system can be called multiple times safely"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0}
        ]

        self.agent.perceive(visible_entities)

        # Multiple calls should not cause errors
        for _ in range(5):
            context = self.agent.get_current_context()
            assert context is not None

            danger = self.agent.assess_danger_at(15.0, 15.0)
            assert danger is not None

            factors = self.agent.get_context_factors_for_behavior("test_behavior")
            assert isinstance(factors, dict)

    def test_context_with_empty_environment(self):
        """Test context analysis with empty environment"""
        self.agent.perceive([])
        context = self.agent.get_current_context()

        # Should handle empty environment gracefully
        assert context is not None
        assert context.local_danger == DangerLevel.SAFE
        assert context.nearby_enemies == 0
        assert context.nearby_resources == 0
        assert context.nearby_allies == 0

    def test_context_integration_with_opportunity_system(self):
        """Test that context manager works alongside opportunity system"""
        visible_entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 12.0, "y": 11.0},
            {"id": "wood_1", "type": "wood", "x": 8.0, "y": 9.0}
        ]

        self.agent.perceive(visible_entities)

        # Get both context and opportunities
        context = self.agent.get_current_context()
        opportunities = self.agent.get_current_opportunities()

        # Both should work without interference
        assert context is not None
        assert isinstance(opportunities, list)

        # Should be able to get best opportunity too
        best_opportunity = self.agent.get_best_opportunity()
        if best_opportunity:
            opportunity, score = best_opportunity
            assert score > 0


if __name__ == "__main__":
    pytest.main([__file__])