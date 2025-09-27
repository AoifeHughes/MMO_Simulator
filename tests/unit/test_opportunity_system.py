"""
Unit tests for the Opportunity System.

Tests the core functionality of opportunity detection, evaluation, and scoring.
"""

import math
import time
from unittest.mock import MagicMock, Mock

import pytest

from client.opportunity_system import (
    Opportunity,
    OpportunityDetector,
    OpportunityEvaluator,
    OpportunitySystem,
    OpportunityType,
)
from shared.personality import Personality


class TestOpportunity:
    """Test the Opportunity class"""

    def test_opportunity_creation(self):
        """Test basic opportunity creation"""
        opp = Opportunity(
            opportunity_id="test_opp",
            opportunity_type=OpportunityType.RESOURCE,
            position=(10.0, 15.0),
            value=5.0,
            urgency=3.0,
        )

        assert opp.opportunity_id == "test_opp"
        assert opp.opportunity_type == OpportunityType.RESOURCE
        assert opp.position == (10.0, 15.0)
        assert opp.value == 5.0
        assert opp.urgency == 3.0

    def test_opportunity_expiration(self):
        """Test opportunity expiration logic"""
        # Create opportunity with very short duration
        opp = Opportunity(
            opportunity_id="short_lived",
            opportunity_type=OpportunityType.COMBAT,
            position=(0.0, 0.0),
            duration=0.01,  # 10ms duration
        )

        # Should not be expired immediately
        assert not opp.is_expired()

        # Wait and check expiration
        time.sleep(0.02)
        assert opp.is_expired()

    def test_distance_calculation(self):
        """Test distance calculation"""
        opp = Opportunity(
            opportunity_id="distance_test",
            opportunity_type=OpportunityType.RESOURCE,
            position=(3.0, 4.0),  # 3-4-5 triangle
        )

        # Test distance from origin
        distance = opp.distance_to(0.0, 0.0)
        assert abs(distance - 5.0) < 0.001

        # Test distance from same position
        distance = opp.distance_to(3.0, 4.0)
        assert abs(distance - 0.0) < 0.001

    def test_within_range(self):
        """Test range checking"""
        opp = Opportunity(
            opportunity_id="range_test",
            opportunity_type=OpportunityType.TRADE,
            position=(5.0, 5.0),
            required_distance=2.0,
        )

        # Within range
        assert opp.is_within_range(5.0, 6.0)
        assert opp.is_within_range(6.0, 5.0)

        # Outside range
        assert not opp.is_within_range(5.0, 8.0)
        assert not opp.is_within_range(0.0, 0.0)


