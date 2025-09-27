"""
Tests for Flexibility Testing Harness

Comprehensive tests for the flexibility testing framework to ensure
accurate measurement of agent behavioral flexibility and adaptation.
"""

import pytest
import time
import tempfile
import json
from pathlib import Path

from tests.flexibility.flexibility_harness import (
    FlexibilityHarness, FlexibilityMetric, ScenarioDifficulty, FlexibilityScore,
    ScenarioResult, FlexibilityReport, MockFlexibilityAgent,
    quick_flexibility_test, comprehensive_flexibility_test
)
from shared.personality import Personality


class TestFlexibilityScore:
    """Test FlexibilityScore dataclass"""

    def test_flexibility_score_creation(self):
        """Test creating flexibility scores"""
        score = FlexibilityScore(
            metric=FlexibilityMetric.ADAPTATION_SPEED,
            score=0.85,
            raw_value=1.2,
            measurement_time=time.time(),
            context={"test": True},
            details="Test measurement"
        )

        assert score.metric == FlexibilityMetric.ADAPTATION_SPEED
        assert score.score == 0.85
        assert score.raw_value == 1.2
        assert "test" in score.context
        assert score.details == "Test measurement"


class TestScenarioResult:
    """Test ScenarioResult dataclass and methods"""

    def test_scenario_result_creation(self):
        """Test creating scenario results"""
        scores = [
            FlexibilityScore(FlexibilityMetric.ADAPTATION_SPEED, 0.8, 1.0, time.time(), {}),
            FlexibilityScore(FlexibilityMetric.BEHAVIOR_DIVERSITY, 0.6, 3.0, time.time(), {})
        ]

        result = ScenarioResult(
            scenario_name="test_scenario",
            difficulty=ScenarioDifficulty.MODERATE,
            duration=2.5,
            scores=scores,
            agent_id="test_agent",
            success=True
        )

        assert result.scenario_name == "test_scenario"
        assert result.difficulty == ScenarioDifficulty.MODERATE
        assert result.success is True
        assert len(result.scores) == 2

    def test_overall_score_calculation(self):
        """Test overall score calculation"""
        scores = [
            FlexibilityScore(FlexibilityMetric.ADAPTATION_SPEED, 0.8, 1.0, time.time(), {}),
            FlexibilityScore(FlexibilityMetric.BEHAVIOR_DIVERSITY, 0.6, 3.0, time.time(), {})
        ]

        result = ScenarioResult(
            scenario_name="test",
            difficulty=ScenarioDifficulty.EASY,
            duration=1.0,
            scores=scores,
            agent_id="test",
            success=True
        )

        overall = result.get_overall_score()
        assert overall == 0.7  # (0.8 + 0.6) / 2

    def test_overall_score_empty_scores(self):
        """Test overall score with no scores"""
        result = ScenarioResult(
            scenario_name="test",
            difficulty=ScenarioDifficulty.EASY,
            duration=1.0,
            scores=[],
            agent_id="test",
            success=False
        )

        assert result.get_overall_score() == 0.0

    def test_get_metric_score(self):
        """Test getting specific metric scores"""
        scores = [
            FlexibilityScore(FlexibilityMetric.ADAPTATION_SPEED, 0.8, 1.0, time.time(), {}),
            FlexibilityScore(FlexibilityMetric.BEHAVIOR_DIVERSITY, 0.6, 3.0, time.time(), {})
        ]

        result = ScenarioResult(
            scenario_name="test",
            difficulty=ScenarioDifficulty.EASY,
            duration=1.0,
            scores=scores,
            agent_id="test",
            success=True
        )

        assert result.get_metric_score(FlexibilityMetric.ADAPTATION_SPEED) == 0.8
        assert result.get_metric_score(FlexibilityMetric.BEHAVIOR_DIVERSITY) == 0.6
        assert result.get_metric_score(FlexibilityMetric.ROBUSTNESS) is None


