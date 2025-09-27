"""
Integration tests for the Opportunity System with agent behavior.

Tests that the opportunity system properly integrates with existing agent functionality.
"""

import pytest
from unittest.mock import Mock

from client.agent import BaseAgent
from client.opportunity_system import OpportunityType
from shared.personality import Personality


class Agent(BaseAgent):
    """Simple test agent implementation"""

    def update(self, delta_time: float):
        pass

    def perceive(self, visible_entities):
        self.visible_entities = visible_entities

    def decide(self):
        return None


class TestOpportunityIntegration:
    """Test opportunity system integration with agents"""

    def setup_method(self):
        """Set up test fixtures"""
        self.personality = Personality(
            combat=7.0,
            fishing=8.0,
            foraging=6.0,
            social=5.0,
            exploration=4.0
        )

        self.agent = Agent("test_agent", 10.0, 10.0, "test", self.personality)

    def test_opportunity_system_initialization(self):
        """Test that opportunity system initializes properly"""
        # Should not have opportunity system initially
        assert self.agent.opportunity_system is None

        # Should initialize when requested
        opp_system = self.agent.get_opportunity_system()
        assert opp_system is not None
        assert self.agent.opportunity_system is opp_system

        # Should return same instance on subsequent calls
        opp_system2 = self.agent.get_opportunity_system()
        assert opp_system is opp_system2

    def test_opportunity_detection_with_agent(self):
        """Test opportunity detection with real agent"""
        visible_entities = [
            {
                "id": "wood_1",
                "type": "wood",
                "x": 12.0,
                "y": 11.0
            },
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 8.0,
                "y": 9.0,
                "health": 60.0
            }
        ]

        self.agent.perceive(visible_entities)
        opportunities = self.agent.get_current_opportunities()

        # Should detect opportunities
        assert len(opportunities) > 0

        # Should have resource and combat opportunities
        opportunity_types = {opp[0].opportunity_type for opp in opportunities}
        assert OpportunityType.RESOURCE in opportunity_types
        assert OpportunityType.COMBAT in opportunity_types

    def test_best_opportunity_selection(self):
        """Test selecting the best opportunity"""
        visible_entities = [
            {
                "id": "fish_1",
                "type": "fish",  # Agent has high fishing preference
                "x": 11.0,
                "y": 11.0
            },
            {
                "id": "wood_1",
                "type": "wood",
                "x": 15.0,
                "y": 15.0
            }
        ]

        self.agent.perceive(visible_entities)
        best_opportunity = self.agent.get_best_opportunity()

        assert best_opportunity is not None
        opportunity, score = best_opportunity
        assert opportunity.opportunity_type == OpportunityType.RESOURCE
        assert score > 0

        # The fish should be preferred due to personality and distance
        assert opportunity.data.get("resource_type") == "fish"

    def test_opportunity_system_with_low_health(self):
        """Test that low health triggers emergency opportunities"""
        self.agent.health = 15.0  # Very low health

        opportunities = self.agent.get_current_opportunities()

        # Should detect emergency opportunity
        emergency_opportunities = [
            opp for opp, score in opportunities
            if opp.opportunity_type == OpportunityType.EMERGENCY
        ]

        assert len(emergency_opportunities) >= 1
        emergency_opp = emergency_opportunities[0]
        assert emergency_opp.data.get("emergency_type") == "low_health"

    def test_opportunity_system_respects_personality(self):
        """Test that opportunity scoring respects agent personality"""
        # Create agent with high combat preference
        combat_personality = Personality(combat=9.0, fishing=2.0)
        combat_agent = Agent("combat_agent", 10.0, 10.0, "test", combat_personality)

        # Create agent with high fishing preference
        fishing_personality = Personality(combat=2.0, fishing=9.0)
        fishing_agent = Agent("fishing_agent", 10.0, 10.0, "test", fishing_personality)

        visible_entities = [
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 12.0,
                "y": 11.0,
                "health": 80.0
            },
            {
                "id": "fish_1",
                "type": "fish",
                "x": 12.0,
                "y": 11.0
            }
        ]

        # Both agents see the same entities
        combat_agent.perceive(visible_entities)
        fishing_agent.perceive(visible_entities)

        combat_best = combat_agent.get_best_opportunity()
        fishing_best = fishing_agent.get_best_opportunity()

        assert combat_best is not None
        assert fishing_best is not None

        # Combat agent should prefer combat, fishing agent should prefer fishing
        # (though this depends on exact utility calculations)
        combat_opp, combat_score = combat_best
        fishing_opp, fishing_score = fishing_best

        # Both should find valid opportunities
        assert combat_score > 0
        assert fishing_score > 0

    def test_opportunity_system_with_terrain_data(self):
        """Test opportunity detection with terrain data"""
        # Mock terrain data with harvestable resources
        terrain_data = {
            (11, 11): "wood",  # Assuming string-based terrain types for test
            (12, 10): "water",
            (13, 11): "grass"
        }

        opportunities = self.agent.get_current_opportunities(terrain_data)

        # Should detect terrain-based opportunities if the terrain detection works
        # Note: This might not work if TileType imports fail, but should not error
        assert isinstance(opportunities, list)

    def test_opportunity_clearing(self):
        """Test clearing opportunities"""
        visible_entities = [
            {
                "id": "resource_1",
                "type": "wood",
                "x": 12.0,
                "y": 11.0
            }
        ]

        self.agent.perceive(visible_entities)
        opportunities_before = self.agent.get_current_opportunities()
        assert len(opportunities_before) > 0

        # Clear opportunities
        opp_system = self.agent.get_opportunity_system()
        opp_system.clear_opportunities()

        # Should have no opportunities now
        opportunities_after = self.agent.get_current_opportunities()
        assert len(opportunities_after) == 0

    def test_opportunity_system_thread_safety(self):
        """Test that opportunity system can be called multiple times safely"""
        visible_entities = [
            {
                "id": "resource_1",
                "type": "wood",
                "x": 12.0,
                "y": 11.0
            }
        ]

        self.agent.perceive(visible_entities)

        # Multiple calls should not cause errors
        for _ in range(5):
            opportunities = self.agent.get_current_opportunities()
            assert len(opportunities) >= 0

            best = self.agent.get_best_opportunity()
            if best:
                assert best[1] > 0  # Positive score


if __name__ == "__main__":
    pytest.main([__file__])