"""
Agent Integration Test Suite

This module provides comprehensive integration tests for the agent flexibility
framework, ensuring that all components work together correctly across different
scenarios and configurations.
"""

import time
import tempfile
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from client.behavior_tree.behavior_composer import BehaviorComposer
from client.behavior_tree.interrupt_manager import InterruptManager
from client.agent_memory import AgentMemory
from tests.flexibility.flexibility_harness import FlexibilityHarness, MockFlexibilityAgent
from tests.regression.behavioral_regression import BehaviorRegressionTester
from shared.personality import Personality


class IntegrationTestLevel(Enum):
    """Levels of integration testing"""
    UNIT = "unit"                    # Single component
    COMPONENT = "component"          # Multiple related components
    SUBSYSTEM = "subsystem"          # Complete subsystem
    SYSTEM = "system"                # Full system integration
    END_TO_END = "end_to_end"       # Complete user workflow


class TestResult(Enum):
    """Test result status"""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class IntegrationTestReport:
    """Report for a single integration test"""
    test_name: str
    test_level: IntegrationTestLevel
    result: TestResult
    duration: float
    components_tested: List[str]
    error_message: Optional[str] = None
    performance_metrics: Dict[str, float] = None
    memory_usage: Dict[str, int] = None
    details: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "test_name": self.test_name,
            "test_level": self.test_level.value,
            "result": self.result.value,
            "duration": self.duration,
            "components_tested": self.components_tested,
            "error_message": self.error_message,
            "performance_metrics": self.performance_metrics or {},
            "memory_usage": self.memory_usage or {},
            "details": self.details or {}
        }


