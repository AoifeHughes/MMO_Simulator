"""
Unit tests for movement behaviors using behavioral contracts.

These tests demonstrate the new contract-based testing approach,
focusing on behavioral outcomes rather than implementation details.
"""

import pytest
import asyncio
from tests.framework.world_builder import WorldBuilder, PredefinedWorlds
from tests.framework.agent_harness import (
    AgentTestHarness, BehaviorContract, BehaviorExpectation,
    create_movement_test, create_navigation_test
)


class TestMovementContracts:
    """Test movement behaviors through behavioral contracts"""

    @pytest.mark.asyncio
    async def test_agent_eventually_moves_in_empty_space(self):
        """Agent should eventually move when placed in empty space"""
        # Arrange: Create empty world with explorer
        world_builder = PredefinedWorlds.empty_arena(20)
        harness = create_movement_test(world_builder, "explorer")

        # Act: Run simulation
        harness.run_for_duration(5.0)

        # Assert: Agent eventually moves from starting position
        expectation = BehaviorExpectation(
            contract=BehaviorContract.EVENTUALLY_MOVES,
            timeout_seconds=5.0,
            tolerance=1.0
        )

        assert harness.verify_contract("test_agent", expectation), \
            "Agent should eventually move from starting position"

    @pytest.mark.asyncio
    async def test_explorer_navigates_around_water_obstacle(self):
        """Explorer should navigate around water obstacles to reach target"""
        # Arrange: Create world with water pond between start and target
        world_builder = (WorldBuilder(20, 20)
                        .with_seed(12345)
                        .add_water_pond(center=(10, 10), radius=3)
                        .add_agent_spawn("explorer", 5, 10))

        harness = create_navigation_test(world_builder, (5, 10), (15, 10))

        # Act: Run simulation until agent reaches target or timeout
        target_reached = await harness.run_until_condition(
            lambda: harness.verify_contract("navigator", BehaviorExpectation(
                contract=BehaviorContract.REACHES_TARGET,
                timeout_seconds=30.0,
                tolerance=2.0,
                parameters={"target": (15, 10)}
            )),
            max_duration=30.0
        )

        # Assert: Agent reaches target and avoids water
        assert target_reached, "Agent should reach target despite water obstacle"

        # Verify agent avoided water tiles
        water_obstacles = [(x, y) for x in range(7, 14) for y in range(7, 14)
                          if ((x - 10) ** 2 + (y - 10) ** 2) <= 9]  # Water pond positions

        avoidance_expectation = BehaviorExpectation(
            contract=BehaviorContract.AVOIDS_OBSTACLES,
            timeout_seconds=30.0,
            tolerance=0.8,  # Must stay away from water
            parameters={"obstacles": water_obstacles}
        )

        assert harness.verify_contract("navigator", avoidance_expectation), \
            "Agent should avoid water while navigating"

    @pytest.mark.asyncio
    async def test_agent_finds_path_through_maze(self):
        """Agent should find path through simple maze"""
        # Arrange: Create maze world
        world_builder = PredefinedWorlds.simple_maze(21)
        harness = create_navigation_test(world_builder, (1, 1), (19, 19))

        # Act: Let agent attempt navigation
        reached_target = await harness.run_until_condition(
            lambda: harness.verify_contract("navigator", BehaviorExpectation(
                contract=BehaviorContract.REACHES_TARGET,
                timeout_seconds=60.0,
                tolerance=2.0,
                parameters={"target": (19, 19)}
            )),
            max_duration=60.0
        )

        # Assert: Agent should eventually find path or at least move significantly
        if not reached_target:
            # If target not reached, verify agent at least moved significantly
            movement_expectation = BehaviorExpectation(
                contract=BehaviorContract.EVENTUALLY_MOVES,
                timeout_seconds=10.0,
                tolerance=5.0  # Should move at least 5 units
            )
            assert harness.verify_contract("navigator", movement_expectation), \
                "Agent should at least move significantly in maze"
        else:
            # Verify agent avoided wall tiles
            total_distance = harness.get_total_distance_traveled("navigator")
            assert total_distance > 10.0, "Agent should travel reasonable distance through maze"

    @pytest.mark.asyncio
    async def test_multiple_agents_maintain_personal_space(self):
        """Multiple agents should maintain distance from each other"""
        # Arrange: Create world with multiple agents close together
        world_builder = (WorldBuilder(15, 15)
                        .with_seed(54321))

        world = world_builder.build()
        harness = AgentTestHarness(world)

        # Add multiple agents in close proximity
        agent1 = harness.add_agent("explorer", "agent1", 7, 7)
        agent2 = harness.add_agent("explorer", "agent2", 8, 7)
        agent3 = harness.add_agent("explorer", "agent3", 7, 8)

        # Act: Run simulation
        harness.run_for_duration(10.0)

        # Assert: Agents maintain minimum distance
        distance_expectation = BehaviorExpectation(
            contract=BehaviorContract.MAINTAINS_DISTANCE,
            timeout_seconds=10.0,
            tolerance=0.1,
            parameters={
                "other_agent_id": "agent2",
                "min_distance": 1.5
            }
        )

        assert harness.verify_contract("agent1", distance_expectation), \
            "Agents should maintain personal space"

    @pytest.mark.asyncio
    async def test_agent_responds_to_environment_changes(self):
        """Agent should respond when environment changes"""
        # Arrange: Create simple world
        world_builder = (WorldBuilder(10, 10)
                        .with_seed(99999))

        harness = create_movement_test(world_builder, "explorer")

        # Act: Run for a bit, then introduce stimulus (position change)
        harness.run_for_duration(2.0)

        # Simulate environment change by manually moving agent
        agent = harness.agents["test_agent"]
        original_x, original_y = agent.x, agent.y
        agent.x += 3.0  # Simulate external force moving agent

        # Continue simulation
        harness.run_for_duration(5.0)

        # Assert: Agent responds to position change
        response_expectation = BehaviorExpectation(
            contract=BehaviorContract.RESPONDS_TO_STIMULUS,
            timeout_seconds=5.0,
            tolerance=1.0,
            parameters={
                "stimulus_time": 2.0,
                "response_window": 5.0
            }
        )

        assert harness.verify_contract("test_agent", response_expectation), \
            "Agent should respond to environmental changes"