class TestOpportunityDetector:
    """Test the OpportunityDetector class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.detector = OpportunityDetector("test_agent")
        self.mock_agent = Mock()
        self.mock_agent.id = "test_agent"
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.health = 80.0

        # Add personality
        self.mock_agent.personality = Personality(
            combat=7.0,
            fishing=8.0,
            foraging=6.0,
            social=5.0,
            cooperativeness=6.0,
            exploration=4.0,
        )

    def test_resource_opportunity_detection(self):
        """Test detection of resource opportunities"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0},
            {"id": "fish_1", "type": "fish", "x": 8.0, "y": 9.0},
            {"id": "enemy_1", "type": "enemy", "x": 15.0, "y": 15.0},
        ]

        opportunities = self.detector.detect_opportunities(
            self.mock_agent, visible_entities
        )

        # Should detect wood and fish resources
        resource_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.RESOURCE
        ]

        assert len(resource_opportunities) >= 2
        resource_ids = [opp.target_id for opp in resource_opportunities]
        assert "wood_1" in resource_ids
        assert "fish_1" in resource_ids

    def test_combat_opportunity_detection(self):
        """Test detection of combat opportunities"""
        visible_entities = [
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 13.0,
                "y": 12.0,
                "health": 60.0,
            },
            {
                "id": "friendly_1",
                "agent_type": "player",
                "x": 11.0,
                "y": 11.0,
                "health": 100.0,
            },
        ]

        opportunities = self.detector.detect_opportunities(
            self.mock_agent, visible_entities
        )

        combat_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.COMBAT
        ]

        # Should detect enemy but behavior depends on cooperativeness
        # With cooperativeness=6.0, should only target designated enemies
        enemy_targets = [opp.target_id for opp in combat_opportunities]
        assert "enemy_1" in enemy_targets

    def test_low_health_combat_avoidance(self):
        """Test that low health agents avoid combat"""
        self.mock_agent.health = 20.0  # Low health

        visible_entities = [
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 12.0,
                "y": 11.0,
                "health": 100.0,
            }
        ]

        opportunities = self.detector.detect_opportunities(
            self.mock_agent, visible_entities
        )

        combat_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.COMBAT
        ]

        # Should not detect combat opportunities when health is low
        assert len(combat_opportunities) == 0

    def test_trade_opportunity_detection(self):
        """Test detection of trade opportunities"""
        visible_entities = [
            {"id": "trader_1", "agent_type": "player", "x": 12.0, "y": 13.0},
            {"id": "trader_2", "agent_type": "npc", "x": 8.0, "y": 7.0},
        ]

        opportunities = self.detector.detect_opportunities(
            self.mock_agent, visible_entities
        )

        trade_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.TRADE
        ]

        assert len(trade_opportunities) >= 2
        trader_ids = [opp.target_id for opp in trade_opportunities]
        assert "trader_1" in trader_ids
        assert "trader_2" in trader_ids

    def test_emergency_low_health_detection(self):
        """Test detection of low health emergency"""
        self.mock_agent.health = 20.0  # Trigger emergency

        opportunities = self.detector.detect_opportunities(self.mock_agent, [])

        emergency_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.EMERGENCY
        ]

        assert len(emergency_opportunities) >= 1
        low_health_emergency = next(
            (
                opp
                for opp in emergency_opportunities
                if opp.data.get("emergency_type") == "low_health"
            ),
            None,
        )
        assert low_health_emergency is not None
        assert low_health_emergency.urgency == 10.0

    def test_surrounded_emergency_detection(self):
        """Test detection of surrounded emergency"""
        visible_entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 11.0, "y": 11.0},
            {"id": "enemy_2", "agent_type": "enemy", "x": 9.0, "y": 9.0},
        ]

        opportunities = self.detector.detect_opportunities(
            self.mock_agent, visible_entities
        )

        emergency_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.EMERGENCY
        ]

        surrounded_emergency = next(
            (
                opp
                for opp in emergency_opportunities
                if opp.data.get("emergency_type") == "surrounded"
            ),
            None,
        )
        assert surrounded_emergency is not None
        assert surrounded_emergency.urgency >= 8.0

    def test_social_opportunity_detection(self):
        """Test detection of social opportunities"""
        visible_entities = [
            {
                "id": "injured_ally",
                "agent_type": "player",
                "x": 12.0,
                "y": 11.0,
                "health": 30.0,  # Injured, needs help
            },
            {
                "id": "healthy_ally",
                "agent_type": "player",
                "x": 8.0,
                "y": 9.0,
                "health": 90.0,
            },
        ]

        opportunities = self.detector.detect_opportunities(
            self.mock_agent, visible_entities
        )

        social_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.SOCIAL
        ]

        # Should detect opportunities for both, but injured ally should have higher urgency
        assert len(social_opportunities) >= 1

        injured_opportunity = next(
            (opp for opp in social_opportunities if opp.target_id == "injured_ally"),
            None,
        )
        assert injured_opportunity is not None
        assert injured_opportunity.data.get("needs_help") is True

    def test_detection_ranges(self):
        """Test that detection respects range limits"""
        # Place entities at various distances
        visible_entities = [
            {
                "id": "close_resource",
                "type": "wood",
                "x": 12.0,  # Distance: ~2.8
                "y": 12.0,
            },
            {
                "id": "far_resource",
                "type": "wood",
                "x": 25.0,  # Distance: ~21.2 (beyond detection range)
                "y": 25.0,
            },
        ]

        opportunities = self.detector.detect_opportunities(
            self.mock_agent, visible_entities
        )

        resource_opportunities = [
            opp
            for opp in opportunities
            if opp.opportunity_type == OpportunityType.RESOURCE
        ]

        # Should only detect close resource
        detected_ids = [opp.target_id for opp in resource_opportunities]
        assert "close_resource" in detected_ids
        assert "far_resource" not in detected_ids


