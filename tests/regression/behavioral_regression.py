"""
Behavioral Regression Testing Framework

This module provides a framework for detecting behavioral regressions in agent
systems. It captures baseline behaviors, compares them against current performance,
and identifies significant deviations that could indicate bugs or unintended changes.
"""

import json
import time
import statistics
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from enum import Enum

from client.behavior_tree.behavior_composer import BehaviorComposer
from tests.flexibility.flexibility_harness import MockFlexibilityAgent, FlexibilityHarness


class RegressionSeverity(Enum):
    """Severity levels for behavioral regressions"""
    CRITICAL = "critical"     # Major behavioral changes
    HIGH = "high"            # Significant performance degradation
    MEDIUM = "medium"        # Noticeable but manageable changes
    LOW = "low"             # Minor variations within acceptable range
    INFO = "info"           # Changes that are informational only


class BehaviorMetric(Enum):
    """Types of behavioral metrics to track"""
    DECISION_TIME = "decision_time"
    BEHAVIOR_CONSISTENCY = "behavior_consistency"
    RESOURCE_EFFICIENCY = "resource_efficiency"
    GOAL_COMPLETION_RATE = "goal_completion_rate"
    ADAPTATION_QUALITY = "adaptation_quality"
    MEMORY_UTILIZATION = "memory_utilization"
    SOCIAL_INTERACTION_SUCCESS = "social_interaction_success"
    STRATEGY_DIVERSITY = "strategy_diversity"


@dataclass
class BehaviorSnapshot:
    """Snapshot of behavior at a specific point in time"""
    timestamp: float
    agent_config: Dict[str, Any]
    scenario: str
    metrics: Dict[BehaviorMetric, float]
    execution_trace: List[str]
    context: Dict[str, Any]
    version_info: Dict[str, str]


@dataclass
class RegressionResult:
    """Result of a regression comparison"""
    metric: BehaviorMetric
    baseline_value: float
    current_value: float
    change_percentage: float
    severity: RegressionSeverity
    significance: float  # Statistical significance (0.0 to 1.0)
    description: str


@dataclass
class RegressionReport:
    """Comprehensive regression analysis report"""
    test_timestamp: float
    baseline_timestamp: float
    scenario: str
    agent_config: Dict[str, Any]
    regressions: List[RegressionResult]
    overall_score: float  # 0.0 (many regressions) to 1.0 (no regressions)
    summary: str
    recommendations: List[str]

    def save_to_file(self, filepath: str):
        """Save report to JSON file"""
        data = asdict(self)
        # Convert enums to strings
        for regression in data['regressions']:
            regression['metric'] = regression['metric'].value
            regression['severity'] = regression['severity'].value

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def has_critical_regressions(self) -> bool:
        """Check if there are any critical regressions"""
        return any(r.severity == RegressionSeverity.CRITICAL for r in self.regressions)

    def get_regressions_by_severity(self, severity: RegressionSeverity) -> List[RegressionResult]:
        """Get all regressions of a specific severity"""
        return [r for r in self.regressions if r.severity == severity]


