"""
Tests for Behavioral Regression Testing Framework

Comprehensive tests for the behavioral regression testing system to ensure
accurate detection of behavioral changes and proper baseline management.
"""

import pytest
import time
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch

from tests.regression.behavioral_regression import (
    BehaviorBaseline, BehaviorMeasurer, RegressionAnalyzer, BehaviorRegressionTester,
    BehaviorSnapshot, RegressionResult, RegressionReport, BehaviorMetric,
    RegressionSeverity, create_standard_baseline, quick_regression_test
)
from tests.flexibility.flexibility_harness import MockFlexibilityAgent
from shared.personality import Personality


class TestBehaviorSnapshot:
    """Test BehaviorSnapshot dataclass"""

    def test_behavior_snapshot_creation(self):
        """Test creating behavior snapshots"""
        metrics = {
            BehaviorMetric.DECISION_TIME: 1.5,
            BehaviorMetric.RESOURCE_EFFICIENCY: 0.8
        }

        snapshot = BehaviorSnapshot(
            timestamp=time.time(),
            agent_config={"test": True},
            scenario="test_scenario",
            metrics=metrics,
            execution_trace=["step1", "step2"],
            context={"context": "test"},
            version_info={"version": "1.0.0"}
        )

        assert snapshot.scenario == "test_scenario"
        assert len(snapshot.metrics) == 2
        assert BehaviorMetric.DECISION_TIME in snapshot.metrics
        assert len(snapshot.execution_trace) == 2


class TestRegressionResult:
    """Test RegressionResult dataclass"""

    def test_regression_result_creation(self):
        """Test creating regression results"""
        result = RegressionResult(
            metric=BehaviorMetric.DECISION_TIME,
            baseline_value=1.0,
            current_value=1.5,
            change_percentage=50.0,
            severity=RegressionSeverity.HIGH,
            significance=0.8,
            description="Decision time increased significantly"
        )

        assert result.metric == BehaviorMetric.DECISION_TIME
        assert result.change_percentage == 50.0
        assert result.severity == RegressionSeverity.HIGH


