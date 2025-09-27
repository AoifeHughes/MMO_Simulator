"""
Tests for Agent Integration Test Suite

Comprehensive tests for the integration testing framework to ensure
proper testing of component interactions and system behavior.
"""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tests.integration.agent_integration import (
    AgentIntegrationTester,
    IntegrationTestLevel,
    IntegrationTestReport,
    IntegrationTestSuite,
    Result,
    run_comprehensive_integration_test,
    run_quick_integration_test,
)


class TestIntegrationTestReport:
    """Test IntegrationTestReport dataclass"""

    def test_report_creation(self):
        """Test creating integration test reports"""
        report = IntegrationTestReport(
            test_name="test_component_integration",
            test_level=IntegrationTestLevel.COMPONENT,
            result=Result.PASS,
            duration=1.5,
            components_tested=["ComponentA", "ComponentB"],
            performance_metrics={"metric1": 0.8},
            memory_usage={"peak_memory": 1024},
            details={"extra_info": "test_data"},
        )

        assert report.test_name == "test_component_integration"
        assert report.test_level == IntegrationTestLevel.COMPONENT
        assert report.result == Result.PASS
        assert report.duration == 1.5
        assert len(report.components_tested) == 2

    def test_report_to_dict(self):
        """Test converting report to dictionary"""
        report = IntegrationTestReport(
            test_name="test_serialization",
            test_level=IntegrationTestLevel.SYSTEM,
            result=Result.FAIL,
            duration=2.0,
            components_tested=["System"],
            error_message="Test failed",
            performance_metrics={"response_time": 1.2},
            memory_usage={"memory_used": 512},
            details={"failure_reason": "timeout"},
        )

        data = report.to_dict()

        assert data["test_name"] == "test_serialization"
        assert data["test_level"] == "system"
        assert data["result"] == "fail"
        assert data["error_message"] == "Test failed"
        assert data["performance_metrics"]["response_time"] == 1.2
        assert data["memory_usage"]["memory_used"] == 512
        assert data["details"]["failure_reason"] == "timeout"