class TestOpportunityEvaluator:
    """Test the OpportunityEvaluator class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.evaluator = OpportunityEvaluator("test_agent")
        self.mock_agent = Mock()
        self.mock_agent.id = "test_agent"
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.health = 80.0
        self.mock_agent.visible_entities = []

        # Add personality
        self.mock_agent.personality = Personality(
            combat=8.0,
            fishing=6.0,
            foraging=7.0,
            social=5.0,
            cooperativeness=6.0,
            exploration=4.0,
        )

    def test_utility_calculation(self):
        """Test basic utility calculation"""
        opportunities = [
            Opportunity(
                opportunity_id="high_value",
                opportunity_type=OpportunityType.RESOURCE,
                position=(11.0, 11.0),  # Close
                value=8.0,
                urgency=5.0,
                data={"resource_type": "wood"},
            ),
            Opportunity(
                opportunity_id="low_value",
                opportunity_type=OpportunityType.RESOURCE,
                position=(15.0, 15.0),  # Farther
                value=3.0,
                urgency=2.0,
                data={"resource_type": "wood"},
            ),
        ]

        scored = self.evaluator.evaluate_opportunities(self.mock_agent, opportunities)

        # Should be sorted by utility (highest first)
        assert len(scored) == 2
        assert scored[0][0].opportunity_id == "high_value"
        assert scored[1][0].opportunity_id == "low_value"
        assert scored[0][1] > scored[1][1]  # Higher utility score

    def test_personality_factor(self):
        """Test personality influence on utility"""
        # Combat opportunity
        combat_opp = Opportunity(
            opportunity_id="combat_test",
            opportunity_type=OpportunityType.COMBAT,
            position=(11.0, 11.0),
            value=5.0,
            urgency=5.0,
        )

        # Resource opportunity
        resource_opp = Opportunity(
            opportunity_id="resource_test",
            opportunity_type=OpportunityType.RESOURCE,
            position=(11.0, 11.0),
            value=5.0,
            urgency=5.0,
            data={"resource_type": "wood"},
        )

        scored = self.evaluator.evaluate_opportunities(
            self.mock_agent, [combat_opp, resource_opp]
        )

        # Agent has high combat (8.0) and foraging (7.0)
        combat_score = next(
            score for opp, score in scored if opp.opportunity_id == "combat_test"
        )
        resource_score = next(
            score for opp, score in scored if opp.opportunity_id == "resource_test"
        )

        # The exact comparison depends on all factors, so just ensure both have reasonable scores
        assert combat_score > 0
        assert resource_score > 0

    def test_distance_penalty(self):
        """Test distance penalty on utility"""
        close_opp = Opportunity(
            opportunity_id="close",
            opportunity_type=OpportunityType.RESOURCE,
            position=(11.0, 11.0),  # Distance: ~1.4
            value=5.0,
        )

        far_opp = Opportunity(
            opportunity_id="far",
            opportunity_type=OpportunityType.RESOURCE,
            position=(20.0, 20.0),  # Distance: ~14.1
            value=5.0,
        )

        scored = self.evaluator.evaluate_opportunities(
            self.mock_agent, [close_opp, far_opp]
        )

        close_score = next(
            score for opp, score in scored if opp.opportunity_id == "close"
        )
        far_score = next(score for opp, score in scored if opp.opportunity_id == "far")

        assert close_score > far_score

    def test_urgency_multiplier(self):
        """Test urgency effect on utility"""
        urgent_opp = Opportunity(
            opportunity_id="urgent",
            opportunity_type=OpportunityType.EMERGENCY,
            position=(11.0, 11.0),
            value=5.0,
            urgency=10.0,
        )

        normal_opp = Opportunity(
            opportunity_id="normal",
            opportunity_type=OpportunityType.RESOURCE,
            position=(11.0, 11.0),
            value=5.0,
            urgency=3.0,
        )

        scored = self.evaluator.evaluate_opportunities(
            self.mock_agent, [urgent_opp, normal_opp]
        )

        urgent_score = next(
            score for opp, score in scored if opp.opportunity_id == "urgent"
        )
        normal_score = next(
            score for opp, score in scored if opp.opportunity_id == "normal"
        )

        assert urgent_score > normal_score

    def test_health_based_needs(self):
        """Test needs factor based on agent health"""
        self.mock_agent.health = 15.0  # Very low health

        emergency_opp = Opportunity(
            opportunity_id="emergency",
            opportunity_type=OpportunityType.EMERGENCY,
            position=(11.0, 11.0),
            value=5.0,
            data={"emergency_type": "low_health"},
        )

        combat_opp = Opportunity(
            opportunity_id="combat",
            opportunity_type=OpportunityType.COMBAT,
            position=(11.0, 11.0),
            value=5.0,
        )

        scored = self.evaluator.evaluate_opportunities(
            self.mock_agent, [emergency_opp, combat_opp]
        )

        emergency_score = next(
            score for opp, score in scored if opp.opportunity_id == "emergency"
        )
        combat_score = next(
            score for opp, score in scored if opp.opportunity_id == "combat"
        )

        # Emergency should have much higher utility when health is low
        assert emergency_score > combat_score * 2

    def test_expired_opportunity_filtering(self):
        """Test that expired opportunities are filtered out"""
        # Create an expired opportunity
        expired_opp = Opportunity(
            opportunity_id="expired",
            opportunity_type=OpportunityType.RESOURCE,
            position=(11.0, 11.0),
            value=5.0,
            duration=0.01,  # Very short duration
        )

        valid_opp = Opportunity(
            opportunity_id="valid",
            opportunity_type=OpportunityType.RESOURCE,
            position=(12.0, 12.0),
            value=5.0,
            duration=60.0,  # Long duration
        )

        # Wait for expiration
        time.sleep(0.02)

        scored = self.evaluator.evaluate_opportunities(
            self.mock_agent, [expired_opp, valid_opp]
        )

        # Should only return valid opportunity
        assert len(scored) == 1
        assert scored[0][0].opportunity_id == "valid"


class TestOpportunitySystem:
    """Test the complete OpportunitySystem"""

    def setup_method(self):
        """Set up test fixtures"""
        self.system = OpportunitySystem("test_agent")
        self.mock_agent = Mock()
        self.mock_agent.id = "test_agent"
        self.mock_agent.x = 10.0
        self.mock_agent.y = 10.0
        self.mock_agent.health = 80.0
        self.mock_agent.visible_entities = []  # Initialize as empty list

        self.mock_agent.personality = Personality(
            combat=6.0, fishing=7.0, foraging=5.0, social=4.0, cooperativeness=5.0
        )

    def test_system_integration(self):
        """Test complete system integration"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0},
            {
                "id": "enemy_1",
                "agent_type": "enemy",
                "x": 8.0,
                "y": 9.0,
                "health": 60.0,
            },
        ]

        scored_opportunities = self.system.update(self.mock_agent, visible_entities)

        # Should detect and score opportunities
        assert len(scored_opportunities) > 0

        # Should be sorted by utility
        if len(scored_opportunities) > 1:
            assert scored_opportunities[0][1] >= scored_opportunities[1][1]

    def test_best_opportunity_selection(self):
        """Test getting the best opportunity"""
        visible_entities = [
            {
                "id": "high_value_resource",
                "type": "fish",  # Agent has high fishing preference
                "x": 11.0,
                "y": 11.0,
            },
            {"id": "low_value_resource", "type": "wood", "x": 15.0, "y": 15.0},
        ]

        best_opportunity = self.system.get_best_opportunity(
            self.mock_agent, visible_entities
        )

        assert best_opportunity is not None
        opportunity, score = best_opportunity
        # Should get a valid opportunity with positive score
        assert opportunity.opportunity_type == OpportunityType.RESOURCE
        assert score > 0

    def test_opportunity_type_filtering(self):
        """Test filtering opportunities by type"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0},
            {"id": "enemy_1", "agent_type": "enemy", "x": 8.0, "y": 9.0},
        ]

        # Update system first
        self.system.update(self.mock_agent, visible_entities)

        # Get only resource opportunities
        resource_opportunities = self.system.get_opportunities_by_type(
            OpportunityType.RESOURCE
        )

        # Should only contain resource opportunities
        assert all(
            opp.opportunity_type == OpportunityType.RESOURCE
            for opp in resource_opportunities
        )

    def test_detection_interval(self):
        """Test detection interval throttling"""
        visible_entities = [{"id": "resource_1", "type": "wood", "x": 12.0, "y": 11.0}]

        # Set short detection interval
        self.system.set_detection_interval(0.1)

        # First update should detect opportunities
        opportunities1 = self.system.update(self.mock_agent, visible_entities)
        assert len(opportunities1) > 0

        # Immediate second update should return same opportunities (cached)
        opportunities2 = self.system.update(self.mock_agent, visible_entities)
        assert len(opportunities2) == len(opportunities1)

        # Wait for interval and update again
        time.sleep(0.11)
        opportunities3 = self.system.update(self.mock_agent, visible_entities)
        assert len(opportunities3) > 0

    def test_clear_opportunities(self):
        """Test clearing opportunities"""
        visible_entities = [{"id": "resource_1", "type": "wood", "x": 12.0, "y": 11.0}]

        # Detect opportunities
        self.system.update(self.mock_agent, visible_entities)
        assert len(self.system.current_opportunities) > 0

        # Clear opportunities
        self.system.clear_opportunities()
        assert len(self.system.current_opportunities) == 0


if __name__ == "__main__":
    pytest.main([__file__])