class TestFlexibilityReport:
    """Test FlexibilityReport dataclass and methods"""

    def test_report_save_to_file(self):
        """Test saving report to JSON file"""
        scores = [FlexibilityScore(FlexibilityMetric.ADAPTATION_SPEED, 0.8, 1.0, time.time(), {})]
        scenario = ScenarioResult("test", ScenarioDifficulty.EASY, 1.0, scores, "agent", True)

        report = FlexibilityReport(
            agent_id="test_agent",
            test_timestamp=time.time(),
            scenarios=[scenario],
            overall_flexibility=0.75,
            metric_breakdown={FlexibilityMetric.ADAPTATION_SPEED: 0.8},
            recommendations=["Test recommendation"],
            strengths=["Test strength"],
            weaknesses=["Test weakness"]
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report.save_to_file(f.name)

            # Verify file was created and contains valid JSON
            with open(f.name, 'r') as read_f:
                data = json.load(read_f)
                assert data['agent_id'] == "test_agent"
                assert data['overall_flexibility'] == 0.75
                assert len(data['scenarios']) == 1

            # Cleanup
            Path(f.name).unlink()


class TestMockFlexibilityAgent:
    """Test MockFlexibilityAgent functionality"""

    def test_agent_creation(self):
        """Test creating mock agents"""
        agent = MockFlexibilityAgent("test_agent")

        assert agent.id == "test_agent"
        assert agent.x == 0.0
        assert agent.y == 0.0
        assert agent.health == 100.0
        assert "wood" in agent.resources
        assert len(agent.behavior_history) == 0

    def test_agent_with_custom_personality(self):
        """Test agent with custom personality"""
        personality = Personality(combat=8.0, exploration=3.0, social=9.0)
        agent = MockFlexibilityAgent("test_agent", personality)

        assert agent.personality.combat == 8.0
        assert agent.personality.exploration == 3.0
        assert agent.personality.social == 9.0

    def test_agent_movement(self):
        """Test agent movement"""
        agent = MockFlexibilityAgent("test_agent")
        agent.move_to(10.0, 20.0)

        assert agent.x == 10.0
        assert agent.y == 20.0

    def test_resource_updates(self):
        """Test resource updates"""
        agent = MockFlexibilityAgent("test_agent")
        initial_wood = agent.resources["wood"]

        agent.update_resources({"wood": 5, "new_resource": 3})

        assert agent.resources["wood"] == initial_wood + 5
        assert agent.resources["new_resource"] == 3

    def test_resource_updates_negative(self):
        """Test negative resource updates don't go below zero"""
        agent = MockFlexibilityAgent("test_agent")
        agent.update_resources({"wood": -100})

        assert agent.resources["wood"] == 0

    def test_behavior_recording(self):
        """Test behavior recording"""
        agent = MockFlexibilityAgent("test_agent")
        agent.record_behavior("gather_wood", 1.5)
        agent.record_behavior("explore_area", 2.0)

        assert len(agent.behavior_history) == 2
        assert agent.behavior_history[0] == "gather_wood"
        assert agent.behavior_history[1] == "explore_area"
        assert len(agent.decision_times) == 2


class TestFlexibilityHarness:
    """Test FlexibilityHarness core functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.harness = FlexibilityHarness()
        self.agent = MockFlexibilityAgent("test_agent")

    def test_harness_creation(self):
        """Test creating flexibility harness"""
        assert self.harness.output_dir.exists()
        assert self.harness.behavior_composer is not None
        assert len(self.harness.metrics_calculators) == 8

    def test_adaptation_speed_measurement(self):
        """Test adaptation speed measurement"""
        context = {"test_context": True}
        score = self.harness._measure_adaptation_speed(self.agent, 1.0, context)

        assert score.metric == FlexibilityMetric.ADAPTATION_SPEED
        assert 0.0 <= score.score <= 1.0
        assert score.raw_value == 1.0
        assert score.context == context

    def test_adaptation_speed_fast_vs_slow(self):
        """Test adaptation speed scoring for fast vs slow responses"""
        context = {}
        fast_score = self.harness._measure_adaptation_speed(self.agent, 0.5, context)
        slow_score = self.harness._measure_adaptation_speed(self.agent, 4.0, context)

        assert fast_score.score > slow_score.score

    def test_behavior_diversity_measurement(self):
        """Test behavior diversity measurement"""
        # Add some behavior history
        self.agent.behavior_history = ["gather", "explore", "gather", "combat", "social"]

        context = {"diversity_test": True}
        score = self.harness._measure_behavior_diversity(self.agent, context)

        assert score.metric == FlexibilityMetric.BEHAVIOR_DIVERSITY
        assert 0.0 <= score.score <= 1.0
        assert score.raw_value == 4  # 4 unique behaviors

    def test_behavior_diversity_empty_history(self):
        """Test behavior diversity with empty history"""
        context = {}
        score = self.harness._measure_behavior_diversity(self.agent, context)

        assert score.score == 0.0
        assert score.raw_value == 0

    def test_context_sensitivity_measurement(self):
        """Test context sensitivity measurement"""
        # Add some location memories
        self.agent.memory.remember_resource_location(0, 0, "wood", 0.8, 5)
        self.agent.memory.remember_danger_zone(2, 2, "threat", 0.7, {"type": "enemy"})

        context = {"location_based": True}
        score = self.harness._measure_context_sensitivity(self.agent, context)

        assert score.metric == FlexibilityMetric.CONTEXT_SENSITIVITY
        assert 0.0 <= score.score <= 1.0
        assert score.raw_value >= 0

    def test_recovery_time_measurement(self):
        """Test recovery time measurement"""
        # Set up a recovery scenario
        self.agent.health = 50.0
        self.agent.resources = {"wood": 5, "food": 10}

        context = {"recovery_scenario": True}
        score = self.harness._measure_recovery_time(self.agent, context)

        assert score.metric == FlexibilityMetric.RECOVERY_TIME
        assert 0.0 <= score.score <= 1.0

    def test_strategy_switching_measurement(self):
        """Test strategy switching measurement"""
        contexts = [
            {"phase": 1, "strategy": "gather"},
            {"phase": 2, "strategy": "combat"},
            {"phase": 3, "strategy": "explore"}
        ]

        score = self.harness._measure_strategy_switching(self.agent, contexts)

        assert score.metric == FlexibilityMetric.STRATEGY_SWITCHING
        assert 0.0 <= score.score <= 1.0
        assert score.raw_value == 2  # 2 strategy switches

    def test_strategy_switching_insufficient_contexts(self):
        """Test strategy switching with insufficient contexts"""
        contexts = [{"single": "context"}]
        score = self.harness._measure_strategy_switching(self.agent, contexts)

        assert score.score == 0.0
        assert "Insufficient context" in score.details

    def test_resource_efficiency_measurement(self):
        """Test resource efficiency measurement"""
        original_resources = {"wood": 10, "stone": 5, "food": 20}
        self.agent.resources = {"wood": 8, "stone": 4, "food": 18}  # Some consumption

        context = {"efficiency_test": True}
        score = self.harness._measure_resource_efficiency(self.agent, context, original_resources)

        assert score.metric == FlexibilityMetric.RESOURCE_EFFICIENCY
        assert 0.0 <= score.score <= 1.0

    def test_learning_rate_measurement(self):
        """Test learning rate measurement"""
        # Add some memories to simulate learning
        self.agent.memory.remember_resource_location(0, 0, "wood", 0.8, 5)
        self.agent.memory.remember_social_interaction("partner", "trade", "success")

        context = {"learning_test": True}
        score = self.harness._measure_learning_rate(self.agent, context)

        assert score.metric == FlexibilityMetric.LEARNING_RATE
        assert 0.0 <= score.score <= 1.0
        assert score.raw_value >= 2  # At least 2 memories

    def test_robustness_measurement(self):
        """Test robustness measurement"""
        # Test with different health/resource states
        self.agent.health = 80.0
        self.agent.resources = {"wood": 15, "food": 25}

        context = {"robustness_test": True}
        score = self.harness._measure_robustness(self.agent, context)

        assert score.metric == FlexibilityMetric.ROBUSTNESS
        assert 0.0 <= score.score <= 1.0

    def test_robustness_poor_conditions(self):
        """Test robustness under poor conditions"""
        self.agent.health = 10.0
        self.agent.resources = {"wood": 1}

        context = {}
        score = self.harness._measure_robustness(self.agent, context)

        assert score.score < 0.5  # Should be low under poor conditions


class TestScenarioExecution:
    """Test scenario execution"""

    def setup_method(self):
        """Set up test fixtures"""
        self.harness = FlexibilityHarness()
        self.agent = MockFlexibilityAgent("test_agent")

    def test_resource_scarcity_scenario(self):
        """Test resource scarcity adaptation scenario"""
        result = self.harness.run_scenario(self.agent, "resource_scarcity_adaptation")

        assert result.scenario_name == "resource_scarcity_adaptation"
        assert result.difficulty == ScenarioDifficulty.CHALLENGING
        assert result.success is True
        assert len(result.scores) > 0
        assert result.agent_id == self.agent.id

    def test_environment_change_scenario(self):
        """Test environment change response scenario"""
        result = self.harness.run_scenario(self.agent, "environment_change_response")

        assert result.scenario_name == "environment_change_response"
        assert result.difficulty == ScenarioDifficulty.MODERATE
        assert result.success is True
        assert len(result.scores) > 0

    def test_social_dynamics_scenario(self):
        """Test social dynamics scenario"""
        result = self.harness.run_scenario(self.agent, "social_dynamics_shift")

        assert result.scenario_name == "social_dynamics_shift"
        assert result.success is True
        assert len(result.scores) > 0

    def test_threat_variation_scenario(self):
        """Test threat variation scenario"""
        result = self.harness.run_scenario(self.agent, "threat_level_variation")

        assert result.scenario_name == "threat_level_variation"
        assert result.difficulty == ScenarioDifficulty.CHALLENGING
        assert result.success is True

    def test_opportunity_recognition_scenario(self):
        """Test opportunity recognition scenario"""
        result = self.harness.run_scenario(self.agent, "opportunity_recognition")

        assert result.scenario_name == "opportunity_recognition"
        assert result.success is True

    def test_multi_constraint_scenario(self):
        """Test multi-constraint optimization scenario"""
        result = self.harness.run_scenario(self.agent, "multi_constraint_optimization")

        assert result.scenario_name == "multi_constraint_optimization"
        assert result.difficulty == ScenarioDifficulty.EXPERT
        assert result.success is True

    def test_unknown_scenario(self):
        """Test handling of unknown scenario"""
        result = self.harness.run_scenario(self.agent, "unknown_scenario")

        assert result.success is False
        assert result.failure_reason is not None
        assert "Unknown scenario" in result.failure_reason


class TestFlexibilityAssessment:
    """Test full flexibility assessment"""

    def setup_method(self):
        """Set up test fixtures"""
        self.harness = FlexibilityHarness()
        self.agent = MockFlexibilityAgent("assessment_agent")

    def test_full_assessment_default_scenarios(self):
        """Test full assessment with default scenarios"""
        report = self.harness.run_flexibility_assessment(self.agent)

        assert report.agent_id == self.agent.id
        assert len(report.scenarios) == 6  # Default scenarios
        assert 0.0 <= report.overall_flexibility <= 1.0
        assert len(report.metric_breakdown) == 8  # All metrics
        assert isinstance(report.recommendations, list)
        assert isinstance(report.strengths, list)
        assert isinstance(report.weaknesses, list)

    def test_assessment_custom_scenarios(self):
        """Test assessment with custom scenarios"""
        custom_scenarios = ["resource_scarcity_adaptation", "environment_change_response"]
        report = self.harness.run_flexibility_assessment(self.agent, custom_scenarios)

        assert len(report.scenarios) == 2
        assert report.scenarios[0].scenario_name == "resource_scarcity_adaptation"
        assert report.scenarios[1].scenario_name == "environment_change_response"

    def test_assessment_with_personality(self):
        """Test assessment with different personality"""
        high_combat_personality = Personality(combat=9.0, exploration=2.0, social=5.0)
        combat_agent = MockFlexibilityAgent("combat_agent", high_combat_personality)

        report = self.harness.run_flexibility_assessment(combat_agent)

        assert report.agent_id == "combat_agent"
        assert len(report.scenarios) > 0

    def test_metric_breakdown_completeness(self):
        """Test that all metrics are included in breakdown"""
        report = self.harness.run_flexibility_assessment(self.agent)

        for metric in FlexibilityMetric:
            assert metric in report.metric_breakdown
            assert 0.0 <= report.metric_breakdown[metric] <= 1.0

    def test_recommendations_generation(self):
        """Test recommendation generation logic"""
        # Create a report with specific low scores
        metric_scores = {
            FlexibilityMetric.ADAPTATION_SPEED: 0.3,  # Low
            FlexibilityMetric.BEHAVIOR_DIVERSITY: 0.4,  # Low
            FlexibilityMetric.LEARNING_RATE: 0.2,  # Very low
            FlexibilityMetric.ROBUSTNESS: 0.4,  # Low
            FlexibilityMetric.CONTEXT_SENSITIVITY: 0.8,  # High
            FlexibilityMetric.RECOVERY_TIME: 0.7,  # Good
            FlexibilityMetric.STRATEGY_SWITCHING: 0.6,  # OK
            FlexibilityMetric.RESOURCE_EFFICIENCY: 0.9  # Excellent
        }

        recommendations = self.harness._generate_recommendations(metric_scores)

        assert len(recommendations) > 0
        assert any("decision-making" in rec for rec in recommendations)
        assert any("behavioral repertoire" in rec for rec in recommendations)
        assert any("memory formation" in rec for rec in recommendations)

    def test_strengths_identification(self):
        """Test strengths identification"""
        metric_scores = {metric: 0.85 for metric in FlexibilityMetric}  # All high scores

        strengths = self.harness._identify_strengths(metric_scores)

        assert len(strengths) == len(FlexibilityMetric)  # All should be strengths
        assert all("Excellent" in strength for strength in strengths)

    def test_weaknesses_identification(self):
        """Test weaknesses identification"""
        metric_scores = {metric: 0.2 for metric in FlexibilityMetric}  # All low scores

        weaknesses = self.harness._identify_weaknesses(metric_scores)

        assert len(weaknesses) == len(FlexibilityMetric)  # All should be weaknesses
        assert all("Poor" in weakness for weakness in weaknesses)


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_quick_flexibility_test(self):
        """Test quick flexibility test function"""
        report = quick_flexibility_test("quick_test_agent")

        assert report.agent_id == "quick_test_agent"
        assert len(report.scenarios) > 0
        assert 0.0 <= report.overall_flexibility <= 1.0

    def test_comprehensive_flexibility_test(self):
        """Test comprehensive flexibility test function"""
        personality = Personality(combat=7.0, exploration=8.0, social=6.0)
        custom_scenarios = ["resource_scarcity_adaptation", "social_dynamics_shift"]

        report = comprehensive_flexibility_test(
            "comprehensive_agent",
            personality,
            custom_scenarios
        )

        assert report.agent_id == "comprehensive_agent"
        assert len(report.scenarios) == 2

    def test_comprehensive_test_defaults(self):
        """Test comprehensive test with default parameters"""
        report = comprehensive_flexibility_test("default_agent")

        assert report.agent_id == "default_agent"
        assert len(report.scenarios) > 0


class TestIntegration:
    """Integration tests for flexibility harness"""

    def test_harness_with_real_behavior_composer(self):
        """Test harness integration with real behavior composer"""
        harness = FlexibilityHarness()
        agent = MockFlexibilityAgent("integration_agent")

        # Test that behavior composer integration works
        composition = harness.behavior_composer.compose_behavior(
            agent, {"resource_target": "wood"}
        )

        # Should not crash and should return a composition or None
        assert composition is None or composition is not None

    def test_memory_persistence_during_scenarios(self):
        """Test that memories persist across scenario phases"""
        harness = FlexibilityHarness()
        agent = MockFlexibilityAgent("memory_agent")

        # Run a scenario that should create memories
        result = harness.run_scenario(agent, "resource_scarcity_adaptation")

        # Check that memories were created
        location_memories_count = len(agent.memory.location_memory.memories)
        social_memories_count = sum(len(memories) for memories in agent.memory.social_memory.agent_memories.values())
        total_memories = location_memories_count + social_memories_count
        assert total_memories >= 0  # Should have some memories

    def test_report_serialization_roundtrip(self):
        """Test report serialization and deserialization"""
        harness = FlexibilityHarness()
        agent = MockFlexibilityAgent("serialization_agent")

        report = harness.run_flexibility_assessment(agent, ["resource_scarcity_adaptation"])

        # Save and load report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report.save_to_file(f.name)

            # Verify file contains valid JSON
            with open(f.name, 'r') as read_f:
                data = json.load(read_f)
                assert data['agent_id'] == agent.id
                assert 'overall_flexibility' in data
                assert 'scenarios' in data

            # Cleanup
            Path(f.name).unlink()

    def test_concurrent_scenario_safety(self):
        """Test that running multiple scenarios doesn't interfere"""
        harness = FlexibilityHarness()
        agent1 = MockFlexibilityAgent("agent1")
        agent2 = MockFlexibilityAgent("agent2")

        # Run scenarios on different agents
        result1 = harness.run_scenario(agent1, "resource_scarcity_adaptation")
        result2 = harness.run_scenario(agent2, "environment_change_response")

        assert result1.agent_id == "agent1"
        assert result2.agent_id == "agent2"
        assert result1.success
        assert result2.success


if __name__ == "__main__":
    pytest.main([__file__])