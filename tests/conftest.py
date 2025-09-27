"""
New Test Configuration and Fixtures

Provides pytest fixtures and configuration for the improved test framework.
Follows the test pyramid pattern with proper separation of concerns.
"""

import pytest
import asyncio
import logging
from typing import Dict, Any

from tests.framework.world_builder import WorldBuilder, PredefinedWorlds
from tests.framework.agent_harness import AgentTestHarness
from tests.framework.test_server import TestGameServer, TestServerConfig, IntegrationTestContext


# Configure test logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise during tests


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Unit Test Fixtures (Fast, Isolated)

@pytest.fixture
def empty_world_builder():
    """Create empty world builder for unit tests"""
    return WorldBuilder(10, 10).with_seed(12345)


@pytest.fixture
def maze_world_builder():
    """Create maze world for pathfinding unit tests"""
    return PredefinedWorlds.simple_maze(15)


@pytest.fixture
def water_world_builder():
    """Create world with water obstacles for navigation unit tests"""
    return PredefinedWorlds.water_navigation_test()


@pytest.fixture
def agent_harness(empty_world_builder):
    """Create agent test harness with empty world"""
    world = empty_world_builder.build()
    return AgentTestHarness(world)


# Integration Test Fixtures (Medium Speed, Real Components)

@pytest.fixture
async def test_server():
    """Create lightweight test server for integration tests"""
    config = TestServerConfig(
        world_width=15,
        world_height=15,
        time_acceleration=10.0,  # Speed up tests
        log_level="ERROR"  # Minimal logging
    )
    server = TestGameServer(config)
    await server.start()

    yield server

    await server.stop()


@pytest.fixture
async def integration_context():
    """Create integration test context with automatic cleanup"""
    config = TestServerConfig(
        world_width=20,
        world_height=20,
        time_acceleration=5.0,
        log_level="ERROR"
    )

    async with IntegrationTestContext(config) as ctx:
        yield ctx


# Scenario Test Fixtures (Slower, Complex Environments)

@pytest.fixture
async def complex_scenario_context():
    """Create complex scenario for end-to-end tests"""
    config = TestServerConfig(
        world_width=30,
        world_height=30,
        time_acceleration=2.0,  # Slower for complex scenarios
        log_level="WARNING"
    )

    world_builder = PredefinedWorlds.multi_room_dungeon()

    async with IntegrationTestContext(config, world_builder) as ctx:
        yield ctx


@pytest.fixture
async def resource_scenario_context():
    """Create resource gathering scenario"""
    config = TestServerConfig(
        world_width=25,
        world_height=25,
        time_acceleration=3.0
    )

    world_builder = PredefinedWorlds.resource_gathering_area()

    async with IntegrationTestContext(config, world_builder) as ctx:
        yield ctx


# Parameterized Test Fixtures

@pytest.fixture(params=["explorer", "player", "enemy"])
def agent_type(request):
    """Parameterized agent type for testing all agent types"""
    return request.param


@pytest.fixture(params=[
    {"width": 10, "height": 10},
    {"width": 20, "height": 15},
    {"width": 5, "height": 25}
])
def world_dimensions(request):
    """Parameterized world dimensions for testing different sizes"""
    return request.param


@pytest.fixture(params=[1, 2, 5])
def agent_count(request):
    """Parameterized agent count for multi-agent tests"""
    return request.param


# Performance Test Fixtures

@pytest.fixture
def performance_config():
    """Configuration for performance tests"""
    return TestServerConfig(
        world_width=50,
        world_height=50,
        time_acceleration=1.0,  # Real-time for performance measurement
        log_level="ERROR",
        max_agents=100
    )


# Test Utilities

@pytest.fixture
def test_data():
    """Common test data for various scenarios"""
    return {
        "spawn_positions": [
            (5, 5), (10, 10), (15, 15), (20, 20)
        ],
        "target_positions": [
            (25, 25), (30, 30), (35, 35), (40, 40)
        ],
        "movement_speeds": [0.5, 1.0, 1.5, 2.0],
        "timeouts": {
            "unit": 5.0,
            "integration": 15.0,
            "scenario": 60.0
        }
    }


# Cleanup and Utilities

@pytest.fixture(autouse=True)
def cleanup_logs():
    """Automatically clean up log handlers after each test"""
    yield
    # Remove any test-specific log handlers
    for logger_name in ["server", "client", "tests"]:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)


# Marks for Test Organization

pytest_markers = [
    "unit: Fast unit tests (<1s each)",
    "integration: Integration tests with real components (<10s each)",
    "scenario: Complex end-to-end scenario tests (<60s each)",
    "performance: Performance and load tests",
    "slow: Tests that take longer than 30 seconds",
    "network: Tests requiring network components",
    "agent: Agent behavior tests",
    "pathfinding: Pathfinding and navigation tests",
    "collision: Collision detection tests",
    "action_system: Action request/response system tests"
]


def pytest_configure(config):
    """Configure pytest with custom markers"""
    for marker in pytest_markers:
        config.addinivalue_line("markers", marker)


def pytest_collection_modifyitems(config, items):
    """Automatically apply test markers based on file location"""
    for item in items:
        # Apply markers based on test file location
        if "unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "scenarios/" in str(item.fspath):
            item.add_marker(pytest.mark.scenario)
        elif "performance/" in str(item.fspath):
            item.add_marker(pytest.mark.performance)

        # Apply markers based on test name patterns
        if "pathfind" in item.name.lower():
            item.add_marker(pytest.mark.pathfinding)
        elif "collision" in item.name.lower():
            item.add_marker(pytest.mark.collision)
        elif "action" in item.name.lower():
            item.add_marker(pytest.mark.action_system)
        elif "agent" in item.name.lower():
            item.add_marker(pytest.mark.agent)


# Test Selection Helpers

def pytest_addoption(parser):
    """Add custom command line options"""
    parser.addoption(
        "--fast-only",
        action="store_true",
        default=False,
        help="Run only fast tests (unit tests)"
    )
    parser.addoption(
        "--integration-only",
        action="store_true",
        default=False,
        help="Run only integration tests"
    )
    parser.addoption(
        "--scenarios-only",
        action="store_true",
        default=False,
        help="Run only scenario tests"
    )


def pytest_runtest_setup(item):
    """Setup hook to filter tests based on command line options"""
    if item.config.getoption("--fast-only"):
        if not item.get_closest_marker("unit"):
            pytest.skip("Skipping non-unit test in fast-only mode")

    if item.config.getoption("--integration-only"):
        if not item.get_closest_marker("integration"):
            pytest.skip("Skipping non-integration test in integration-only mode")

    if item.config.getoption("--scenarios-only"):
        if not item.get_closest_marker("scenario"):
            pytest.skip("Skipping non-scenario test in scenarios-only mode")