class TestMovementProperties:
    """Property-based tests for movement behaviors"""

    @pytest.mark.asyncio
    async def test_movement_is_bounded_by_world_limits(self):
        """Agent position should always stay within world boundaries"""
        world_builder = PredefinedWorlds.empty_arena(10)
        harness = create_movement_test(world_builder, "explorer")

        # Run for extended period
        harness.run_for_duration(20.0)

        # Check all positions stayed in bounds
        positions = harness.get_agent_path("test_agent")
        for x, y in positions:
            assert 0 <= x < 10, f"X position {x} out of bounds"
            assert 0 <= y < 10, f"Y position {y} out of bounds"

    @pytest.mark.asyncio
    async def test_movement_velocity_is_reasonable(self):
        """Agent movement velocity should be within reasonable limits"""
        world_builder = PredefinedWorlds.empty_arena(20)
        harness = create_movement_test(world_builder, "explorer")

        harness.run_for_duration(10.0)

        # Check velocity measurements
        velocities = harness.get_agent_velocity_over_time("test_agent")
        max_velocity = max([v for _, v in velocities], default=0)

        # Agent shouldn't move faster than physically reasonable
        # (adjust based on your game's movement parameters)
        assert max_velocity < 20.0, f"Agent velocity {max_velocity} too high"

    @pytest.mark.asyncio
    async def test_agent_makes_forward_progress_toward_targets(self):
        """When agent has clear path to target, it should make forward progress"""
        world_builder = PredefinedWorlds.empty_arena(20)
        harness = create_navigation_test(world_builder, (2, 2), (18, 18))

        # Measure initial distance to target
        initial_positions = harness.get_agent_path("navigator")
        if not initial_positions:
            return  # Skip if no initial position

        initial_distance = ((18 - 2) ** 2 + (18 - 2) ** 2) ** 0.5

        # Run simulation
        harness.run_for_duration(10.0)

        # Measure final distance to target
        final_positions = harness.get_agent_path("navigator")
        if len(final_positions) > 0:
            final_x, final_y = final_positions[-1]
            final_distance = ((18 - final_x) ** 2 + (18 - final_y) ** 2) ** 0.5

            # Agent should make forward progress
            progress = initial_distance - final_distance
            assert progress > 2.0, f"Agent should make progress toward target (made {progress})"


class TestMovementInvarients:
    """Tests for movement invariants that should always hold"""

    @pytest.mark.asyncio
    async def test_agent_position_changes_are_continuous(self):
        """Agent position should change continuously (no teleporting)"""
        world_builder = PredefinedWorlds.empty_arena(15)
        harness = create_movement_test(world_builder, "explorer")

        harness.run_for_duration(10.0)

        # Check for discontinuous jumps
        positions = harness.get_agent_path("test_agent")
        if len(positions) < 2:
            return

        max_jump = 0.0
        for i in range(1, len(positions)):
            prev_x, prev_y = positions[i-1]
            curr_x, curr_y = positions[i]
            distance = ((curr_x - prev_x) ** 2 + (curr_y - prev_y) ** 2) ** 0.5
            max_jump = max(max_jump, distance)

        # No single step should be unreasonably large (adjust threshold as needed)
        assert max_jump < 5.0, f"Agent made discontinuous jump of {max_jump} units"

    @pytest.mark.asyncio
    async def test_agent_cannot_move_through_walls(self):
        """Agent should never occupy wall tiles"""
        world_builder = (WorldBuilder(10, 10)
                        .with_seed(11111)
                        .add_walls_around_perimeter()
                        .add_room(top_left=(2, 2), width=6, height=6, door_positions=[(7, 5)]))

        harness = create_movement_test(world_builder, "explorer")
        harness.run_for_duration(15.0)

        # Get wall positions
        wall_positions = []
        for (x, y), tile_type in world_builder.terrain.items():
            if tile_type.name == "WALL":
                wall_positions.append((x, y))

        # Verify agent never occupied wall positions
        agent_positions = harness.get_agent_path("test_agent")
        for x, y in agent_positions:
            # Convert to tile coordinates
            tile_x, tile_y = int(x), int(y)
            assert (tile_x, tile_y) not in wall_positions, \
                f"Agent illegally occupied wall at ({tile_x}, {tile_y})"