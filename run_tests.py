#!/usr/bin/env python3
"""
MMO Simulator Test Runner

This script provides convenient ways to run different types of tests
with appropriate configurations.
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report results"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)

    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"\n❌ {description} failed with exit code {result.returncode}")
        return False
    else:
        print(f"\n✅ {description} passed!")
        return True


def main():
    """Main test runner"""
    if len(sys.argv) < 2:
        print("Usage: python run_tests.py <test_type>")
        print("\nAvailable test types:")
        print("  unit         - Fast unit tests only")
        print("  integration  - Integration tests")
        print("  behavior     - Behavior tests")
        print("  performance  - Performance tests (slow)")
        print("  all          - All tests except performance")
        print("  everything   - All tests including performance")
        print("  quick        - Quick smoke test of key functionality")
        sys.exit(1)

    test_type = sys.argv[1].lower()
    base_cmd = ["python", "-m", "pytest"]

    if test_type == "unit":
        cmd = base_cmd + ["tests/unit/", "-v", "--tb=short", "-x"]
        success = run_command(cmd, "Unit Tests")

    elif test_type == "integration":
        cmd = base_cmd + ["tests/integration/", "-v", "--tb=short"]
        success = run_command(cmd, "Integration Tests")

    elif test_type == "behavior":
        cmd = base_cmd + ["tests/behavior/", "-v", "--tb=short"]
        success = run_command(cmd, "Behavior Tests")

    elif test_type == "performance":
        cmd = base_cmd + ["tests/performance/", "-v", "--tb=short", "--run-performance"]
        success = run_command(cmd, "Performance Tests")

    elif test_type == "all":
        print("Running all non-performance tests...")
        success = True

        # Unit tests
        cmd = base_cmd + ["tests/unit/", "-v", "--tb=short", "-x"]
        success &= run_command(cmd, "Unit Tests")

        if success:
            # Integration tests
            cmd = base_cmd + ["tests/integration/", "-v", "--tb=short"]
            success &= run_command(cmd, "Integration Tests")

        if success:
            # Behavior tests
            cmd = base_cmd + ["tests/behavior/", "-v", "--tb=short"]
            success &= run_command(cmd, "Behavior Tests")

    elif test_type == "everything":
        print("Running ALL tests including performance...")
        success = True

        # Run all test types
        for test_dir in ["unit", "integration", "behavior", "performance"]:
            cmd = base_cmd + [f"tests/{test_dir}/", "-v", "--tb=short"]
            if test_dir == "performance":
                cmd.append("--run-performance")
            success &= run_command(cmd, f"{test_dir.title()} Tests")
            if not success:
                break

    elif test_type == "quick":
        print("Running quick smoke tests...")
        cmd = base_cmd + [
            "tests/unit/test_action_validators.py::TestRateLimitValidator::test_allows_normal_rate",
            "tests/unit/test_world_physics.py::TestCollisionDetector::test_basic_bounds_checking",
            "tests/integration/test_action_system.py::TestActionRequestFlow::test_move_action_complete_flow",
            "-v", "--tb=short"
        ]
        success = run_command(cmd, "Quick Smoke Tests")

    else:
        print(f"Unknown test type: {test_type}")
        sys.exit(1)

    if success:
        print(f"\n🎉 All {test_type} tests passed!")
        sys.exit(0)
    else:
        print(f"\n💥 Some {test_type} tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()