class BehaviorBaseline:
    """Manages behavioral baselines for regression testing"""

    def __init__(self, baseline_dir: str = "behavior_baselines"):
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(exist_ok=True)
        self.baselines: Dict[str, List[BehaviorSnapshot]] = {}

    def add_snapshot(self, snapshot: BehaviorSnapshot, scenario: str):
        """Add a behavior snapshot to the baseline"""
        if scenario not in self.baselines:
            self.baselines[scenario] = []
        self.baselines[scenario].append(snapshot)

    def save_baseline(self, scenario: str, version: str):
        """Save baseline to disk"""
        if scenario not in self.baselines:
            return

        filename = f"{scenario}_{version}_baseline.json"
        filepath = self.baseline_dir / filename

        data = {
            "scenario": scenario,
            "version": version,
            "snapshots": []
        }

        for snapshot in self.baselines[scenario]:
            snapshot_data = asdict(snapshot)
            # Convert enums to strings
            metrics_data = {k.value: v for k, v in snapshot_data['metrics'].items()}
            snapshot_data['metrics'] = metrics_data
            data["snapshots"].append(snapshot_data)

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_baseline(self, scenario: str, version: str) -> bool:
        """Load baseline from disk"""
        filename = f"{scenario}_{version}_baseline.json"
        filepath = self.baseline_dir / filename

        if not filepath.exists():
            return False

        with open(filepath, 'r') as f:
            data = json.load(f)

        snapshots = []
        for snapshot_data in data["snapshots"]:
            # Convert string keys back to enums
            metrics = {BehaviorMetric(k): v for k, v in snapshot_data['metrics'].items()}
            snapshot_data['metrics'] = metrics

            snapshot = BehaviorSnapshot(**snapshot_data)
            snapshots.append(snapshot)

        self.baselines[scenario] = snapshots
        return True

    def get_baseline_stats(self, scenario: str) -> Dict[BehaviorMetric, Dict[str, float]]:
        """Get statistical summary of baseline for a scenario"""
        if scenario not in self.baselines or not self.baselines[scenario]:
            return {}

        stats = {}
        all_metrics = set()
        for snapshot in self.baselines[scenario]:
            all_metrics.update(snapshot.metrics.keys())

        for metric in all_metrics:
            values = [s.metrics[metric] for s in self.baselines[scenario] if metric in s.metrics]
            if values:
                stats[metric] = {
                    "mean": statistics.mean(values),
                    "median": statistics.median(values),
                    "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }

        return stats


class BehaviorMeasurer:
    """Measures behavioral metrics for regression testing"""

    def __init__(self):
        self.behavior_composer = BehaviorComposer()
        self.flexibility_harness = FlexibilityHarness()

    def measure_behavior(self, agent: MockFlexibilityAgent, scenario: str,
                        context: Dict[str, Any]) -> BehaviorSnapshot:
        """Measure comprehensive behavior metrics for an agent"""
        start_time = time.time()
        execution_trace = []

        # Measure decision time
        decision_start = time.time()
        composition = self.behavior_composer.compose_behavior(agent, context)
        decision_time = time.time() - decision_start

        if composition:
            execution_trace.append(f"Composed behavior with {len(composition.fragments)} fragments")

            # Execute and measure
            execution_start = time.time()
            result = composition.execute(agent, 0.1)
            execution_time = time.time() - execution_start
            execution_trace.append(f"Executed behavior in {execution_time:.3f}s with result {result}")

        # Calculate metrics
        metrics = {
            BehaviorMetric.DECISION_TIME: decision_time,
            BehaviorMetric.BEHAVIOR_CONSISTENCY: self._measure_consistency(agent, scenario),
            BehaviorMetric.RESOURCE_EFFICIENCY: self._measure_resource_efficiency(agent),
            BehaviorMetric.GOAL_COMPLETION_RATE: self._measure_goal_completion(composition, result),
            BehaviorMetric.ADAPTATION_QUALITY: self._measure_adaptation_quality(agent, context),
            BehaviorMetric.MEMORY_UTILIZATION: self._measure_memory_utilization(agent),
            BehaviorMetric.SOCIAL_INTERACTION_SUCCESS: self._measure_social_success(agent),
            BehaviorMetric.STRATEGY_DIVERSITY: self._measure_strategy_diversity(agent)
        }

        return BehaviorSnapshot(
            timestamp=time.time(),
            agent_config={
                "personality": {
                    "combat": agent.personality.combat,
                    "exploration": agent.personality.exploration,
                    "social": agent.personality.social
                },
                "resources": agent.resources.copy(),
                "health": agent.health
            },
            scenario=scenario,
            metrics=metrics,
            execution_trace=execution_trace,
            context=context.copy(),
            version_info={"test_version": "1.0.0"}  # Could be dynamically determined
        )

    def _measure_consistency(self, agent: MockFlexibilityAgent, scenario: str) -> float:
        """Measure behavioral consistency (repeatability)"""
        # For now, return a stable value based on agent configuration
        # In practice, this would run multiple iterations and measure variance
        config_hash = hashlib.md5(str(agent.personality.__dict__).encode()).hexdigest()
        return (int(config_hash[:8], 16) % 100) / 100.0

    def _measure_resource_efficiency(self, agent: MockFlexibilityAgent) -> float:
        """Measure how efficiently agent uses resources"""
        total_resources = sum(agent.resources.values())
        if total_resources == 0:
            return 0.0

        # Simple efficiency measure based on resource distribution
        resource_balance = 1.0 - (statistics.stdev(agent.resources.values()) /
                                 statistics.mean(agent.resources.values())
                                 if len(agent.resources) > 1 else 0.0)
        return max(0.0, min(1.0, resource_balance))

    def _measure_goal_completion(self, composition, result) -> float:
        """Measure goal completion rate"""
        if composition is None:
            return 0.0

        # Simple completion measure based on execution result
        from client.behavior_tree.nodes.base import NodeStatus
        if result == NodeStatus.SUCCESS:
            return 1.0
        elif result == NodeStatus.RUNNING:
            return 0.5
        else:
            return 0.0

    def _measure_adaptation_quality(self, agent: MockFlexibilityAgent,
                                  context: Dict[str, Any]) -> float:
        """Measure quality of adaptation to context"""
        # Use flexibility harness for adaptation measurement
        adaptation_score = self.flexibility_harness._measure_adaptation_speed(
            agent, 1.0, context
        )
        return adaptation_score.score

    def _measure_memory_utilization(self, agent: MockFlexibilityAgent) -> float:
        """Measure how well agent utilizes memory"""
        location_memories = len(agent.memory.location_memory.memories)
        social_memories = sum(len(memories) for memories in
                             agent.memory.social_memory.agent_memories.values())
        total_memories = location_memories + social_memories

        # Normalize memory utilization (assuming 50 is a good target)
        return min(1.0, total_memories / 50.0)

    def _measure_social_success(self, agent: MockFlexibilityAgent) -> float:
        """Measure social interaction success rate"""
        total_interactions = sum(len(memories) for memories in
                               agent.memory.social_memory.agent_memories.values())

        if total_interactions == 0:
            return 0.5  # Neutral score for no interactions

        # For now, return a stable score based on agent's social personality
        return agent.personality.social / 10.0

    def _measure_strategy_diversity(self, agent: MockFlexibilityAgent) -> float:
        """Measure diversity of strategies used"""
        if not agent.behavior_history:
            return 0.0

        unique_behaviors = len(set(agent.behavior_history))
        total_behaviors = len(agent.behavior_history)

        return unique_behaviors / total_behaviors if total_behaviors > 0 else 0.0


class RegressionAnalyzer:
    """Analyzes behavioral changes and identifies regressions"""

    def __init__(self, significance_threshold: float = 0.1):
        self.significance_threshold = significance_threshold

    def compare_behaviors(self, baseline_stats: Dict[BehaviorMetric, Dict[str, float]],
                         current_snapshot: BehaviorSnapshot) -> List[RegressionResult]:
        """Compare current behavior against baseline and identify regressions"""
        regressions = []

        for metric in BehaviorMetric:
            if metric not in baseline_stats:
                continue

            if metric not in current_snapshot.metrics:
                continue

            baseline_mean = baseline_stats[metric]["mean"]
            baseline_stdev = baseline_stats[metric]["stdev"]
            current_value = current_snapshot.metrics[metric]

            # Calculate change percentage
            if baseline_mean != 0:
                change_percentage = ((current_value - baseline_mean) / baseline_mean) * 100
            else:
                change_percentage = 0.0 if current_value == 0 else float('inf')

            # Calculate statistical significance
            if baseline_stdev > 0:
                z_score = abs(current_value - baseline_mean) / baseline_stdev
                significance = min(1.0, z_score / 3.0)  # Normalize to 0-1
            else:
                significance = 1.0 if current_value != baseline_mean else 0.0

            # Determine severity
            severity = self._determine_severity(metric, change_percentage, significance)

            # Create regression result
            regression = RegressionResult(
                metric=metric,
                baseline_value=baseline_mean,
                current_value=current_value,
                change_percentage=change_percentage,
                severity=severity,
                significance=significance,
                description=self._generate_description(metric, change_percentage, significance)
            )

            # Only include significant regressions
            if significance >= self.significance_threshold:
                regressions.append(regression)

        return regressions

    def _determine_severity(self, metric: BehaviorMetric, change_percentage: float,
                          significance: float) -> RegressionSeverity:
        """Determine regression severity based on metric, change, and significance"""
        abs_change = abs(change_percentage)

        # Critical thresholds
        if significance > 0.9 and abs_change > 50:
            return RegressionSeverity.CRITICAL

        # High severity thresholds
        if significance > 0.7 and abs_change > 30:
            return RegressionSeverity.HIGH

        # Medium severity thresholds
        if significance > 0.5 and abs_change > 15:
            return RegressionSeverity.MEDIUM

        # Low severity thresholds
        if significance > 0.3 and abs_change > 5:
            return RegressionSeverity.LOW

        return RegressionSeverity.INFO

    def _generate_description(self, metric: BehaviorMetric, change_percentage: float,
                            significance: float) -> str:
        """Generate human-readable description of the regression"""
        direction = "increased" if change_percentage > 0 else "decreased"
        abs_change = abs(change_percentage)

        significance_desc = "highly significant" if significance > 0.8 else \
                           "significant" if significance > 0.5 else \
                           "moderately significant"

        return f"{metric.value} {direction} by {abs_change:.1f}% " \
               f"({significance_desc} change)"

    def generate_report(self, scenario: str, baseline_stats: Dict[BehaviorMetric, Dict[str, float]],
                       current_snapshot: BehaviorSnapshot,
                       baseline_timestamp: float) -> RegressionReport:
        """Generate comprehensive regression report"""
        regressions = self.compare_behaviors(baseline_stats, current_snapshot)

        # Calculate overall score (0.0 = many critical regressions, 1.0 = no regressions)
        if not regressions:
            overall_score = 1.0
        else:
            severity_weights = {
                RegressionSeverity.CRITICAL: 1.0,
                RegressionSeverity.HIGH: 0.7,
                RegressionSeverity.MEDIUM: 0.4,
                RegressionSeverity.LOW: 0.2,
                RegressionSeverity.INFO: 0.0
            }

            total_impact = sum(severity_weights[r.severity] * r.significance for r in regressions)
            max_possible_impact = len(regressions) * 1.0  # Maximum if all were critical
            overall_score = max(0.0, 1.0 - (total_impact / max_possible_impact if max_possible_impact > 0 else 0))

        # Generate summary
        critical_count = len([r for r in regressions if r.severity == RegressionSeverity.CRITICAL])
        high_count = len([r for r in regressions if r.severity == RegressionSeverity.HIGH])

        if critical_count > 0:
            summary = f"CRITICAL: {critical_count} critical behavioral regressions detected"
        elif high_count > 0:
            summary = f"HIGH: {high_count} high-severity behavioral changes detected"
        elif regressions:
            summary = f"MODERATE: {len(regressions)} behavioral changes detected"
        else:
            summary = "PASS: No significant behavioral regressions detected"

        # Generate recommendations
        recommendations = self._generate_recommendations(regressions)

        return RegressionReport(
            test_timestamp=current_snapshot.timestamp,
            baseline_timestamp=baseline_timestamp,
            scenario=scenario,
            agent_config=current_snapshot.agent_config,
            regressions=regressions,
            overall_score=overall_score,
            summary=summary,
            recommendations=recommendations
        )

    def _generate_recommendations(self, regressions: List[RegressionResult]) -> List[str]:
        """Generate actionable recommendations based on regressions"""
        recommendations = []

        critical_regressions = [r for r in regressions if r.severity == RegressionSeverity.CRITICAL]
        if critical_regressions:
            recommendations.append(
                "URGENT: Investigate critical behavioral changes before deployment"
            )

        decision_time_issues = [r for r in regressions
                              if r.metric == BehaviorMetric.DECISION_TIME and r.change_percentage > 20]
        if decision_time_issues:
            recommendations.append(
                "Performance: Decision-making speed has degraded significantly"
            )

        efficiency_issues = [r for r in regressions
                           if r.metric == BehaviorMetric.RESOURCE_EFFICIENCY and r.change_percentage < -15]
        if efficiency_issues:
            recommendations.append(
                "Efficiency: Resource utilization has become less efficient"
            )

        consistency_issues = [r for r in regressions
                            if r.metric == BehaviorMetric.BEHAVIOR_CONSISTENCY and r.change_percentage < -10]
        if consistency_issues:
            recommendations.append(
                "Stability: Behavioral consistency has decreased, check for randomization issues"
            )

        return recommendations


class BehaviorRegressionTester:
    """Main interface for behavioral regression testing"""

    def __init__(self, baseline_dir: str = "behavior_baselines"):
        self.baseline = BehaviorBaseline(baseline_dir)
        self.measurer = BehaviorMeasurer()
        self.analyzer = RegressionAnalyzer()

    def create_baseline(self, scenario: str, version: str, agent_configs: List[Dict[str, Any]],
                       context: Dict[str, Any]) -> bool:
        """Create a new behavioral baseline"""
        for config in agent_configs:
            agent = self._create_agent_from_config(config)
            snapshot = self.measurer.measure_behavior(agent, scenario, context)
            self.baseline.add_snapshot(snapshot, scenario)

        self.baseline.save_baseline(scenario, version)
        return True

    def test_regression(self, scenario: str, baseline_version: str,
                       agent_config: Dict[str, Any], context: Dict[str, Any]) -> RegressionReport:
        """Test for behavioral regressions against a baseline"""
        # Load baseline
        if not self.baseline.load_baseline(scenario, baseline_version):
            raise ValueError(f"Baseline not found: {scenario}_{baseline_version}")

        # Get baseline statistics
        baseline_stats = self.baseline.get_baseline_stats(scenario)
        baseline_timestamp = min(s.timestamp for s in self.baseline.baselines[scenario])

        # Measure current behavior
        agent = self._create_agent_from_config(agent_config)
        current_snapshot = self.measurer.measure_behavior(agent, scenario, context)

        # Analyze regressions
        return self.analyzer.generate_report(
            scenario, baseline_stats, current_snapshot, baseline_timestamp
        )

    def _create_agent_from_config(self, config: Dict[str, Any]) -> MockFlexibilityAgent:
        """Create an agent from configuration"""
        from shared.personality import Personality

        personality_config = config.get("personality", {})
        personality = Personality(
            combat=personality_config.get("combat", 5.0),
            exploration=personality_config.get("exploration", 5.0),
            social=personality_config.get("social", 5.0)
        )

        agent = MockFlexibilityAgent(config.get("agent_id", "test_agent"), personality)

        # Set resources if provided
        if "resources" in config:
            agent.resources = config["resources"].copy()

        # Set health if provided
        if "health" in config:
            agent.health = config["health"]

        return agent

    def run_regression_suite(self, scenarios: List[str], baseline_version: str,
                           agent_configs: List[Dict[str, Any]],
                           contexts: Dict[str, Dict[str, Any]]) -> List[RegressionReport]:
        """Run comprehensive regression testing suite"""
        reports = []

        for scenario in scenarios:
            context = contexts.get(scenario, {})
            for agent_config in agent_configs:
                try:
                    report = self.test_regression(scenario, baseline_version, agent_config, context)
                    reports.append(report)
                except Exception as e:
                    # Create error report
                    error_report = RegressionReport(
                        test_timestamp=time.time(),
                        baseline_timestamp=0.0,
                        scenario=scenario,
                        agent_config=agent_config,
                        regressions=[],
                        overall_score=0.0,
                        summary=f"ERROR: {str(e)}",
                        recommendations=[f"Fix error in scenario {scenario}"]
                    )
                    reports.append(error_report)

        return reports


# Convenience functions
def create_standard_baseline(version: str = "1.0.0") -> bool:
    """Create standard behavioral baseline with common scenarios"""
    tester = BehaviorRegressionTester()

    # Standard agent configurations
    agent_configs = [
        {
            "agent_id": "balanced_agent",
            "personality": {"combat": 5.0, "exploration": 5.0, "social": 5.0},
            "resources": {"wood": 10, "stone": 5, "food": 20},
            "health": 100.0
        },
        {
            "agent_id": "combat_focused",
            "personality": {"combat": 8.0, "exploration": 3.0, "social": 4.0},
            "resources": {"wood": 8, "stone": 8, "food": 15},
            "health": 100.0
        },
        {
            "agent_id": "explorer_agent",
            "personality": {"combat": 3.0, "exploration": 9.0, "social": 3.0},
            "resources": {"wood": 12, "stone": 3, "food": 25},
            "health": 100.0
        }
    ]

    # Standard scenarios
    scenarios = [
        "resource_gathering",
        "exploration",
        "social_interaction",
        "threat_response"
    ]

    for scenario in scenarios:
        context = {"scenario_type": scenario, "difficulty": "standard"}
        tester.create_baseline(scenario, version, agent_configs, context)

    return True


def quick_regression_test(scenario: str = "resource_gathering",
                         baseline_version: str = "1.0.0") -> RegressionReport:
    """Run a quick regression test with default settings"""
    tester = BehaviorRegressionTester()

    agent_config = {
        "agent_id": "quick_test_agent",
        "personality": {"combat": 5.0, "exploration": 5.0, "social": 5.0},
        "resources": {"wood": 10, "stone": 5, "food": 20},
        "health": 100.0
    }

    context = {"scenario_type": scenario, "difficulty": "standard"}

    return tester.test_regression(scenario, baseline_version, agent_config, context)