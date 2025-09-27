"""
Modern pytest configuration with fast, reliable fixtures

This replaces the old conftest.py with more focused, lightweight fixtures
that don't require full server startup for most tests.
"""

import asyncio
import logging
from typing import Any, Dict

import pytest

from tests.fixtures.mock_server import FastTestFixture, MockGameServer, MockWorld
from tests.fixtures.test_maps import TestMapBuilder, TestMaps

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def mock_world():
    """Fast mock world for unit tests"""
    return MockWorld(20, 20)


@pytest.fixture
def mock_server():
    """Fast mock server for unit tests"""
    return MockGameServer(20, 20)


@pytest.fixture
async def fast_test_env():
    """Fast test environment with mock components"""
    fixture = FastTestFixture()
    yield fixture
    # No cleanup needed for mocks


@pytest.fixture(
    params=[
        ("empty_arena", TestMaps.get_empty_arena),
        ("combat_arena", TestMaps.get_combat_arena),
        ("fishing_pond", TestMaps.get_fishing_pond),
    ]
)
def test_terrain(request):
    """Parameterized terrain fixtures"""
    terrain_name, terrain_func = request.param
    return terrain_name, terrain_func()


@pytest.fixture
def terrain_builder():
    """Terrain builder for custom test maps"""
    return TestMapBuilder


@pytest.fixture(scope="session")
def event_loop():
    """Session-wide event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Custom markers for test organization
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with custom settings"""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated components)")
    config.addinivalue_line(
        "markers", "integration: Integration tests (component interactions)"
    )
    config.addinivalue_line(
        "markers", "behavior: Behavior tests (agent AI and decision making)"
    )
    config.addinivalue_line("markers", "performance: Performance and load tests")


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location"""
    for item in items:
        # Mark tests based on directory structure
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "behavior" in str(item.fspath):
            item.add_marker(pytest.mark.behavior)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
            item.add_marker(pytest.mark.slow)


class TestHelpers:
    """Helper functions for tests"""

    @staticmethod
    def assert_agent_moved(start_pos: tuple, end_pos: tuple, min_distance: float = 1.0):
        """Assert agent moved minimum distance"""
        distance = (
            (end_pos[0] - start_pos[0]) ** 2 + (end_pos[1] - start_pos[1]) ** 2
        ) ** 0.5
        assert (
            distance >= min_distance
        ), f"Agent moved only {distance:.2f}, expected >= {min_distance}"

    @staticmethod
    def assert_position_in_bounds(pos: tuple, width: int, height: int):
        """Assert position is within world bounds"""
        x, y = pos
        assert (
            0 <= x < width and 0 <= y < height
        ), f"Position {pos} out of bounds ({width}x{height})"

    @staticmethod
    def assert_response_time(response_time: float, max_time: float = 0.1):
        """Assert response time is acceptable"""
        assert (
            response_time <= max_time
        ), f"Response time {response_time:.3f}s exceeds limit {max_time:.3f}s"


@pytest.fixture
def test_helpers():
    """Test helper functions"""
    return TestHelpers


# Timeout configuration for different test types
def pytest_timeout_set_timer(item, timeout):
    """Set custom timeouts based on test type"""
    if item.get_closest_marker("performance"):
        return 60  # Performance tests get more time
    elif item.get_closest_marker("integration"):
        return 30  # Integration tests
    elif item.get_closest_marker("unit"):
        return 10  # Unit tests should be fast
    return timeout  # Default


@pytest.fixture(autouse=True)
def setup_test_logging(caplog):
    """Set up logging for each test"""
    caplog.set_level(logging.INFO)


# Skip slow tests by default in development
def pytest_addoption(parser):
    """Add command line options"""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run slow tests (performance, network simulation)",
    )
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="Run performance tests",
    )


def pytest_runtest_setup(item):
    """Skip certain tests based on command line options"""
    if item.get_closest_marker("slow") and not item.config.getoption("--run-slow"):
        pytest.skip("need --run-slow option to run")

    if item.get_closest_marker("performance") and not item.config.getoption(
        "--run-performance"
    ):
        pytest.skip("need --run-performance option to run")
