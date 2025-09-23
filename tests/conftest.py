import asyncio
import logging
from typing import Any, Dict, List

import pytest
import pytest_asyncio

from client.client import GameClient
from scenarios.scenario_manager import ScenarioManager
from server.server import GameServer
from tests.utils.agent_tracker import AgentTracker
from tests.utils.metrics import BehaviorMetrics

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest_asyncio.fixture
async def game_server():
    """Create a test game server"""
    server = GameServer(50, 50)  # Smaller world for faster tests

    # Start server in background
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)  # Let server initialize

    yield server

    # Cleanup
    server.stop()
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


@pytest_asyncio.fixture
async def game_client(game_server):
    """Create a test game client"""
    client = GameClient()
    connected = await client.connect("127.0.0.1", "player")

    if not connected:
        pytest.fail("Failed to connect test client")

    yield client

    # Cleanup
    if client.connected:
        await client.disconnect()


@pytest_asyncio.fixture
async def agent_clients(game_server):
    """Create multiple agent clients for testing"""
    clients = []

    async def create_agent_client(agent_type: str) -> GameClient:
        client = GameClient()
        connected = await client.connect("127.0.0.1", agent_type)
        if connected:
            clients.append(client)
            # Start the client update loop
            update_task = asyncio.create_task(client.run_update_loop())
            client._update_task = update_task  # Store for cleanup
            return client
        return None

    yield create_agent_client

    # Cleanup all clients
    for client in clients:
        # Cancel update task if exists
        if hasattr(client, "_update_task"):
            client._update_task.cancel()
            try:
                await client._update_task
            except asyncio.CancelledError:
                pass

        if client.connected:
            await client.disconnect()


@pytest.fixture
def scenario_manager():
    """Create scenario manager for tests"""
    return ScenarioManager()


@pytest_asyncio.fixture
async def agent_tracker(game_server):
    """Create agent tracker for monitoring agent behavior"""
    tracker = AgentTracker(game_server)
    await tracker.start()

    yield tracker

    await tracker.stop()


@pytest.fixture
def behavior_metrics():
    """Create behavior metrics collector"""
    return BehaviorMetrics()


@pytest_asyncio.fixture
async def test_scenario(game_server, scenario_manager):
    """Load a test scenario"""

    async def load_scenario(scenario_name: str):
        scenario = await scenario_manager.load_scenario(scenario_name, game_server)
        if not scenario:
            pytest.fail(f"Failed to load scenario: {scenario_name}")
        return scenario

    yield load_scenario


@pytest.fixture
def assert_agent_behavior():
    """Custom assertions for agent behavior"""

    def _assert_agent_moved(
        start_pos: tuple, end_pos: tuple, min_distance: float = 1.0
    ):
        """Assert agent moved at least minimum distance"""
        distance = (
            (end_pos[0] - start_pos[0]) ** 2 + (end_pos[1] - start_pos[1]) ** 2
        ) ** 0.5
        assert (
            distance >= min_distance
        ), f"Agent moved only {distance:.2f}, expected >= {min_distance}"

    def _assert_agent_in_radius(agent_pos: tuple, center: tuple, radius: float):
        """Assert agent is within specified radius of center"""
        distance = (
            (agent_pos[0] - center[0]) ** 2 + (agent_pos[1] - center[1]) ** 2
        ) ** 0.5
        assert (
            distance <= radius
        ), f"Agent at {agent_pos} is {distance:.2f} from center {center}, expected <= {radius}"

    def _assert_agent_state(agent_data: dict, expected_state: str):
        """Assert agent is in expected state"""
        actual_state = agent_data.get("state", "unknown")
        assert (
            actual_state == expected_state
        ), f"Agent state is {actual_state}, expected {expected_state}"

    class AssertAgent:
        moved = _assert_agent_moved
        in_radius = _assert_agent_in_radius
        state = _assert_agent_state

    return AssertAgent()


@pytest_asyncio.fixture(autouse=True)
async def test_timeout():
    """Ensure tests don't hang indefinitely"""
    # This fixture runs automatically for all tests
    yield
    # Cleanup happens automatically via pytest-timeout
