"""
Flexibility Testing Harness

This module provides a comprehensive framework for testing agent behavioral flexibility
and adaptation capabilities. It measures how well agents adjust to changing environments,
new challenges, and varying resource conditions.
"""

import time
import json
import statistics
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
from pathlib import Path

from client.behavior_tree.behavior_composer import BehaviorComposer, BehaviorComposition
from client.agent_memory import AgentMemory
from shared.personality import Personality


class FlexibilityMetric(Enum):
    """Types of flexibility metrics we can measure"""
    ADAPTATION_SPEED = "adaptation_speed"
    BEHAVIOR_DIVERSITY = "behavior_diversity"
    CONTEXT_SENSITIVITY = "context_sensitivity"
    RECOVERY_TIME = "recovery_time"
    STRATEGY_SWITCHING = "strategy_switching"
    RESOURCE_EFFICIENCY = "resource_efficiency"
    LEARNING_RATE = "learning_rate"
    ROBUSTNESS = "robustness"


class ScenarioDifficulty(Enum):
    """Difficulty levels for flexibility scenarios"""
    TRIVIAL = 1
    EASY = 2
    MODERATE = 3
    CHALLENGING = 4
    EXPERT = 5
    EXTREME = 6


@dataclass
class FlexibilityScore:
    """Individual flexibility measurement"""
    metric: FlexibilityMetric
    score: float  # 0.0 to 1.0
    raw_value: float
    measurement_time: float
    context: Dict[str, Any]
    details: str = ""


@dataclass
class ScenarioResult:
    """Results from running a flexibility scenario"""
    scenario_name: str
    difficulty: ScenarioDifficulty
    duration: float
    scores: List[FlexibilityScore]
    agent_id: str
    success: bool
    failure_reason: Optional[str] = None
    metadata: Dict[str, Any] = None

    def get_overall_score(self) -> float:
        """Calculate overall flexibility score for this scenario"""
        if not self.scores:
            return 0.0
        return statistics.mean([score.score for score in self.scores])

    def get_metric_score(self, metric: FlexibilityMetric) -> Optional[float]:
        """Get score for specific metric"""
        for score in self.scores:
            if score.metric == metric:
                return score.score
        return None


@dataclass
class FlexibilityReport:
    """Comprehensive flexibility assessment report"""
    agent_id: str
    test_timestamp: float
    scenarios: List[ScenarioResult]
    overall_flexibility: float
    metric_breakdown: Dict[FlexibilityMetric, float]
    recommendations: List[str]
    strengths: List[str]
    weaknesses: List[str]

    def save_to_file(self, filepath: str):
        """Save report to JSON file"""
        data = asdict(self)
        # Convert enums to strings for JSON serialization
        data['metric_breakdown'] = {k.value: v for k, v in data['metric_breakdown'].items()}
        for scenario in data['scenarios']:
            scenario['difficulty'] = scenario['difficulty'].value
            for score in scenario['scores']:
                score['metric'] = score['metric'].value

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


class MockFlexibilityAgent:
    """Mock agent for flexibility testing"""

    def __init__(self, agent_id: str, personality: Optional[Personality] = None):
        self.id = agent_id
        self.x = 0.0
        self.y = 0.0
        self.personality = personality or Personality(combat=5.0, exploration=5.0, social=5.0)
        self.memory = AgentMemory(agent_id)
        self.health = 100.0
        self.resources = {"wood": 10, "stone": 5, "food": 20}
        self.agent_type = "flexibility_test_agent"
        self.behavior_history: List[str] = []
        self.decision_times: List[float] = []

    def move_to(self, x: float, y: float):
        """Move agent to new position"""
        self.x = x
        self.y = y

    def update_resources(self, resource_changes: Dict[str, int]):
        """Update agent resources"""
        for resource, change in resource_changes.items():
            if resource in self.resources:
                self.resources[resource] = max(0, self.resources[resource] + change)
            else:
                self.resources[resource] = max(0, change)

    def record_behavior(self, behavior_name: str, decision_time: float):
        """Record behavior for analysis"""
        self.behavior_history.append(behavior_name)
        self.decision_times.append(decision_time)