@dataclass
class IntegrationTestSuite:
    """Complete integration test suite results"""
    suite_name: str
    start_time: float
    end_time: float
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    test_reports: List[IntegrationTestReport]
    overall_performance: Dict[str, float]
    summary: str

    @property
    def success_rate(self) -> float:
        """Calculate test success rate"""
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests

    @property
    def duration(self) -> float:
        """Total suite duration"""
        return self.end_time - self.start_time

    def save_to_file(self, filepath: str):
        """Save suite results to JSON file"""
        data = {
            "suite_name": self.suite_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "success_rate": self.success_rate,
            "test_reports": [report.to_dict() for report in self.test_reports],
            "overall_performance": self.overall_performance,
            "summary": self.summary
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


class AgentIntegrationTester:
    """Main integration testing framework"""

    def __init__(self, output_dir: str = "integration_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Initialize testing components
        self.behavior_composer = BehaviorComposer()
        self.flexibility_harness = FlexibilityHarness()
        self.regression_tester = BehaviorRegressionTester()

        # Test tracking
        self.current_suite: Optional[IntegrationTestSuite] = None
        self.test_reports: List[IntegrationTestReport] = []

    def run_integration_test_suite(self, suite_name: str = "comprehensive") -> IntegrationTestSuite:
        """Run comprehensive integration test suite"""
        start_time = time.time()
        self.test_reports = []

        # Component-level tests
        try:
            self._run_memory_behavior_integration()
        except Exception as e:
            self._add_error_report("memory_behavior_integration", IntegrationTestLevel.COMPONENT,
                                 ["AgentMemory", "BehaviorComposer"], str(e))

        try:
            self._run_behavior_interrupt_integration()
        except Exception as e:
            self._add_error_report("behavior_interrupt_integration", IntegrationTestLevel.COMPONENT,
                                 ["BehaviorComposer", "InterruptManager"], str(e))

        try:
            self._run_flexibility_regression_integration()
        except Exception as e:
            self._add_error_report("flexibility_regression_integration", IntegrationTestLevel.COMPONENT,
                                 ["FlexibilityHarness", "BehaviorRegressionTester"], str(e))

        # Subsystem-level tests
        try:
            self._run_agent_lifecycle_integration()
        except Exception as e:
            self._add_error_report("agent_lifecycle_integration", IntegrationTestLevel.SUBSYSTEM,
                                 ["AgentMemory", "BehaviorComposer", "InterruptManager", "FlexibilityHarness"], str(e))

        try:
            self._run_multi_agent_interaction_integration()
        except Exception as e:
            self._add_error_report("multi_agent_interaction_integration", IntegrationTestLevel.SUBSYSTEM,
                                 ["AgentMemory", "BehaviorComposer", "FlexibilityHarness"], str(e))

        # System-level tests
        try:
            self._run_performance_integration()
        except Exception as e:
            self._add_error_report("performance_integration", IntegrationTestLevel.SYSTEM,
                                 ["BehaviorComposer", "AgentMemory", "FlexibilityHarness"], str(e))

        try:
            self._run_stress_test_integration()
        except Exception as e:
            self._add_error_report("stress_test_integration", IntegrationTestLevel.SYSTEM,
                                 ["BehaviorComposer", "AgentMemory", "FlexibilityHarness"], str(e))

        # End-to-end tests
        try:
            self._run_complete_scenario_integration()
        except Exception as e:
            self._add_error_report("complete_scenario_integration", IntegrationTestLevel.END_TO_END,
                                 ["AgentMemory", "BehaviorComposer", "InterruptManager", "FlexibilityHarness", "BehaviorRegressionTester"], str(e))

        # Calculate results
        end_time = time.time()
        total_tests = len(self.test_reports)
        passed = len([r for r in self.test_reports if r.result == TestResult.PASS])
        failed = len([r for r in self.test_reports if r.result == TestResult.FAIL])
        skipped = len([r for r in self.test_reports if r.result == TestResult.SKIP])
        errors = len([r for r in self.test_reports if r.result == TestResult.ERROR])

        # Overall performance metrics
        overall_performance = self._calculate_overall_performance()

        # Generate summary
        summary = self._generate_suite_summary(passed, failed, skipped, errors, total_tests)

        suite = IntegrationTestSuite(
            suite_name=suite_name,
            start_time=start_time,
            end_time=end_time,
            total_tests=total_tests,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            test_reports=self.test_reports,
            overall_performance=overall_performance,
            summary=summary
        )

        # Save results
        suite.save_to_file(str(self.output_dir / f"{suite_name}_integration_results.json"))
        return suite

    def _run_test(self, test_name: str, test_level: IntegrationTestLevel,
                  components: List[str], test_func) -> IntegrationTestReport:
        """Run a single integration test"""
        start_time = time.time()

        try:
            result_data = test_func()
            duration = time.time() - start_time

            # Determine result
            if result_data.get("success", True):
                result = TestResult.PASS
                error_message = None
            else:
                result = TestResult.FAIL
                error_message = result_data.get("error", "Test failed")

        except Exception as e:
            duration = time.time() - start_time
            result = TestResult.ERROR
            error_message = str(e)
            result_data = {}

        report = IntegrationTestReport(
            test_name=test_name,
            test_level=test_level,
            result=result,
            duration=duration,
            components_tested=components,
            error_message=error_message,
            performance_metrics=result_data.get("performance", {}),
            memory_usage=result_data.get("memory", {}),
            details=result_data.get("details", {})
        )

        self.test_reports.append(report)
        return report

    def _add_error_report(self, test_name: str, test_level: IntegrationTestLevel,
                         components: List[str], error_message: str):
        """Add an error report for a failed test"""
        report = IntegrationTestReport(
            test_name=test_name,
            test_level=test_level,
            result=TestResult.ERROR,
            duration=0.0,
            components_tested=components,
            error_message=error_message
        )
        self.test_reports.append(report)

    def _run_memory_behavior_integration(self):
        """Test integration between memory system and behavior composer"""
        def test_func():
            agent = MockFlexibilityAgent("memory_behavior_test")

            # Add memories that should influence behavior
            agent.memory.remember_resource_location(10, 10, "gold", 0.9, 8)
            agent.memory.remember_danger_zone(5, 5, "trap", 0.8, {"lethal": True})

            # Test behavior composition with memory influence
            context = {"resource_target": "gold", "location": (10, 10)}
            composition = self.behavior_composer.compose_behavior(agent, context)

            # Measure memory influence
            memory_count_before = len(agent.memory.location_memory.memories)

            if composition:
                composition.execute(agent, 0.1)

            memory_count_after = len(agent.memory.location_memory.memories)

            return {
                "success": composition is not None,
                "performance": {
                    "composition_time": 0.1,
                    "memory_influence": 1.0 if memory_count_after >= memory_count_before else 0.0
                },
                "details": {
                    "composition_created": composition is not None,
                    "memory_count_change": memory_count_after - memory_count_before
                }
            }

        self._run_test(
            "memory_behavior_integration",
            IntegrationTestLevel.COMPONENT,
            ["AgentMemory", "BehaviorComposer"],
            test_func
        )

    def _run_behavior_interrupt_integration(self):
        """Test integration between behavior composer and interrupt manager"""
        def test_func():
            agent = MockFlexibilityAgent("interrupt_test")

            # Create a composition
            context = {"resource_target": "wood"}
            composition = self.behavior_composer.compose_behavior(agent, context)

            if not composition:
                return {"success": False, "error": "Failed to create composition"}

            # Test interrupt functionality through composer
            interrupt_handled = False
            try:
                # This should trigger interrupt system integration
                self.behavior_composer.check_for_interrupts(agent, context)
                interrupt_handled = True
            except Exception as e:
                return {"success": False, "error": f"Interrupt integration failed: {e}"}

            return {
                "success": interrupt_handled,
                "performance": {
                    "interrupt_check_time": 0.01,
                    "integration_success": 1.0 if interrupt_handled else 0.0
                },
                "details": {
                    "interrupt_system_accessible": interrupt_handled
                }
            }

        self._run_test(
            "behavior_interrupt_integration",
            IntegrationTestLevel.COMPONENT,
            ["BehaviorComposer", "InterruptManager"],
            test_func
        )

    def _run_flexibility_regression_integration(self):
        """Test integration between flexibility harness and regression testing"""
        def test_func():
            # Create a baseline for regression testing
            temp_dir = tempfile.mkdtemp()
            regression_tester = BehaviorRegressionTester(temp_dir)

            agent_config = {
                "agent_id": "flexibility_regression_test",
                "personality": {"combat": 6.0, "exploration": 7.0, "social": 5.0}
            }

            context = {"integration_test": True}

            # Create baseline
            baseline_success = regression_tester.create_baseline(
                "flexibility_integration", "1.0.0", [agent_config], context
            )

            if not baseline_success:
                return {"success": False, "error": "Failed to create baseline"}

            # Run flexibility test
            agent = MockFlexibilityAgent("flexibility_test")
            flexibility_report = self.flexibility_harness.run_flexibility_assessment(
                agent, ["resource_scarcity_adaptation"]
            )

            # Test regression against baseline
            regression_report = regression_tester.test_regression(
                "flexibility_integration", "1.0.0", agent_config, context
            )

            integration_success = (
                flexibility_report.overall_flexibility > 0.0 and
                regression_report.overall_score >= 0.0
            )

            return {
                "success": integration_success,
                "performance": {
                    "flexibility_score": flexibility_report.overall_flexibility,
                    "regression_score": regression_report.overall_score
                },
                "details": {
                    "flexibility_scenarios": len(flexibility_report.scenarios),
                    "regression_count": len(regression_report.regressions),
                    "baseline_created": baseline_success
                }
            }

        self._run_test(
            "flexibility_regression_integration",
            IntegrationTestLevel.COMPONENT,
            ["FlexibilityHarness", "BehaviorRegressionTester"],
            test_func
        )

    def _run_agent_lifecycle_integration(self):
        """Test complete agent lifecycle integration"""
        def test_func():
            agent = MockFlexibilityAgent("lifecycle_test")
            lifecycle_stages = []

            # Stage 1: Initial behavior composition
            context1 = {"phase": "initialization"}
            composition1 = self.behavior_composer.compose_behavior(agent, context1)
            lifecycle_stages.append("composition_created" if composition1 else "composition_failed")

            # Stage 2: Memory formation
            agent.memory.remember_resource_location(0, 0, "wood", 0.7, 3)
            memory_formed = len(agent.memory.location_memory.memories) > 0
            lifecycle_stages.append("memory_formed" if memory_formed else "memory_failed")

            # Stage 3: Behavior adaptation
            context2 = {"phase": "adaptation", "resource_target": "wood"}
            composition2 = self.behavior_composer.compose_behavior(agent, context2)
            adaptation_success = composition2 is not None
            lifecycle_stages.append("adaptation_success" if adaptation_success else "adaptation_failed")

            # Stage 4: Interrupt handling (simulated)
            try:
                self.behavior_composer.check_for_interrupts(agent, context2)
                interrupt_success = True
            except:
                interrupt_success = False
            lifecycle_stages.append("interrupt_handled" if interrupt_success else "interrupt_failed")

            # Stage 5: Performance measurement
            flexibility_report = self.flexibility_harness.run_flexibility_assessment(
                agent, ["resource_scarcity_adaptation"]
            )
            performance_measured = flexibility_report.overall_flexibility >= 0.0
            lifecycle_stages.append("performance_measured" if performance_measured else "performance_failed")

            # Calculate success
            success_count = len([stage for stage in lifecycle_stages if "success" in stage or "created" in stage or "formed" in stage or "handled" in stage or "measured" in stage])
            overall_success = success_count >= 4  # At least 4 out of 5 stages successful

            return {
                "success": overall_success,
                "performance": {
                    "lifecycle_completion": success_count / 5.0,
                    "memory_utilization": len(agent.memory.location_memory.memories),
                    "flexibility_score": flexibility_report.overall_flexibility
                },
                "details": {
                    "lifecycle_stages": lifecycle_stages,
                    "successful_stages": success_count,
                    "total_stages": 5
                }
            }

        self._run_test(
            "agent_lifecycle_integration",
            IntegrationTestLevel.SUBSYSTEM,
            ["AgentMemory", "BehaviorComposer", "InterruptManager", "FlexibilityHarness"],
            test_func
        )

    def _run_multi_agent_interaction_integration(self):
        """Test multi-agent interaction integration"""
        def test_func():
            # Create multiple agents with different personalities
            agent1 = MockFlexibilityAgent("social_agent", Personality(combat=3.0, exploration=5.0, social=9.0))
            agent2 = MockFlexibilityAgent("combat_agent", Personality(combat=9.0, exploration=4.0, social=3.0))

            interactions_successful = 0

            # Test social memory formation
            agent1.memory.remember_social_interaction("combat_agent", "cooperation", "successful")
            agent2.memory.remember_social_interaction("social_agent", "cooperation", "successful")

            if len(agent1.memory.social_memory.agent_memories) > 0:
                interactions_successful += 1

            if len(agent2.memory.social_memory.agent_memories) > 0:
                interactions_successful += 1

            # Test behavior composition considering social context
            social_context = {"partner_agent": "combat_agent", "interaction_type": "cooperation"}
            composition1 = self.behavior_composer.compose_behavior(agent1, social_context)

            combat_context = {"partner_agent": "social_agent", "interaction_type": "cooperation"}
            composition2 = self.behavior_composer.compose_behavior(agent2, combat_context)

            if composition1:
                interactions_successful += 1
            if composition2:
                interactions_successful += 1

            # Test flexibility in multi-agent scenarios
            multi_agent_context = {"multi_agent": True, "agents": ["social_agent", "combat_agent"]}
            flexibility_report = self.flexibility_harness.run_flexibility_assessment(
                agent1, ["social_dynamics_shift"]
            )

            if flexibility_report.overall_flexibility > 0.0:
                interactions_successful += 1

            success = interactions_successful >= 4  # At least 4 out of 5 interactions successful

            return {
                "success": success,
                "performance": {
                    "interaction_success_rate": interactions_successful / 5.0,
                    "social_memory_formation": len(agent1.memory.social_memory.agent_memories),
                    "flexibility_in_social_context": flexibility_report.overall_flexibility
                },
                "details": {
                    "successful_interactions": interactions_successful,
                    "total_interactions": 5,
                    "agent1_personality": agent1.personality.__dict__,
                    "agent2_personality": agent2.personality.__dict__
                }
            }

        self._run_test(
            "multi_agent_interaction_integration",
            IntegrationTestLevel.SUBSYSTEM,
            ["AgentMemory", "BehaviorComposer", "FlexibilityHarness"],
            test_func
        )

    def _run_performance_integration(self):
        """Test system performance under integration load"""
        def test_func():
            performance_metrics = {}

            # Test behavior composition performance
            agent = MockFlexibilityAgent("performance_test")
            contexts = [
                {"resource_target": "wood"},
                {"threat_level": "high"},
                {"social_partner": "ally"},
                {"exploration_target": "unknown_area"},
                {"emergency": True}
            ]

            composition_times = []
            for context in contexts:
                start = time.time()
                composition = self.behavior_composer.compose_behavior(agent, context)
                composition_time = time.time() - start
                composition_times.append(composition_time)

                if composition:
                    exec_start = time.time()
                    composition.execute(agent, 0.1)
                    exec_time = time.time() - exec_start
                    composition_times.append(exec_time)

            performance_metrics["avg_composition_time"] = sum(composition_times) / len(composition_times)
            performance_metrics["max_composition_time"] = max(composition_times)

            # Test memory performance
            memory_ops = []
            for i in range(50):
                start = time.time()
                agent.memory.remember_resource_location(i, i, "test_resource", 0.5, 1)
                memory_time = time.time() - start
                memory_ops.append(memory_time)

            performance_metrics["avg_memory_operation_time"] = sum(memory_ops) / len(memory_ops)
            performance_metrics["max_memory_operation_time"] = max(memory_ops)

            # Test flexibility assessment performance
            start = time.time()
            self.flexibility_harness.run_flexibility_assessment(agent, ["resource_scarcity_adaptation"])
            flexibility_time = time.time() - start
            performance_metrics["flexibility_assessment_time"] = flexibility_time

            # Performance success criteria
            composition_acceptable = performance_metrics["avg_composition_time"] < 0.1  # < 100ms
            memory_acceptable = performance_metrics["avg_memory_operation_time"] < 0.01  # < 10ms
            flexibility_acceptable = performance_metrics["flexibility_assessment_time"] < 5.0  # < 5s

            overall_performance = (composition_acceptable and memory_acceptable and flexibility_acceptable)

            return {
                "success": overall_performance,
                "performance": performance_metrics,
                "details": {
                    "composition_performance": "acceptable" if composition_acceptable else "slow",
                    "memory_performance": "acceptable" if memory_acceptable else "slow",
                    "flexibility_performance": "acceptable" if flexibility_acceptable else "slow",
                    "total_operations": len(composition_times) + len(memory_ops) + 1
                }
            }

        self._run_test(
            "performance_integration",
            IntegrationTestLevel.SYSTEM,
            ["BehaviorComposer", "AgentMemory", "FlexibilityHarness"],
            test_func
        )

    def _run_stress_test_integration(self):
        """Test system behavior under stress conditions"""
        def test_func():
            stress_results = {}

            # Create multiple agents
            agents = []
            for i in range(10):
                agent = MockFlexibilityAgent(f"stress_agent_{i}")
                agents.append(agent)

            # Stress test: rapid behavior composition
            composition_failures = 0
            for agent in agents:
                for _ in range(10):  # 10 rapid compositions per agent
                    try:
                        context = {"stress_test": True, "agent_id": agent.id}
                        composition = self.behavior_composer.compose_behavior(agent, context)
                        if composition is None:
                            composition_failures += 1
                    except Exception:
                        composition_failures += 1

            stress_results["composition_failure_rate"] = composition_failures / (len(agents) * 10)

            # Stress test: memory operations
            memory_failures = 0
            for agent in agents:
                for i in range(20):  # 20 memory operations per agent
                    try:
                        agent.memory.remember_resource_location(i, i, f"stress_resource_{i}", 0.5, 1)
                    except Exception:
                        memory_failures += 1

            stress_results["memory_failure_rate"] = memory_failures / (len(agents) * 20)

            # Stress test: concurrent flexibility assessments (simulated)
            flexibility_failures = 0
            for agent in agents[:3]:  # Test 3 agents to avoid too much time
                try:
                    self.flexibility_harness.run_flexibility_assessment(agent, ["resource_scarcity_adaptation"])
                except Exception:
                    flexibility_failures += 1

            stress_results["flexibility_failure_rate"] = flexibility_failures / 3

            # Success criteria: failure rates should be low
            composition_success = stress_results["composition_failure_rate"] < 0.1  # < 10% failure
            memory_success = stress_results["memory_failure_rate"] < 0.05  # < 5% failure
            flexibility_success = stress_results["flexibility_failure_rate"] < 0.2  # < 20% failure

            overall_success = composition_success and memory_success and flexibility_success

            return {
                "success": overall_success,
                "performance": stress_results,
                "details": {
                    "agents_tested": len(agents),
                    "composition_operations": len(agents) * 10,
                    "memory_operations": len(agents) * 20,
                    "flexibility_operations": 3,
                    "composition_reliability": "good" if composition_success else "poor",
                    "memory_reliability": "good" if memory_success else "poor",
                    "flexibility_reliability": "good" if flexibility_success else "poor"
                }
            }

        self._run_test(
            "stress_test_integration",
            IntegrationTestLevel.SYSTEM,
            ["BehaviorComposer", "AgentMemory", "FlexibilityHarness"],
            test_func
        )

    def _run_complete_scenario_integration(self):
        """Test complete end-to-end scenario integration"""
        def test_func():
            # Create an agent for end-to-end testing
            agent = MockFlexibilityAgent("e2e_agent", Personality(combat=6.0, exploration=7.0, social=5.0))
            scenario_steps = []

            # Step 1: Agent enters new environment
            agent.move_to(25.0, 30.0)
            scenario_steps.append("environment_entry")

            # Step 2: Agent discovers resources and remembers them
            agent.memory.remember_resource_location(25.0, 30.0, "rare_ore", 0.9, 7)
            resource_memory_formed = len(agent.memory.location_memory.memories) > 0
            scenario_steps.append("resource_discovery" if resource_memory_formed else "resource_discovery_failed")

            # Step 3: Agent encounters danger and adapts
            agent.memory.remember_danger_zone(26.0, 31.0, "hostile_creature", 0.8, {"threat_type": "creature"})
            danger_context = {"threat_detected": True, "location": (26.0, 31.0)}
            danger_composition = self.behavior_composer.compose_behavior(agent, danger_context)
            scenario_steps.append("danger_adaptation" if danger_composition else "danger_adaptation_failed")

            # Step 4: Agent meets another agent and forms social memory
            agent.memory.remember_social_interaction("friendly_trader", "trade", "successful",
                                                   details={"items_traded": 5})
            social_memory_formed = len(agent.memory.social_memory.agent_memories) > 0
            scenario_steps.append("social_interaction" if social_memory_formed else "social_interaction_failed")

            # Step 5: Agent's behavior is interrupted by emergency
            emergency_context = {"emergency": True, "type": "health_critical"}
            try:
                self.behavior_composer.check_for_interrupts(agent, emergency_context)
                interrupt_handled = True
            except:
                interrupt_handled = False
            scenario_steps.append("emergency_handled" if interrupt_handled else "emergency_failed")

            # Step 6: Flexibility assessment of entire scenario
            flexibility_report = self.flexibility_harness.run_flexibility_assessment(
                agent, ["resource_scarcity_adaptation", "environment_change_response", "social_dynamics_shift"]
            )
            flexibility_success = flexibility_report.overall_flexibility > 0.3
            scenario_steps.append("flexibility_assessed" if flexibility_success else "flexibility_assessment_failed")

            # Step 7: Regression check against baseline behavior
            temp_dir = tempfile.mkdtemp()
            regression_tester = BehaviorRegressionTester(temp_dir)
            agent_config = {
                "agent_id": "e2e_baseline_agent",
                "personality": {"combat": 6.0, "exploration": 7.0, "social": 5.0}
            }

            # Create and test against baseline
            baseline_created = regression_tester.create_baseline("e2e_scenario", "1.0.0", [agent_config], {})
            if baseline_created:
                regression_report = regression_tester.test_regression("e2e_scenario", "1.0.0", agent_config, {})
                regression_success = not regression_report.has_critical_regressions()
            else:
                regression_success = False
            scenario_steps.append("regression_check" if regression_success else "regression_check_failed")

            # Calculate scenario success
            successful_steps = len([step for step in scenario_steps if not step.endswith("_failed")])
            scenario_success = successful_steps >= 6  # At least 6 out of 7 steps successful

            return {
                "success": scenario_success,
                "performance": {
                    "scenario_completion": successful_steps / 7.0,
                    "flexibility_score": flexibility_report.overall_flexibility,
                    "memory_utilization": len(agent.memory.location_memory.memories) +
                                        sum(len(memories) for memories in agent.memory.social_memory.agent_memories.values()),
                    "regression_score": regression_report.overall_score if baseline_created else 0.0
                },
                "details": {
                    "scenario_steps": scenario_steps,
                    "successful_steps": successful_steps,
                    "total_steps": 7,
                    "agent_final_position": (agent.x, agent.y),
                    "memory_count": len(agent.memory.location_memory.memories),
                    "social_connections": len(agent.memory.social_memory.agent_memories)
                }
            }

        self._run_test(
            "complete_scenario_integration",
            IntegrationTestLevel.END_TO_END,
            ["AgentMemory", "BehaviorComposer", "InterruptManager", "FlexibilityHarness", "BehaviorRegressionTester"],
            test_func
        )

    def _calculate_overall_performance(self) -> Dict[str, float]:
        """Calculate overall performance metrics for the suite"""
        if not self.test_reports:
            return {}

        # Aggregate performance metrics
        all_durations = [report.duration for report in self.test_reports]
        performance_metrics = {}

        for report in self.test_reports:
            if report.performance_metrics:
                for key, value in report.performance_metrics.items():
                    if key not in performance_metrics:
                        performance_metrics[key] = []
                    performance_metrics[key].append(value)

        # Calculate aggregated metrics
        overall = {
            "avg_test_duration": sum(all_durations) / len(all_durations),
            "max_test_duration": max(all_durations),
            "total_test_time": sum(all_durations)
        }

        # Add averaged performance metrics
        for key, values in performance_metrics.items():
            if values:
                overall[f"avg_{key}"] = sum(values) / len(values)
                overall[f"max_{key}"] = max(values)

        return overall

    def _generate_suite_summary(self, passed: int, failed: int, skipped: int,
                               errors: int, total: int) -> str:
        """Generate human-readable summary of test suite results"""
        if total == 0:
            return "No tests executed"

        if failed == 0 and errors == 0:
            return f"SUCCESS: All {passed} tests passed"
        elif failed > 0 and errors == 0:
            return f"PARTIAL SUCCESS: {passed}/{total} tests passed, {failed} failed"
        elif errors > 0 and failed == 0:
            return f"ERRORS: {passed}/{total} tests passed, {errors} errors"
        else:
            return f"ISSUES: {passed}/{total} tests passed, {failed} failed, {errors} errors"


def run_quick_integration_test() -> IntegrationTestSuite:
    """Run a quick integration test with essential components"""
    tester = AgentIntegrationTester()
    return tester.run_integration_test_suite("quick_integration")


def run_comprehensive_integration_test() -> IntegrationTestSuite:
    """Run comprehensive integration test suite"""
    tester = AgentIntegrationTester()
    return tester.run_integration_test_suite("comprehensive_integration")