class TestRegressionReport:
    """Test RegressionReport dataclass and methods"""

    def test_regression_report_creation(self):
        """Test creating regression reports"""
        regressions = [
            RegressionResult(
                BehaviorMetric.DECISION_TIME, 1.0, 1.5, 50.0,
                RegressionSeverity.HIGH, 0.8, "Test regression"
            )
        ]

        report = RegressionReport(
            test_timestamp=time.time(),
            baseline_timestamp=time.time() - 3600,
            scenario="test_scenario",
            agent_config={"test": True},
            regressions=regressions,
            overall_score=0.7,
            summary="Test summary",
            recommendations=["Test recommendation"]
        )

        assert report.scenario == "test_scenario"
        assert len(report.regressions) == 1
        assert report.overall_score == 0.7

    def test_has_critical_regressions(self):
        """Test critical regression detection"""
        critical_regression = RegressionResult(
            BehaviorMetric.DECISION_TIME, 1.0, 2.0, 100.0,
            RegressionSeverity.CRITICAL, 0.9, "Critical issue"
        )

        high_regression = RegressionResult(
            BehaviorMetric.RESOURCE_EFFICIENCY, 0.8, 0.6, -25.0,
            RegressionSeverity.HIGH, 0.7, "High issue"
        )

        # Report with critical regression
        report_critical = RegressionReport(
            time.time(), time.time(), "test", {}, [critical_regression],
            0.5, "Critical issues", []
        )

        # Report without critical regression
        report_non_critical = RegressionReport(
            time.time(), time.time(), "test", {}, [high_regression],
            0.7, "High issues", []
        )

        assert report_critical.has_critical_regressions() is True
        assert report_non_critical.has_critical_regressions() is False

    def test_get_regressions_by_severity(self):
        """Test filtering regressions by severity"""
        regressions = [
            RegressionResult(
                BehaviorMetric.DECISION_TIME, 1.0, 2.0, 100.0,
                RegressionSeverity.CRITICAL, 0.9, "Critical"
            ),
            RegressionResult(
                BehaviorMetric.RESOURCE_EFFICIENCY, 0.8, 0.6, -25.0,
                RegressionSeverity.HIGH, 0.7, "High"
            ),
            RegressionResult(
                BehaviorMetric.BEHAVIOR_CONSISTENCY, 0.9, 0.8, -11.0,
                RegressionSeverity.MEDIUM, 0.5, "Medium"
            )
        ]

        report = RegressionReport(
            time.time(), time.time(), "test", {}, regressions,
            0.6, "Mixed issues", []
        )

        critical = report.get_regressions_by_severity(RegressionSeverity.CRITICAL)
        high = report.get_regressions_by_severity(RegressionSeverity.HIGH)
        medium = report.get_regressions_by_severity(RegressionSeverity.MEDIUM)

        assert len(critical) == 1
        assert len(high) == 1
        assert len(medium) == 1
        assert critical[0].severity == RegressionSeverity.CRITICAL

    def test_save_to_file(self):
        """Test saving report to file"""
        regression = RegressionResult(
            BehaviorMetric.DECISION_TIME, 1.0, 1.5, 50.0,
            RegressionSeverity.HIGH, 0.8, "Test regression"
        )

        report = RegressionReport(
            test_timestamp=time.time(),
            baseline_timestamp=time.time() - 3600,
            scenario="test_scenario",
            agent_config={"test": True},
            regressions=[regression],
            overall_score=0.7,
            summary="Test summary",
            recommendations=["Test recommendation"]
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report.save_to_file(f.name)

            # Verify file was created and contains valid JSON
            with open(f.name, 'r') as read_f:
                data = json.load(read_f)
                assert data['scenario'] == "test_scenario"
                assert data['overall_score'] == 0.7
                assert len(data['regressions']) == 1

            # Cleanup
            Path(f.name).unlink()


class TestBehaviorBaseline:
    """Test BehaviorBaseline functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.baseline = BehaviorBaseline(self.temp_dir)

    def test_baseline_creation(self):
        """Test creating baselines"""
        assert self.baseline.baseline_dir.exists()
        assert isinstance(self.baseline.baselines, dict)

    def test_add_snapshot(self):
        """Test adding snapshots to baseline"""
        snapshot = BehaviorSnapshot(
            timestamp=time.time(),
            agent_config={},
            scenario="test",
            metrics={BehaviorMetric.DECISION_TIME: 1.0},
            execution_trace=[],
            context={},
            version_info={}
        )

        self.baseline.add_snapshot(snapshot, "test_scenario")

        assert "test_scenario" in self.baseline.baselines
        assert len(self.baseline.baselines["test_scenario"]) == 1

    def test_save_and_load_baseline(self):
        """Test saving and loading baselines"""
        # Create test snapshot
        snapshot = BehaviorSnapshot(
            timestamp=time.time(),
            agent_config={"test": True},
            scenario="test",
            metrics={
                BehaviorMetric.DECISION_TIME: 1.0,
                BehaviorMetric.RESOURCE_EFFICIENCY: 0.8
            },
            execution_trace=["step1"],
            context={"test": True},
            version_info={"version": "1.0.0"}
        )

        # Add and save
        self.baseline.add_snapshot(snapshot, "test_scenario")
        self.baseline.save_baseline("test_scenario", "1.0.0")

        # Create new baseline and load
        new_baseline = BehaviorBaseline(self.temp_dir)
        loaded = new_baseline.load_baseline("test_scenario", "1.0.0")

        assert loaded is True
        assert "test_scenario" in new_baseline.baselines
        assert len(new_baseline.baselines["test_scenario"]) == 1

        loaded_snapshot = new_baseline.baselines["test_scenario"][0]
        assert loaded_snapshot.agent_config["test"] is True
        assert BehaviorMetric.DECISION_TIME in loaded_snapshot.metrics

    def test_load_nonexistent_baseline(self):
        """Test loading non-existent baseline"""
        result = self.baseline.load_baseline("nonexistent", "1.0.0")
        assert result is False

    def test_get_baseline_stats(self):
        """Test getting baseline statistics"""
        # Add multiple snapshots
        for i in range(5):
            snapshot = BehaviorSnapshot(
                timestamp=time.time() + i,
                agent_config={},
                scenario="test",
                metrics={
                    BehaviorMetric.DECISION_TIME: 1.0 + i * 0.1,
                    BehaviorMetric.RESOURCE_EFFICIENCY: 0.8 + i * 0.02
                },
                execution_trace=[],
                context={},
                version_info={}
            )
            self.baseline.add_snapshot(snapshot, "test_scenario")

        stats = self.baseline.get_baseline_stats("test_scenario")

        assert BehaviorMetric.DECISION_TIME in stats
        assert BehaviorMetric.RESOURCE_EFFICIENCY in stats

        decision_stats = stats[BehaviorMetric.DECISION_TIME]
        assert "mean" in decision_stats
        assert "median" in decision_stats
        assert "stdev" in decision_stats
        assert decision_stats["count"] == 5

    def test_get_baseline_stats_empty(self):
        """Test getting stats for empty baseline"""
        stats = self.baseline.get_baseline_stats("nonexistent")
        assert stats == {}


class TestBehaviorMeasurer:
    """Test BehaviorMeasurer functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.measurer = BehaviorMeasurer()
        self.agent = MockFlexibilityAgent("test_agent")

    def test_measure_behavior(self):
        """Test basic behavior measurement"""
        context = {"test_context": True}
        snapshot = self.measurer.measure_behavior(self.agent, "test_scenario", context)

        assert snapshot.scenario == "test_scenario"
        assert snapshot.context == context
        assert len(snapshot.metrics) == len(BehaviorMetric)
        assert all(isinstance(v, float) for v in snapshot.metrics.values())

    def test_measure_consistency(self):
        """Test consistency measurement"""
        consistency = self.measurer._measure_consistency(self.agent, "test")
        assert 0.0 <= consistency <= 1.0

    def test_measure_resource_efficiency(self):
        """Test resource efficiency measurement"""
        # Test with balanced resources
        self.agent.resources = {"wood": 10, "stone": 10, "food": 10}
        efficiency1 = self.measurer._measure_resource_efficiency(self.agent)

        # Test with imbalanced resources
        self.agent.resources = {"wood": 30, "stone": 1, "food": 1}
        efficiency2 = self.measurer._measure_resource_efficiency(self.agent)

        assert 0.0 <= efficiency1 <= 1.0
        assert 0.0 <= efficiency2 <= 1.0
        # Balanced resources should be more efficient
        assert efficiency1 >= efficiency2

    def test_measure_goal_completion(self):
        """Test goal completion measurement"""
        from client.behavior_tree.nodes.base import NodeStatus

        # Test successful completion
        completion1 = self.measurer._measure_goal_completion(Mock(), NodeStatus.SUCCESS)
        assert completion1 == 1.0

        # Test running state
        completion2 = self.measurer._measure_goal_completion(Mock(), NodeStatus.RUNNING)
        assert completion2 == 0.5

        # Test failure
        completion3 = self.measurer._measure_goal_completion(Mock(), NodeStatus.FAILURE)
        assert completion3 == 0.0

        # Test no composition
        completion4 = self.measurer._measure_goal_completion(None, NodeStatus.SUCCESS)
        assert completion4 == 0.0

    def test_measure_memory_utilization(self):
        """Test memory utilization measurement"""
        # Add some memories
        self.agent.memory.remember_resource_location(0, 0, "wood", 0.8, 5)
        self.agent.memory.remember_social_interaction("partner", "trade", "success")

        utilization = self.measurer._measure_memory_utilization(self.agent)
        assert 0.0 <= utilization <= 1.0

    def test_measure_social_success(self):
        """Test social success measurement"""
        success = self.measurer._measure_social_success(self.agent)
        assert 0.0 <= success <= 1.0
        # Should be based on social personality
        expected = self.agent.personality.social / 10.0
        assert success == expected

    def test_measure_strategy_diversity(self):
        """Test strategy diversity measurement"""
        # Empty behavior history
        diversity1 = self.measurer._measure_strategy_diversity(self.agent)
        assert diversity1 == 0.0

        # Add diverse behaviors
        self.agent.behavior_history = ["gather", "explore", "combat", "social"]
        diversity2 = self.measurer._measure_strategy_diversity(self.agent)
        assert diversity2 == 1.0  # All unique

        # Add repeated behaviors
        self.agent.behavior_history = ["gather", "gather", "explore", "gather"]
        diversity3 = self.measurer._measure_strategy_diversity(self.agent)
        assert diversity3 == 0.5  # 2 unique out of 4


class TestRegressionAnalyzer:
    """Test RegressionAnalyzer functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = RegressionAnalyzer()

    def test_compare_behaviors_no_change(self):
        """Test comparison with no behavioral change"""
        baseline_stats = {
            BehaviorMetric.DECISION_TIME: {
                "mean": 1.0,
                "stdev": 0.1
            }
        }

        snapshot = BehaviorSnapshot(
            timestamp=time.time(),
            agent_config={},
            scenario="test",
            metrics={BehaviorMetric.DECISION_TIME: 1.0},  # Same as baseline
            execution_trace=[],
            context={},
            version_info={}
        )

        regressions = self.analyzer.compare_behaviors(baseline_stats, snapshot)
        # Should be no significant regressions for identical values
        assert len(regressions) == 0

    def test_compare_behaviors_with_change(self):
        """Test comparison with behavioral changes"""
        baseline_stats = {
            BehaviorMetric.DECISION_TIME: {
                "mean": 1.0,
                "stdev": 0.1
            }
        }

        snapshot = BehaviorSnapshot(
            timestamp=time.time(),
            agent_config={},
            scenario="test",
            metrics={BehaviorMetric.DECISION_TIME: 1.5},  # 50% increase
            execution_trace=[],
            context={},
            version_info={}
        )

        regressions = self.analyzer.compare_behaviors(baseline_stats, snapshot)
        assert len(regressions) == 1

        regression = regressions[0]
        assert regression.metric == BehaviorMetric.DECISION_TIME
        assert regression.baseline_value == 1.0
        assert regression.current_value == 1.5
        assert regression.change_percentage == 50.0

    def test_determine_severity(self):
        """Test severity determination logic"""
        # Critical regression
        severity1 = self.analyzer._determine_severity(
            BehaviorMetric.DECISION_TIME, 60.0, 0.95
        )
        assert severity1 == RegressionSeverity.CRITICAL

        # High regression
        severity2 = self.analyzer._determine_severity(
            BehaviorMetric.DECISION_TIME, 35.0, 0.8
        )
        assert severity2 == RegressionSeverity.HIGH

        # Medium regression
        severity3 = self.analyzer._determine_severity(
            BehaviorMetric.DECISION_TIME, 20.0, 0.6
        )
        assert severity3 == RegressionSeverity.MEDIUM

        # Low regression
        severity4 = self.analyzer._determine_severity(
            BehaviorMetric.DECISION_TIME, 8.0, 0.4
        )
        assert severity4 == RegressionSeverity.LOW

        # Info level
        severity5 = self.analyzer._determine_severity(
            BehaviorMetric.DECISION_TIME, 3.0, 0.2
        )
        assert severity5 == RegressionSeverity.INFO

    def test_generate_description(self):
        """Test description generation"""
        desc1 = self.analyzer._generate_description(
            BehaviorMetric.DECISION_TIME, 25.0, 0.8
        )
        assert "decision_time" in desc1
        assert "increased" in desc1
        assert "25.0%" in desc1

        desc2 = self.analyzer._generate_description(
            BehaviorMetric.RESOURCE_EFFICIENCY, -15.0, 0.6
        )
        assert "decreased" in desc2
        assert "15.0%" in desc2

    def test_generate_report(self):
        """Test report generation"""
        baseline_stats = {
            BehaviorMetric.DECISION_TIME: {"mean": 1.0, "stdev": 0.1},
            BehaviorMetric.RESOURCE_EFFICIENCY: {"mean": 0.8, "stdev": 0.05}
        }

        snapshot = BehaviorSnapshot(
            timestamp=time.time(),
            agent_config={"test": True},
            scenario="test_scenario",
            metrics={
                BehaviorMetric.DECISION_TIME: 1.8,  # 80% increase - critical
                BehaviorMetric.RESOURCE_EFFICIENCY: 0.7  # 12.5% decrease - medium
            },
            execution_trace=[],
            context={},
            version_info={}
        )

        report = self.analyzer.generate_report(
            "test_scenario", baseline_stats, snapshot, time.time() - 3600
        )

        assert report.scenario == "test_scenario"
        assert len(report.regressions) >= 1  # Should detect the critical regression
        assert report.overall_score < 1.0  # Should be less than perfect
        assert "CRITICAL" in report.summary or "HIGH" in report.summary

    def test_generate_recommendations(self):
        """Test recommendation generation"""
        regressions = [
            RegressionResult(
                BehaviorMetric.DECISION_TIME, 1.0, 2.0, 100.0,
                RegressionSeverity.CRITICAL, 0.9, "Critical performance issue"
            ),
            RegressionResult(
                BehaviorMetric.RESOURCE_EFFICIENCY, 0.8, 0.6, -25.0,
                RegressionSeverity.HIGH, 0.7, "Efficiency degradation"
            )
        ]

        recommendations = self.analyzer._generate_recommendations(regressions)

        assert len(recommendations) > 0
        assert any("URGENT" in rec for rec in recommendations)
        assert any("Performance" in rec for rec in recommendations)


class TestBehaviorRegressionTester:
    """Test BehaviorRegressionTester integration"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.tester = BehaviorRegressionTester(self.temp_dir)

    def test_create_agent_from_config(self):
        """Test agent creation from configuration"""
        config = {
            "agent_id": "test_agent",
            "personality": {"combat": 7.0, "exploration": 3.0, "social": 8.0},
            "resources": {"wood": 15, "stone": 8},
            "health": 85.0
        }

        agent = self.tester._create_agent_from_config(config)

        assert agent.id == "test_agent"
        assert agent.personality.combat == 7.0
        assert agent.personality.exploration == 3.0
        assert agent.personality.social == 8.0
        assert agent.resources["wood"] == 15
        assert agent.resources["stone"] == 8
        assert agent.health == 85.0

    def test_create_baseline(self):
        """Test baseline creation"""
        agent_configs = [
            {
                "agent_id": "agent1",
                "personality": {"combat": 5.0, "exploration": 5.0, "social": 5.0}
            },
            {
                "agent_id": "agent2",
                "personality": {"combat": 7.0, "exploration": 3.0, "social": 6.0}
            }
        ]

        context = {"scenario_type": "test", "difficulty": "easy"}
        result = self.tester.create_baseline("test_scenario", "1.0.0", agent_configs, context)

        assert result is True
        # Check that baseline file was created
        baseline_file = Path(self.temp_dir) / "test_scenario_1.0.0_baseline.json"
        assert baseline_file.exists()

    def test_test_regression_without_baseline(self):
        """Test regression testing without existing baseline"""
        agent_config = {"agent_id": "test_agent"}
        context = {}

        with pytest.raises(ValueError, match="Baseline not found"):
            self.tester.test_regression("nonexistent", "1.0.0", agent_config, context)

    def test_test_regression_with_baseline(self):
        """Test regression testing with existing baseline"""
        # First create a baseline
        agent_configs = [{"agent_id": "baseline_agent"}]
        context = {"test": True}
        self.tester.create_baseline("test_scenario", "1.0.0", agent_configs, context)

        # Then test regression
        agent_config = {"agent_id": "current_agent"}
        report = self.tester.test_regression("test_scenario", "1.0.0", agent_config, context)

        assert isinstance(report, RegressionReport)
        assert report.scenario == "test_scenario"

    def test_run_regression_suite(self):
        """Test running regression suite"""
        # Create baselines first
        agent_configs = [{"agent_id": "suite_agent"}]
        for scenario in ["scenario1", "scenario2"]:
            self.tester.create_baseline(scenario, "1.0.0", agent_configs, {})

        # Run regression suite
        scenarios = ["scenario1", "scenario2"]
        contexts = {"scenario1": {}, "scenario2": {}}
        reports = self.tester.run_regression_suite(scenarios, "1.0.0", agent_configs, contexts)

        assert len(reports) == 2  # One report per scenario
        assert all(isinstance(r, RegressionReport) for r in reports)

    def test_run_regression_suite_with_errors(self):
        """Test regression suite handling errors"""
        # Don't create baselines - should cause errors
        scenarios = ["nonexistent"]
        agent_configs = [{"agent_id": "error_agent"}]
        contexts = {"nonexistent": {}}

        reports = self.tester.run_regression_suite(scenarios, "1.0.0", agent_configs, contexts)

        assert len(reports) == 1
        assert "ERROR" in reports[0].summary


class TestConvenienceFunctions:
    """Test convenience functions"""

    @patch('tests.regression.behavioral_regression.BehaviorRegressionTester')
    def test_create_standard_baseline(self, mock_tester_class):
        """Test creating standard baseline"""
        mock_tester = Mock()
        mock_tester_class.return_value = mock_tester
        mock_tester.create_baseline.return_value = True

        result = create_standard_baseline("2.0.0")

        assert result is True
        # Should have called create_baseline for each standard scenario
        assert mock_tester.create_baseline.call_count == 4

    @patch('tests.regression.behavioral_regression.BehaviorRegressionTester')
    def test_quick_regression_test(self, mock_tester_class):
        """Test quick regression test"""
        mock_tester = Mock()
        mock_tester_class.return_value = mock_tester
        mock_report = Mock(spec=RegressionReport)
        mock_tester.test_regression.return_value = mock_report

        result = quick_regression_test("custom_scenario", "2.0.0")

        assert result == mock_report
        mock_tester.test_regression.assert_called_once()


class TestIntegration:
    """Integration tests for regression framework"""

    def setup_method(self):
        """Set up integration test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

    def test_end_to_end_baseline_and_regression(self):
        """Test complete end-to-end baseline creation and regression testing"""
        tester = BehaviorRegressionTester(self.temp_dir)

        # Create baseline with one agent configuration
        baseline_configs = [
            {
                "agent_id": "baseline_agent",
                "personality": {"combat": 5.0, "exploration": 5.0, "social": 5.0},
                "resources": {"wood": 10, "food": 20},
                "health": 100.0
            }
        ]

        context = {"scenario_type": "integration_test"}
        baseline_created = tester.create_baseline("integration", "1.0.0", baseline_configs, context)
        assert baseline_created

        # Test with slightly different agent (should show some differences)
        test_config = {
            "agent_id": "test_agent",
            "personality": {"combat": 6.0, "exploration": 4.0, "social": 5.0},  # Different personality
            "resources": {"wood": 8, "food": 22},  # Different resources
            "health": 95.0  # Different health
        }

        report = tester.test_regression("integration", "1.0.0", test_config, context)

        assert isinstance(report, RegressionReport)
        assert report.scenario == "integration"
        assert 0.0 <= report.overall_score <= 1.0

    def test_baseline_persistence(self):
        """Test that baselines persist across tester instances"""
        # Create baseline with first tester instance
        tester1 = BehaviorRegressionTester(self.temp_dir)
        agent_configs = [{"agent_id": "persist_agent"}]
        context = {"persistence_test": True}

        tester1.create_baseline("persist_scenario", "1.0.0", agent_configs, context)

        # Use second tester instance to load baseline
        tester2 = BehaviorRegressionTester(self.temp_dir)
        report = tester2.test_regression("persist_scenario", "1.0.0", agent_configs[0], context)

        assert isinstance(report, RegressionReport)
        assert report.scenario == "persist_scenario"

    def test_multiple_baseline_versions(self):
        """Test handling multiple baseline versions"""
        tester = BehaviorRegressionTester(self.temp_dir)
        agent_configs = [{"agent_id": "version_agent"}]
        context = {}

        # Create multiple baseline versions with time separation
        tester.create_baseline("version_scenario", "1.0.0", agent_configs, context)
        time.sleep(0.01)  # Small delay to ensure different timestamps
        tester.create_baseline("version_scenario", "2.0.0", agent_configs, context)

        # Test against both versions
        report1 = tester.test_regression("version_scenario", "1.0.0", agent_configs[0], context)
        report2 = tester.test_regression("version_scenario", "2.0.0", agent_configs[0], context)

        # Baseline timestamps should be different (or at least files should be different)
        assert report1.scenario == "version_scenario"
        assert report2.scenario == "version_scenario"

    def test_large_behavioral_differences(self):
        """Test detection of large behavioral differences"""
        tester = BehaviorRegressionTester(self.temp_dir)

        # Create baseline with conservative agent
        baseline_config = {
            "agent_id": "conservative_agent",
            "personality": {"combat": 2.0, "exploration": 3.0, "social": 8.0},
            "resources": {"wood": 20, "food": 30},
            "health": 100.0
        }

        context = {"scenario_type": "behavioral_diff_test"}
        tester.create_baseline("behavioral_diff", "1.0.0", [baseline_config], context)

        # Test with aggressive agent (very different personality)
        aggressive_config = {
            "agent_id": "aggressive_agent",
            "personality": {"combat": 9.0, "exploration": 8.0, "social": 2.0},
            "resources": {"wood": 5, "food": 10},
            "health": 80.0
        }

        report = tester.test_regression("behavioral_diff", "1.0.0", aggressive_config, context)

        # Should detect some behavioral differences
        assert len(report.regressions) > 0
        # Overall score should reflect the differences
        assert report.overall_score < 1.0


if __name__ == "__main__":
    pytest.main([__file__])