class FlexibilityHarness:
    """Main harness for testing agent flexibility"""

    def __init__(self, output_dir: str = "flexibility_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.behavior_composer = BehaviorComposer()
        self.metrics_calculators: Dict[FlexibilityMetric, Callable] = {
            FlexibilityMetric.ADAPTATION_SPEED: self._measure_adaptation_speed,
            FlexibilityMetric.BEHAVIOR_DIVERSITY: self._measure_behavior_diversity,
            FlexibilityMetric.CONTEXT_SENSITIVITY: self._measure_context_sensitivity,
            FlexibilityMetric.RECOVERY_TIME: self._measure_recovery_time,
            FlexibilityMetric.STRATEGY_SWITCHING: self._measure_strategy_switching,
            FlexibilityMetric.RESOURCE_EFFICIENCY: self._measure_resource_efficiency,
            FlexibilityMetric.LEARNING_RATE: self._measure_learning_rate,
            FlexibilityMetric.ROBUSTNESS: self._measure_robustness
        }

    def run_flexibility_assessment(self, agent: MockFlexibilityAgent,
                                 scenarios: Optional[List[str]] = None) -> FlexibilityReport:
        """Run comprehensive flexibility assessment"""
        if scenarios is None:
            scenarios = [
                "resource_scarcity_adaptation",
                "environment_change_response",
                "social_dynamics_shift",
                "threat_level_variation",
                "opportunity_recognition",
                "multi_constraint_optimization"
            ]

        results = []
        for scenario_name in scenarios:
            result = self.run_scenario(agent, scenario_name)
            results.append(result)

        return self._generate_report(agent, results)

    def run_scenario(self, agent: MockFlexibilityAgent, scenario_name: str) -> ScenarioResult:
        """Run a specific flexibility scenario"""
        start_time = time.time()

        try:
            if scenario_name == "resource_scarcity_adaptation":
                return self._run_resource_scarcity_scenario(agent, start_time)
            elif scenario_name == "environment_change_response":
                return self._run_environment_change_scenario(agent, start_time)
            elif scenario_name == "social_dynamics_shift":
                return self._run_social_dynamics_scenario(agent, start_time)
            elif scenario_name == "threat_level_variation":
                return self._run_threat_variation_scenario(agent, start_time)
            elif scenario_name == "opportunity_recognition":
                return self._run_opportunity_recognition_scenario(agent, start_time)
            elif scenario_name == "multi_constraint_optimization":
                return self._run_multi_constraint_scenario(agent, start_time)
            else:
                raise ValueError(f"Unknown scenario: {scenario_name}")

        except Exception as e:
            duration = time.time() - start_time
            return ScenarioResult(
                scenario_name=scenario_name,
                difficulty=ScenarioDifficulty.MODERATE,
                duration=duration,
                scores=[],
                agent_id=agent.id,
                success=False,
                failure_reason=str(e)
            )

    def _run_resource_scarcity_scenario(self, agent: MockFlexibilityAgent,
                                      start_time: float) -> ScenarioResult:
        """Test adaptation to resource scarcity"""
        # Set up resource scarcity conditions
        original_resources = agent.resources.copy()
        agent.update_resources({"wood": -8, "stone": -4, "food": -15})  # Severe scarcity

        scores = []
        contexts = []

        # Phase 1: Initial adaptation
        context1 = {"resource_target": "wood", "scarcity_level": "high"}
        contexts.append(context1)
        composition1 = self.behavior_composer.compose_behavior(agent, context1)

        # Measure adaptation speed
        adaptation_start = time.time()
        if composition1:
            composition1.execute(agent, 0.1)
        adaptation_time = time.time() - adaptation_start
        adaptation_score = self._measure_adaptation_speed(agent, adaptation_time, context1)
        scores.append(adaptation_score)

        # Phase 2: Resource constraint handling
        context2 = {"resource_target": "food", "scarcity_level": "critical"}
        contexts.append(context2)
        efficiency_score = self._measure_resource_efficiency(agent, context2, original_resources)
        scores.append(efficiency_score)

        # Phase 3: Strategy switching
        context3 = {"emergency": True, "available_resources": list(agent.resources.keys())}
        contexts.append(context3)
        switching_score = self._measure_strategy_switching(agent, contexts)
        scores.append(switching_score)

        duration = time.time() - start_time
        return ScenarioResult(
            scenario_name="resource_scarcity_adaptation",
            difficulty=ScenarioDifficulty.CHALLENGING,
            duration=duration,
            scores=scores,
            agent_id=agent.id,
            success=True,
            metadata={"original_resources": original_resources, "final_resources": agent.resources}
        )

    def _run_environment_change_scenario(self, agent: MockFlexibilityAgent,
                                       start_time: float) -> ScenarioResult:
        """Test response to environmental changes"""
        scores = []

        # Simulate environmental shift
        agent.move_to(50.0, 50.0)  # Move to new environment
        agent.memory.remember_danger_zone(50.0, 50.0, "environmental_hazard", 0.7,
                                        {"hazard_type": "toxic_area"})

        # Test context sensitivity
        context = {"environment_type": "hazardous", "location": (50.0, 50.0)}
        sensitivity_score = self._measure_context_sensitivity(agent, context)
        scores.append(sensitivity_score)

        # Test robustness to change
        robustness_score = self._measure_robustness(agent, context)
        scores.append(robustness_score)

        duration = time.time() - start_time
        return ScenarioResult(
            scenario_name="environment_change_response",
            difficulty=ScenarioDifficulty.MODERATE,
            duration=duration,
            scores=scores,
            agent_id=agent.id,
            success=True
        )

    def _run_social_dynamics_scenario(self, agent: MockFlexibilityAgent,
                                    start_time: float) -> ScenarioResult:
        """Test adaptation to social dynamics changes"""
        scores = []

        # Simulate social interactions
        partner_id = "social_partner"
        agent.memory.remember_social_interaction(partner_id, "cooperation", "successful")
        agent.memory.remember_social_interaction(partner_id, "trade", "failed")

        # Test learning from social feedback
        context = {"social_context": True, "partner_id": partner_id}
        learning_score = self._measure_learning_rate(agent, context)
        scores.append(learning_score)

        duration = time.time() - start_time
        return ScenarioResult(
            scenario_name="social_dynamics_shift",
            difficulty=ScenarioDifficulty.MODERATE,
            duration=duration,
            scores=scores,
            agent_id=agent.id,
            success=True
        )

    def _run_threat_variation_scenario(self, agent: MockFlexibilityAgent,
                                     start_time: float) -> ScenarioResult:
        """Test response to varying threat levels"""
        scores = []

        # Simulate threat variation
        agent.health = 30.0  # Low health
        agent.memory.remember_danger_zone(agent.x, agent.y, "combat_threat", 0.9,
                                        {"threat_level": "high"})

        # Test recovery capabilities
        context = {"threat_level": "high", "health_critical": True}
        recovery_score = self._measure_recovery_time(agent, context)
        scores.append(recovery_score)

        duration = time.time() - start_time
        return ScenarioResult(
            scenario_name="threat_level_variation",
            difficulty=ScenarioDifficulty.CHALLENGING,
            duration=duration,
            scores=scores,
            agent_id=agent.id,
            success=True
        )

    def _run_opportunity_recognition_scenario(self, agent: MockFlexibilityAgent,
                                            start_time: float) -> ScenarioResult:
        """Test opportunity recognition and exploitation"""
        scores = []

        # Create opportunity scenario
        agent.memory.remember_resource_location(agent.x + 5, agent.y + 5, "rare_mineral", 0.95, 10)

        # Test behavior diversity in response to opportunities
        context = {"opportunity_type": "resource_discovery", "opportunity_value": "high"}
        diversity_score = self._measure_behavior_diversity(agent, context)
        scores.append(diversity_score)

        duration = time.time() - start_time
        return ScenarioResult(
            scenario_name="opportunity_recognition",
            difficulty=ScenarioDifficulty.MODERATE,
            duration=duration,
            scores=scores,
            agent_id=agent.id,
            success=True
        )

    def _run_multi_constraint_scenario(self, agent: MockFlexibilityAgent,
                                     start_time: float) -> ScenarioResult:
        """Test handling of multiple simultaneous constraints"""
        scores = []

        # Set up multiple constraints
        agent.health = 25.0  # Low health
        agent.update_resources({"food": -15})  # Low food
        agent.memory.remember_danger_zone(agent.x, agent.y, "multi_threat", 0.8,
                                        {"constraints": ["health", "food", "danger"]})

        # Test overall adaptation under pressure
        context = {
            "multi_constraint": True,
            "health_low": True,
            "food_scarce": True,
            "danger_present": True
        }

        adaptation_score = self._measure_adaptation_speed(agent, 2.0, context)
        scores.append(adaptation_score)

        duration = time.time() - start_time
        return ScenarioResult(
            scenario_name="multi_constraint_optimization",
            difficulty=ScenarioDifficulty.EXPERT,
            duration=duration,
            scores=scores,
            agent_id=agent.id,
            success=True
        )

    # Metrics calculation methods
    def _measure_adaptation_speed(self, agent: MockFlexibilityAgent,
                                decision_time: float, context: Dict[str, Any]) -> FlexibilityScore:
        """Measure how quickly agent adapts to new situations"""
        # Faster adaptation = higher score (inverse relationship)
        # Normalize to 0-1 scale, with 1.0 being instant, 0.0 being very slow
        max_acceptable_time = 5.0
        normalized_score = max(0.0, 1.0 - (decision_time / max_acceptable_time))

        return FlexibilityScore(
            metric=FlexibilityMetric.ADAPTATION_SPEED,
            score=normalized_score,
            raw_value=decision_time,
            measurement_time=time.time(),
            context=context,
            details=f"Decision made in {decision_time:.2f}s"
        )

    def _measure_behavior_diversity(self, agent: MockFlexibilityAgent,
                                  context: Dict[str, Any]) -> FlexibilityScore:
        """Measure variety of behaviors exhibited"""
        unique_behaviors = len(set(agent.behavior_history[-10:]))  # Last 10 behaviors
        max_possible_diversity = min(10, len(agent.behavior_history))

        if max_possible_diversity == 0:
            diversity_score = 0.0
        else:
            diversity_score = unique_behaviors / max_possible_diversity

        return FlexibilityScore(
            metric=FlexibilityMetric.BEHAVIOR_DIVERSITY,
            score=diversity_score,
            raw_value=unique_behaviors,
            measurement_time=time.time(),
            context=context,
            details=f"{unique_behaviors} unique behaviors in recent history"
        )

    def _measure_context_sensitivity(self, agent: MockFlexibilityAgent,
                                   context: Dict[str, Any]) -> FlexibilityScore:
        """Measure how well agent responds to context changes"""
        # Check if agent has memories relevant to current context
        location_memories = agent.memory.location_memory.get_memories_near(agent.x, agent.y, radius=10.0)
        context_relevance = len(location_memories) / 10.0  # Normalize to 0-1
        context_relevance = min(1.0, context_relevance)

        return FlexibilityScore(
            metric=FlexibilityMetric.CONTEXT_SENSITIVITY,
            score=context_relevance,
            raw_value=len(location_memories),
            measurement_time=time.time(),
            context=context,
            details=f"Using {len(location_memories)} contextual memories"
        )

    def _measure_recovery_time(self, agent: MockFlexibilityAgent,
                             context: Dict[str, Any]) -> FlexibilityScore:
        """Measure time to recover from setbacks"""
        # Simulate recovery scenario based on health/resources
        recovery_potential = (agent.health / 100.0) + (sum(agent.resources.values()) / 100.0)
        recovery_score = min(1.0, recovery_potential / 2.0)  # Normalize

        return FlexibilityScore(
            metric=FlexibilityMetric.RECOVERY_TIME,
            score=recovery_score,
            raw_value=recovery_potential,
            measurement_time=time.time(),
            context=context,
            details=f"Recovery potential: {recovery_potential:.2f}"
        )

    def _measure_strategy_switching(self, agent: MockFlexibilityAgent,
                                  contexts: List[Dict[str, Any]]) -> FlexibilityScore:
        """Measure ability to switch strategies based on context"""
        if len(contexts) < 2:
            return FlexibilityScore(
                metric=FlexibilityMetric.STRATEGY_SWITCHING,
                score=0.0,
                raw_value=0,
                measurement_time=time.time(),
                context=contexts[-1] if contexts else {},
                details="Insufficient context changes to measure switching"
            )

        # Check for strategy diversity across contexts
        strategy_changes = len(contexts) - 1  # Number of potential switches
        switching_score = min(1.0, strategy_changes / 3.0)  # Normalize

        return FlexibilityScore(
            metric=FlexibilityMetric.STRATEGY_SWITCHING,
            score=switching_score,
            raw_value=strategy_changes,
            measurement_time=time.time(),
            context=contexts[-1],
            details=f"Handled {strategy_changes} context switches"
        )

    def _measure_resource_efficiency(self, agent: MockFlexibilityAgent,
                                   context: Dict[str, Any],
                                   original_resources: Dict[str, int]) -> FlexibilityScore:
        """Measure efficient use of limited resources"""
        # Compare resource usage efficiency
        resource_preservation = 0.0
        total_original = sum(original_resources.values())
        total_current = sum(agent.resources.values())

        if total_original > 0:
            resource_preservation = total_current / total_original

        efficiency_score = min(1.0, resource_preservation)

        return FlexibilityScore(
            metric=FlexibilityMetric.RESOURCE_EFFICIENCY,
            score=efficiency_score,
            raw_value=resource_preservation,
            measurement_time=time.time(),
            context=context,
            details=f"Resource preservation: {resource_preservation:.2f}"
        )

    def _measure_learning_rate(self, agent: MockFlexibilityAgent,
                             context: Dict[str, Any]) -> FlexibilityScore:
        """Measure speed of learning from experience"""
        # Check memory formation and reinforcement
        location_memories_count = len(agent.memory.location_memory.memories)
        social_memories_count = sum(len(memories) for memories in agent.memory.social_memory.agent_memories.values())
        total_memories = location_memories_count + social_memories_count
        learning_score = min(1.0, total_memories / 50.0)  # Normalize to reasonable scale

        return FlexibilityScore(
            metric=FlexibilityMetric.LEARNING_RATE,
            score=learning_score,
            raw_value=total_memories,
            measurement_time=time.time(),
            context=context,
            details=f"Formed {total_memories} memories"
        )

    def _measure_robustness(self, agent: MockFlexibilityAgent,
                          context: Dict[str, Any]) -> FlexibilityScore:
        """Measure stability under adverse conditions"""
        # Assess agent's stability metrics
        health_stability = agent.health / 100.0
        resource_stability = min(1.0, sum(agent.resources.values()) / 50.0)
        robustness_score = (health_stability + resource_stability) / 2.0

        return FlexibilityScore(
            metric=FlexibilityMetric.ROBUSTNESS,
            score=robustness_score,
            raw_value=robustness_score,
            measurement_time=time.time(),
            context=context,
            details=f"Health: {health_stability:.2f}, Resources: {resource_stability:.2f}"
        )

    def _generate_report(self, agent: MockFlexibilityAgent,
                        results: List[ScenarioResult]) -> FlexibilityReport:
        """Generate comprehensive flexibility report"""
        # Calculate overall flexibility score
        if results:
            overall_score = statistics.mean([r.get_overall_score() for r in results])
        else:
            overall_score = 0.0

        # Calculate metric breakdown
        metric_scores = {}
        for metric in FlexibilityMetric:
            scores = []
            for result in results:
                score = result.get_metric_score(metric)
                if score is not None:
                    scores.append(score)
            if scores:
                metric_scores[metric] = statistics.mean(scores)
            else:
                metric_scores[metric] = 0.0

        # Generate recommendations
        recommendations = self._generate_recommendations(metric_scores)
        strengths = self._identify_strengths(metric_scores)
        weaknesses = self._identify_weaknesses(metric_scores)

        return FlexibilityReport(
            agent_id=agent.id,
            test_timestamp=time.time(),
            scenarios=results,
            overall_flexibility=overall_score,
            metric_breakdown=metric_scores,
            recommendations=recommendations,
            strengths=strengths,
            weaknesses=weaknesses
        )

    def _generate_recommendations(self, metric_scores: Dict[FlexibilityMetric, float]) -> List[str]:
        """Generate improvement recommendations based on scores"""
        recommendations = []

        if metric_scores[FlexibilityMetric.ADAPTATION_SPEED] < 0.6:
            recommendations.append("Focus on faster decision-making under pressure")

        if metric_scores[FlexibilityMetric.BEHAVIOR_DIVERSITY] < 0.5:
            recommendations.append("Expand behavioral repertoire for varied situations")

        if metric_scores[FlexibilityMetric.LEARNING_RATE] < 0.4:
            recommendations.append("Improve memory formation and experience integration")

        if metric_scores[FlexibilityMetric.ROBUSTNESS] < 0.5:
            recommendations.append("Enhance resilience to adverse conditions")

        return recommendations

    def _identify_strengths(self, metric_scores: Dict[FlexibilityMetric, float]) -> List[str]:
        """Identify agent's flexibility strengths"""
        strengths = []

        for metric, score in metric_scores.items():
            if score >= 0.8:
                strengths.append(f"Excellent {metric.value}")
            elif score >= 0.7:
                strengths.append(f"Strong {metric.value}")

        return strengths

    def _identify_weaknesses(self, metric_scores: Dict[FlexibilityMetric, float]) -> List[str]:
        """Identify agent's flexibility weaknesses"""
        weaknesses = []

        for metric, score in metric_scores.items():
            if score < 0.3:
                weaknesses.append(f"Poor {metric.value}")
            elif score < 0.5:
                weaknesses.append(f"Needs improvement in {metric.value}")

        return weaknesses


# Convenience functions for common testing patterns
def quick_flexibility_test(agent_id: str = "test_agent") -> FlexibilityReport:
    """Run a quick flexibility assessment with default settings"""
    harness = FlexibilityHarness()
    agent = MockFlexibilityAgent(agent_id)
    return harness.run_flexibility_assessment(agent)


def comprehensive_flexibility_test(agent_id: str = "test_agent",
                                 personality: Optional[Personality] = None,
                                 scenarios: Optional[List[str]] = None) -> FlexibilityReport:
    """Run comprehensive flexibility assessment with custom options"""
    harness = FlexibilityHarness()
    agent = MockFlexibilityAgent(agent_id, personality)
    return harness.run_flexibility_assessment(agent, scenarios)