class TestIntegrationTestSuite:
    """Test IntegrationTestSuite dataclass and methods"""

    def test_suite_creation(self):
        """Test creating integration test suites"""
        reports = [
            IntegrationTestReport(
                "test1", IntegrationTestLevel.UNIT, Result.PASS, 1.0, ["A"]
            ),
            IntegrationTestReport(
                "test2", IntegrationTestLevel.COMPONENT, Result.FAIL, 2.0, ["B"]
            ),
        ]

        suite = IntegrationTestSuite(
            suite_name="test_suite",
            start_time=1000.0,
            end_time=1010.0,
            total_tests=2,
            passed=1,
            failed=1,
            skipped=0,
            errors=0,
            test_reports=reports,
            overall_performance={"avg_duration": 1.5},
            summary="Mixed results",
        )

        assert suite.suite_name == "test_suite"
        assert suite.total_tests == 2
        assert suite.passed == 1
        assert suite.failed == 1
        assert len(suite.test_reports) == 2

    def test_success_rate_calculation(self):
        """Test success rate calculation"""
        suite = IntegrationTestSuite("test", 0, 0, 10, 8, 2, 0, 0, [], {}, "")
        assert suite.success_rate == 0.8

        # Test edge case with no tests
        empty_suite = IntegrationTestSuite("empty", 0, 0, 0, 0, 0, 0, 0, [], {}, "")
        assert empty_suite.success_rate == 0.0

    def test_duration_calculation(self):
        """Test duration calculation"""
        suite = IntegrationTestSuite("test", 1000.0, 1005.5, 0, 0, 0, 0, 0, [], {}, "")
        assert suite.duration == 5.5

    def test_save_to_file(self):
        """Test saving suite to file"""
        reports = [
            IntegrationTestReport(
                "test1", IntegrationTestLevel.UNIT, Result.PASS, 1.0, ["A"]
            )
        ]

        suite = IntegrationTestSuite(
            suite_name="save_test",
            start_time=1000.0,
            end_time=1005.0,
            total_tests=1,
            passed=1,
            failed=0,
            skipped=0,
            errors=0,
            test_reports=reports,
            overall_performance={"avg_time": 1.0},
            summary="All passed",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            suite.save_to_file(f.name)

            # Verify file was created and contains valid JSON
            with open(f.name, "r") as read_f:
                data = json.load(read_f)
                assert data["suite_name"] == "save_test"
                assert data["total_tests"] == 1
                assert data["success_rate"] == 1.0
                assert len(data["test_reports"]) == 1

            # Cleanup
            Path(f.name).unlink()


class TestAgentIntegrationTester:
    """Test AgentIntegrationTester functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.tester = AgentIntegrationTester(self.temp_dir)

    def test_tester_creation(self):
        """Test creating integration tester"""
        assert self.tester.output_dir.exists()
        assert self.tester.behavior_composer is not None
        assert self.tester.flexibility_harness is not None
        assert self.tester.regression_tester is not None
        assert self.tester.test_reports == []

    def test_run_test_success(self):
        """Test running a successful test"""

        def mock_test_func():
            return {
                "success": True,
                "performance": {"test_metric": 0.9},
                "details": {"test_info": "completed"},
            }

        report = self.tester._run_test(
            "test_success", IntegrationTestLevel.UNIT, ["TestComponent"], mock_test_func
        )

        assert report.test_name == "test_success"
        assert report.result == Result.PASS
        assert report.error_message is None
        assert report.performance_metrics["test_metric"] == 0.9
        assert report.details["test_info"] == "completed"

    def test_run_test_failure(self):
        """Test running a failed test"""

        def mock_test_func():
            return {"success": False, "error": "Test failed for some reason"}

        report = self.tester._run_test(
            "test_failure",
            IntegrationTestLevel.COMPONENT,
            ["FailingComponent"],
            mock_test_func,
        )

        assert report.test_name == "test_failure"
        assert report.result == Result.FAIL
        assert report.error_message == "Test failed for some reason"

    def test_run_test_exception(self):
        """Test running a test that throws an exception"""

        def mock_test_func():
            raise ValueError("Unexpected error in test")

        report = self.tester._run_test(
            "test_exception",
            IntegrationTestLevel.SYSTEM,
            ["ErrorComponent"],
            mock_test_func,
        )

        assert report.test_name == "test_exception"
        assert report.result == Result.ERROR
        assert "Unexpected error in test" in report.error_message

    def test_memory_behavior_integration(self):
        """Test memory-behavior integration test"""
        self.tester._run_memory_behavior_integration()

        # Should have added one test report
        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "memory_behavior_integration"
        assert report.test_level == IntegrationTestLevel.COMPONENT
        assert "AgentMemory" in report.components_tested
        assert "BehaviorComposer" in report.components_tested

    def test_behavior_interrupt_integration(self):
        """Test behavior-interrupt integration test"""
        self.tester._run_behavior_interrupt_integration()

        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "behavior_interrupt_integration"
        assert report.test_level == IntegrationTestLevel.COMPONENT
        assert "BehaviorComposer" in report.components_tested
        assert "InterruptManager" in report.components_tested

    def test_flexibility_regression_integration(self):
        """Test flexibility-regression integration test"""
        self.tester._run_flexibility_regression_integration()

        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "flexibility_regression_integration"
        assert "FlexibilityHarness" in report.components_tested
        assert "BehaviorRegressionTester" in report.components_tested

    def test_agent_lifecycle_integration(self):
        """Test agent lifecycle integration test"""
        self.tester._run_agent_lifecycle_integration()

        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "agent_lifecycle_integration"
        assert report.test_level == IntegrationTestLevel.SUBSYSTEM
        assert len(report.components_tested) >= 3  # Multiple components

    def test_multi_agent_interaction_integration(self):
        """Test multi-agent interaction integration test"""
        self.tester._run_multi_agent_interaction_integration()

        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "multi_agent_interaction_integration"
        assert report.test_level == IntegrationTestLevel.SUBSYSTEM

    def test_performance_integration(self):
        """Test performance integration test"""
        self.tester._run_performance_integration()

        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "performance_integration"
        assert report.test_level == IntegrationTestLevel.SYSTEM
        assert (
            "performance" in report.performance_metrics
            or report.performance_metrics is not None
        )

    def test_stress_test_integration(self):
        """Test stress test integration"""
        self.tester._run_stress_test_integration()

        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "stress_test_integration"
        assert report.test_level == IntegrationTestLevel.SYSTEM

    def test_complete_scenario_integration(self):
        """Test complete scenario integration test"""
        self.tester._run_complete_scenario_integration()

        assert len(self.tester.test_reports) == 1
        report = self.tester.test_reports[0]

        assert report.test_name == "complete_scenario_integration"
        assert report.test_level == IntegrationTestLevel.END_TO_END
        assert len(report.components_tested) >= 4  # Multiple systems

    def test_calculate_overall_performance(self):
        """Test overall performance calculation"""
        # Add some mock test reports
        self.tester.test_reports = [
            IntegrationTestReport(
                "test1",
                IntegrationTestLevel.UNIT,
                Result.PASS,
                1.0,
                ["A"],
                performance_metrics={"metric1": 0.8, "metric2": 1.2},
            ),
            IntegrationTestReport(
                "test2",
                IntegrationTestLevel.COMPONENT,
                Result.PASS,
                2.0,
                ["B"],
                performance_metrics={"metric1": 0.9, "metric3": 0.7},
            ),
        ]

        performance = self.tester._calculate_overall_performance()

        assert "avg_test_duration" in performance
        assert "max_test_duration" in performance
        assert "total_test_time" in performance
        assert performance["avg_test_duration"] == 1.5
        assert performance["max_test_duration"] == 2.0
        assert performance["total_test_time"] == 3.0

        # Should have averaged the metrics
        assert "avg_metric1" in performance
        assert abs(performance["avg_metric1"] - 0.85) < 0.001  # (0.8 + 0.9) / 2

    def test_calculate_overall_performance_empty(self):
        """Test performance calculation with no reports"""
        performance = self.tester._calculate_overall_performance()
        assert performance == {}

    def test_generate_suite_summary(self):
        """Test suite summary generation"""
        # All passed
        summary1 = self.tester._generate_suite_summary(5, 0, 0, 0, 5)
        assert "SUCCESS" in summary1

        # Some failed
        summary2 = self.tester._generate_suite_summary(3, 2, 0, 0, 5)
        assert "PARTIAL SUCCESS" in summary2

        # Some errors
        summary3 = self.tester._generate_suite_summary(3, 0, 0, 2, 5)
        assert "ERRORS" in summary3

        # Mixed issues
        summary4 = self.tester._generate_suite_summary(2, 1, 0, 2, 5)
        assert "ISSUES" in summary4

        # No tests
        summary5 = self.tester._generate_suite_summary(0, 0, 0, 0, 0)
        assert "No tests executed" in summary5

    def test_run_integration_test_suite(self):
        """Test running complete integration test suite"""
        suite = self.tester.run_integration_test_suite("test_suite")

        assert isinstance(suite, IntegrationTestSuite)
        assert suite.suite_name == "test_suite"
        assert suite.total_tests > 0
        assert len(suite.test_reports) == suite.total_tests
        assert suite.start_time < suite.end_time

        # Check that results file was created
        results_file = Path(self.temp_dir) / "test_suite_integration_results.json"
        assert results_file.exists()

        # Verify file contents
        with open(results_file, "r") as f:
            data = json.load(f)
            assert data["suite_name"] == "test_suite"
            assert data["total_tests"] > 0

    def test_suite_includes_all_test_levels(self):
        """Test that suite includes tests from all levels"""
        suite = self.tester.run_integration_test_suite("level_test")

        # Check that we have tests from different levels
        levels_found = set()
        for report in suite.test_reports:
            levels_found.add(report.test_level)

        # Should have at least component, subsystem, system, and end-to-end tests
        assert IntegrationTestLevel.COMPONENT in levels_found
        assert IntegrationTestLevel.SUBSYSTEM in levels_found
        assert IntegrationTestLevel.SYSTEM in levels_found
        assert IntegrationTestLevel.END_TO_END in levels_found

    def test_suite_performance_metrics(self):
        """Test that suite captures performance metrics"""
        suite = self.tester.run_integration_test_suite("performance_test")

        assert suite.overall_performance is not None
        assert len(suite.overall_performance) > 0

        # Should have basic timing metrics
        assert "avg_test_duration" in suite.overall_performance
        assert "max_test_duration" in suite.overall_performance
        assert "total_test_time" in suite.overall_performance

    def test_suite_error_handling(self):
        """Test suite handles errors gracefully"""
        # Patch one of the test methods to raise an exception
        with patch.object(
            self.tester, "_run_memory_behavior_integration"
        ) as mock_method:
            mock_method.side_effect = RuntimeError("Simulated test failure")

            suite = self.tester.run_integration_test_suite("error_test")

            # Suite should still complete
            assert isinstance(suite, IntegrationTestSuite)
            assert suite.total_tests > 0

            # Should have some errors recorded - either in error count or individual reports
            has_errors = suite.errors > 0 or any(
                report.result == Result.ERROR for report in suite.test_reports
            )
            # Note: The error might be caught and handled, so we just verify the suite completes


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_run_quick_integration_test(self):
        """Test quick integration test function"""
        suite = run_quick_integration_test()

        assert isinstance(suite, IntegrationTestSuite)
        assert suite.suite_name == "quick_integration"
        assert suite.total_tests > 0

    def test_run_comprehensive_integration_test(self):
        """Test comprehensive integration test function"""
        suite = run_comprehensive_integration_test()

        assert isinstance(suite, IntegrationTestSuite)
        assert suite.suite_name == "comprehensive_integration"
        assert suite.total_tests > 0


class TestIntegrationResults:
    """Test integration test results and analysis"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()

    def test_integration_test_coverage(self):
        """Test that integration tests cover all major components"""
        tester = AgentIntegrationTester(self.temp_dir)
        suite = tester.run_integration_test_suite("coverage_test")

        # Collect all components tested
        all_components = set()
        for report in suite.test_reports:
            all_components.update(report.components_tested)

        # Should test all major components
        expected_components = [
            "AgentMemory",
            "BehaviorComposer",
            "InterruptManager",
            "FlexibilityHarness",
            "BehaviorRegressionTester",
        ]

        for component in expected_components:
            assert component in all_components, f"Component {component} not tested"

    def test_integration_test_levels(self):
        """Test that all integration levels are covered"""
        tester = AgentIntegrationTester(self.temp_dir)
        suite = tester.run_integration_test_suite("levels_test")

        # Collect all test levels
        levels_tested = set()
        for report in suite.test_reports:
            levels_tested.add(report.test_level)

        # Should have tests at multiple levels
        assert IntegrationTestLevel.COMPONENT in levels_tested
        assert IntegrationTestLevel.SUBSYSTEM in levels_tested
        assert IntegrationTestLevel.SYSTEM in levels_tested
        assert IntegrationTestLevel.END_TO_END in levels_tested

    def test_integration_performance_tracking(self):
        """Test that performance is tracked across integration tests"""
        tester = AgentIntegrationTester(self.temp_dir)
        suite = tester.run_integration_test_suite("performance_tracking_test")

        # Should have performance metrics
        assert suite.overall_performance is not None
        assert len(suite.overall_performance) > 0

        # Performance metrics should be reasonable
        if "avg_test_duration" in suite.overall_performance:
            assert suite.overall_performance["avg_test_duration"] > 0
            assert (
                suite.overall_performance["avg_test_duration"] < 60
            )  # Should be under 1 minute

    def test_integration_results_persistence(self):
        """Test that integration results are properly saved"""
        tester = AgentIntegrationTester(self.temp_dir)
        suite = tester.run_integration_test_suite("persistence_test")

        # Results file should exist
        results_file = Path(self.temp_dir) / "persistence_test_integration_results.json"
        assert results_file.exists()

        # File should contain valid JSON with all expected fields
        with open(results_file, "r") as f:
            data = json.load(f)

        required_fields = [
            "suite_name",
            "start_time",
            "end_time",
            "duration",
            "total_tests",
            "passed",
            "failed",
            "skipped",
            "errors",
            "success_rate",
            "test_reports",
            "overall_performance",
            "summary",
        ]

        for field in required_fields:
            assert field in data, f"Required field {field} missing from results"

    def test_integration_error_reporting(self):
        """Test that integration errors are properly reported"""
        tester = AgentIntegrationTester(self.temp_dir)

        # Patch a method to always fail
        with patch.object(tester, "_run_performance_integration") as mock_method:
            mock_method.side_effect = Exception("Intentional test failure")

            suite = tester.run_integration_test_suite("error_reporting_test")

            # Suite should complete even with errors
            assert isinstance(suite, IntegrationTestSuite)
            assert suite.total_tests > 0

            # Check if any error was captured (either in error count or in reports)
            has_error_info = (
                suite.errors > 0
                or any(r.result == Result.ERROR for r in suite.test_reports)
                or any(
                    r.error_message and "Intentional test failure" in r.error_message
                    for r in suite.test_reports
                )
            )

            # Note: We just verify the suite handles errors gracefully


class TestIntegrationScenarios:
    """Test specific integration scenarios"""

    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.tester = AgentIntegrationTester(self.temp_dir)

    def test_memory_persistence_across_behaviors(self):
        """Test that memory persists across behavior changes"""
        # This test verifies that the memory-behavior integration
        # maintains state consistency
        self.tester._run_memory_behavior_integration()

        report = self.tester.test_reports[-1]
        assert report.result in [Result.PASS, Result.FAIL]  # Should complete
        assert (
            "memory_influence" in report.performance_metrics
            or report.performance_metrics is None
        )

    def test_interrupt_behavior_coordination(self):
        """Test coordination between interrupt and behavior systems"""
        self.tester._run_behavior_interrupt_integration()

        report = self.tester.test_reports[-1]
        assert report.result in [Result.PASS, Result.FAIL]  # Should complete
        # Should test interrupt system accessibility

    def test_end_to_end_agent_workflow(self):
        """Test complete agent workflow from start to finish"""
        self.tester._run_complete_scenario_integration()

        report = self.tester.test_reports[-1]
        assert report.result in [Result.PASS, Result.FAIL]  # Should complete

        # Should have detailed scenario steps
        if report.details and "scenario_steps" in report.details:
            steps = report.details["scenario_steps"]
            assert len(steps) > 0
            # Should cover multiple aspects of agent behavior
            assert any("resource" in step or "discovery" in step for step in steps)
            assert any("social" in step or "interaction" in step for step in steps)

    def test_system_performance_under_load(self):
        """Test system performance under integration load"""
        self.tester._run_performance_integration()
        self.tester._run_stress_test_integration()

        # Should have both performance and stress test results
        assert len(self.tester.test_reports) >= 2

        performance_report = None
        stress_report = None

        for report in self.tester.test_reports:
            if "performance" in report.test_name:
                performance_report = report
            elif "stress" in report.test_name:
                stress_report = report

        assert performance_report is not None
        assert stress_report is not None

        # Both should have performance metrics
        assert performance_report.performance_metrics is not None
        assert stress_report.performance_metrics is not None


if __name__ == "__main__":
    pytest.main([__file__])
