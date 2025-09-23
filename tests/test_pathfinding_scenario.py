import asyncio
import logging
import time

import pytest

from client.client import GameClient
from scenarios.scenario_manager import ScenarioManager
from server.server import GameServer

# Disable logging during tests to reduce noise
logging.disable(logging.CRITICAL)


@pytest.mark.asyncio
async def test_pathfinding_scenario_movement():
    """Test that agent moves through predefined waypoints in pathfinding test scenario"""

    # Create server and scenario
    server = GameServer(100, 100)
    scenario_manager = ScenarioManager()

    # Start server
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)  # Let server start

    try:
        # Load pathfinding test scenario
        scenario = await scenario_manager.load_scenario("pathfinding_test", server)
        assert scenario is not None, "Failed to load pathfinding_test scenario"

        # Wait for agents to spawn
        await asyncio.sleep(0.5)

        # Get the spawned agent
        agents = server.world.get_all_agents()
        assert len(agents) == 1, f"Expected 1 agent, got {len(agents)}"

        test_agent = agents[0]
        assert (
            test_agent.agent_type == "pathfinding_test"
        ), f"Expected pathfinding_test agent, got {test_agent.agent_type}"

        # Connect client for the test agent
        client = GameClient()
        connected = await client.connect(agent_type="pathfinding_test")
        assert connected, "Failed to connect test client"

        # Wait for agent to be created
        await asyncio.sleep(0.5)
        assert client.agent is not None, "Client agent not created"

        # Get initial position
        initial_position = (client.agent.x, client.agent.y)
        expected_start = (10, 10)

        # Verify agent starts reasonably close to expected position (within tolerance for collision detection)
        assert (
            abs(initial_position[0] - expected_start[0]) < 10.0
        ), f"Agent x position {initial_position[0]} not near expected {expected_start[0]}"
        assert (
            abs(initial_position[1] - expected_start[1]) < 10.0
        ), f"Agent y position {initial_position[1]} not near expected {expected_start[1]}"

        # Run test for a reasonable duration to allow movement
        test_duration = 30.0  # 30 seconds should be enough for basic movement
        start_time = time.time()

        while time.time() - start_time < test_duration:
            await client.update()
            await asyncio.sleep(0.033)  # ~30 FPS

            # Check if agent has completed the test
            if (
                hasattr(client.agent, "movement_state")
                and client.agent.movement_state == "completed"
            ):
                break

        # Get test results
        assert hasattr(
            client.agent, "get_test_results"
        ), "Agent doesn't have get_test_results method"
        results = client.agent.get_test_results()

        # Validate results
        assert "visited_waypoints" in results, "Missing visited_waypoints in results"
        assert "movement_history" in results, "Missing movement_history in results"
        assert "completed" in results, "Missing completed status in results"

        visited_waypoints = results["visited_waypoints"]
        movement_history = results["movement_history"]

        # Verify agent moved (has movement history)
        assert len(movement_history) > 0, "Agent has no movement history"

        # Verify agent visited at least the first waypoint beyond start
        assert (
            len(visited_waypoints) >= 1
        ), f"Agent visited {len(visited_waypoints)} waypoints, expected at least 1"

        # Verify movement occurred (position changed from start)
        final_position = results["current_position"]
        distance_moved = (
            (final_position[0] - initial_position[0]) ** 2
            + (final_position[1] - initial_position[1]) ** 2
        ) ** 0.5
        assert (
            distance_moved > 5.0
        ), f"Agent only moved {distance_moved:.2f} units, expected significant movement"

        # Log test results for debugging
        print(f"\nPathfinding Test Results:")
        print(f"  Initial position: {initial_position}")
        print(f"  Final position: {final_position}")
        print(f"  Distance moved: {distance_moved:.2f}")
        print(f"  Waypoints visited: {len(visited_waypoints)}")
        print(f"  Movement history entries: {len(movement_history)}")
        print(f"  Test completed: {results['completed']}")

        if visited_waypoints:
            print(
                f"  First waypoint reached: {visited_waypoints[0]['waypoint']} at time {visited_waypoints[0]['time_reached']:.2f}s"
            )

        await client.disconnect()

    finally:
        # Cleanup
        server.stop()
        try:
            await asyncio.wait_for(server_task, timeout=2.0)
        except asyncio.TimeoutError:
            server_task.cancel()


@pytest.mark.asyncio
async def test_pathfinding_scenario_waypoint_accuracy():
    """Test that agent reaches waypoints with reasonable accuracy"""

    server = GameServer(100, 100)
    scenario_manager = ScenarioManager()

    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(0.5)

    try:
        scenario = await scenario_manager.load_scenario("pathfinding_test", server)
        await asyncio.sleep(0.5)

        client = GameClient()
        connected = await client.connect(agent_type="pathfinding_test")
        assert connected, "Failed to connect test client"
        await asyncio.sleep(0.5)

        # Run for shorter duration to check first waypoint accuracy
        test_duration = 15.0
        start_time = time.time()

        while time.time() - start_time < test_duration:
            await client.update()
            await asyncio.sleep(0.033)

            # Check if agent reached first waypoint
            if (
                hasattr(client.agent, "visited_waypoints")
                and len(client.agent.visited_waypoints) > 0
            ):
                break

        results = client.agent.get_test_results()
        visited_waypoints = results["visited_waypoints"]

        if len(visited_waypoints) > 0:
            first_visit = visited_waypoints[0]
            target_waypoint = first_visit["waypoint"]
            actual_position = first_visit["actual_position"]

            # Verify accuracy (agent should reach within 2 units of target)
            distance_error = (
                (actual_position[0] - target_waypoint[0]) ** 2
                + (actual_position[1] - target_waypoint[1]) ** 2
            ) ** 0.5

            assert (
                distance_error <= 2.0
            ), f"Agent reached waypoint with error of {distance_error:.2f}, expected <= 2.0"

            print(f"\nWaypoint Accuracy Test:")
            print(f"  Target: {target_waypoint}")
            print(f"  Actual: {actual_position}")
            print(f"  Error: {distance_error:.2f}")

        await client.disconnect()

    finally:
        server.stop()
        try:
            await asyncio.wait_for(server_task, timeout=2.0)
        except asyncio.TimeoutError:
            server_task.cancel()


if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_pathfinding_scenario_movement())
    asyncio.run(test_pathfinding_scenario_waypoint_accuracy())
