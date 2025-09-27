"""
Integration tests for the action system using the new test framework.

Tests complete action flows with real server components while
maintaining fast execution through contract-based assertions.
"""

import pytest
import asyncio
from tests.framework.world_builder import WorldBuilder, PredefinedWorlds
from tests.framework.test_server import (
    TestGameServer, TestServerConfig, IntegrationTestContext,
    create_client_server_test
)
from shared.actions import ActionType, ActionRequest


class TestActionSystemIntegration:
    """Integration tests for complete action request-response flows"""

    @pytest.mark.asyncio
    async def test_movement_action_with_real_validation(self):
        """Test movement action with real server validation"""
        # Arrange: Create test environment
        config = TestServerConfig(world_width=10, world_height=10, time_acceleration=5.0)
        world_builder = PredefinedWorlds.empty_arena(10)

        async with IntegrationTestContext(config, world_builder) as ctx:
            client = await ctx.add_client("player", 2.0, 2.0)

            # Act: Request movement action
            action_id = await client.agent.action_manager.request_action(
                ActionType.MOVE_TO,
                {
                    "target_x": 5.0,
                    "target_y": 5.0,
                    "current_x": 2.0,
                    "current_y": 2.0,
                    "speed_multiplier": 1.0
                }
            )

            # Wait for movement to process
            await asyncio.sleep(0.5)

            # Assert: Agent position updated
            server_pos = ctx.server.get_agent_position(client.agent_id)
            assert server_pos is not None, "Agent should exist on server"

            # Agent should have moved toward target
            new_x, new_y = server_pos
            initial_distance = ((5.0 - 2.0) ** 2 + (5.0 - 2.0) ** 2) ** 0.5
            final_distance = ((5.0 - new_x) ** 2 + (5.0 - new_y) ** 2) ** 0.5

            assert final_distance < initial_distance, \
                f"Agent should move toward target. Initial: {initial_distance}, Final: {final_distance}"

    @pytest.mark.asyncio
    async def test_movement_rejection_for_invalid_positions(self):
        """Test that server properly rejects invalid movement requests"""
        config = TestServerConfig(world_width=10, world_height=10)
        world_builder = PredefinedWorlds.empty_arena(10)

        async with IntegrationTestContext(config, world_builder) as ctx:
            client = await ctx.add_client("player", 5.0, 5.0)

            initial_pos = ctx.server.get_agent_position(client.agent_id)

            # Act: Request movement to invalid position (outside world)
            action_id = await client.agent.action_manager.request_action(
                ActionType.MOVE_TO,
                {
                    "target_x": 20.0,  # Outside world bounds
                    "target_y": 20.0,
                    "current_x": 5.0,
                    "current_y": 5.0,
                    "speed_multiplier": 1.0
                }
            )

            await asyncio.sleep(0.2)

            # Assert: Agent position unchanged (movement rejected)
            final_pos = ctx.server.get_agent_position(client.agent_id)
            assert initial_pos == final_pos, \
                "Agent position should be unchanged after invalid movement request"

    @pytest.mark.asyncio
    async def test_multiple_agents_collision_avoidance(self):
        """Test that multiple agents avoid colliding with each other"""
        config = TestServerConfig(world_width=10, world_height=10, time_acceleration=3.0)
        world_builder = PredefinedWorlds.empty_arena(10)

        async with IntegrationTestContext(config, world_builder) as ctx:
            # Add multiple agents close together
            client1 = await ctx.add_client("explorer", 4.0, 5.0)
            client2 = await ctx.add_client("explorer", 6.0, 5.0)

            # Let agents move for a while
            for _ in range(20):  # Multiple update cycles
                client1.update(0.1)
                client2.update(0.1)
                await asyncio.sleep(0.05)

            # Check final positions
            pos1 = ctx.server.get_agent_position(client1.agent_id)
            pos2 = ctx.server.get_agent_position(client2.agent_id)

            if pos1 and pos2:
                distance = ((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2) ** 0.5
                assert distance > 1.0, f"Agents too close: {distance} units apart"

    @pytest.mark.asyncio
    async def test_pathfinding_around_obstacles(self):
        """Test that agents can pathfind around obstacles"""
        config = TestServerConfig(world_width=15, world_height=15, time_acceleration=5.0)

        # Create world with obstacle between start and target
        world_builder = (WorldBuilder(15, 15)
                        .with_seed(12345)
                        .add_room(top_left=(6, 6), width=4, height=4, door_positions=[])  # Solid obstacle
                        .add_agent_spawn("explorer", 3, 8))

        async with IntegrationTestContext(config, world_builder) as ctx:
            client = await ctx.add_client("explorer", 3.0, 8.0)

            # Set target on other side of obstacle
            if hasattr(client.agent, 'set_target'):
                client.agent.set_target(12.0, 8.0)

            # Let agent attempt navigation
            for _ in range(50):  # Extended time for pathfinding
                client.update(0.1)
                await asyncio.sleep(0.02)

            # Check if agent made progress around obstacle
            final_pos = ctx.server.get_agent_position(client.agent_id)
            if final_pos:
                final_x, final_y = final_pos
                # Agent should have moved right and around obstacle
                assert final_x > 3.0, "Agent should move toward target despite obstacle"

    @pytest.mark.asyncio
    async def test_action_system_handles_rapid_requests(self):
        """Test that action system handles multiple rapid requests gracefully"""
        config = TestServerConfig(world_width=20, world_height=20, time_acceleration=10.0)
        world_builder = PredefinedWorlds.empty_arena(20)

        async with IntegrationTestContext(config, world_builder) as ctx:
            client = await ctx.add_client("player", 10.0, 10.0)

            # Send multiple movement requests rapidly
            action_ids = []
            for i in range(5):
                action_id = await client.agent.action_manager.request_action(
                    ActionType.MOVE_TO,
                    {
                        "target_x": 10.0 + i,
                        "target_y": 10.0 + i,
                        "current_x": 10.0,
                        "current_y": 10.0,
                        "speed_multiplier": 1.0
                    }
                )
                action_ids.append(action_id)

            # Wait for processing
            await asyncio.sleep(1.0)

            # System should handle all requests without crashing
            final_pos = ctx.server.get_agent_position(client.agent_id)
            assert final_pos is not None, "Agent should still exist after rapid requests"

            # Agent should have moved from initial position
            final_x, final_y = final_pos
            distance_moved = ((final_x - 10.0) ** 2 + (final_y - 10.0) ** 2) ** 0.5
            assert distance_moved > 0.5, "Agent should have moved despite rapid requests"


class TestRealWorldScenarios:
    """Integration tests for realistic game scenarios"""

    @pytest.mark.asyncio
    async def test_explorer_discovers_and_navigates_complex_environment(self):
        """Test explorer behavior in complex environment with multiple features"""
        config = TestServerConfig(world_width=25, world_height=25, time_acceleration=5.0)

        # Create complex world
        world_builder = (PredefinedWorlds.resource_gathering_area()
                        .add_simple_maze()  # Add maze elements
                        .add_corridor(start=(1, 12), end=(20, 12), width=2))  # Add corridor

        async with IntegrationTestContext(config, world_builder) as ctx:
            client = await ctx.add_client("explorer", 2.0, 2.0)

            # Let explorer run for extended period
            initial_pos = ctx.server.get_agent_position(client.agent_id)

            for _ in range(100):  # Extended exploration time
                client.update(0.1)
                await asyncio.sleep(0.01)

            # Verify explorer behavior
            final_pos = ctx.server.get_agent_position(client.agent_id)

            assert initial_pos != final_pos, "Explorer should move during exploration"

            if final_pos:
                # Explorer should stay within world bounds
                assert 0 <= final_pos[0] < 25, "Explorer should stay in world bounds"
                assert 0 <= final_pos[1] < 25, "Explorer should stay in world bounds"

    @pytest.mark.asyncio
    async def test_multi_agent_coordination_scenario(self):
        """Test multiple agents working in same environment"""
        config = TestServerConfig(world_width=20, world_height=20, time_acceleration=3.0)
        world_builder = (WorldBuilder(20, 20)
                        .with_seed(77777)
                        .add_water_pond(center=(10, 10), radius=4)
                        .add_scattered_resources(TileType.WOOD, 5))

        async with IntegrationTestContext(config, world_builder) as ctx:
            # Add multiple different agent types
            explorer = await ctx.add_client("explorer", 5.0, 5.0)
            player = await ctx.add_client("player", 15.0, 15.0)

            # Let agents run simultaneously
            for _ in range(60):
                explorer.update(0.1)
                player.update(0.1)
                await asyncio.sleep(0.02)

            # Verify both agents behaved reasonably
            explorer_pos = ctx.server.get_agent_position(explorer.agent_id)
            player_pos = ctx.server.get_agent_position(player.agent_id)

            assert explorer_pos is not None, "Explorer should remain active"
            assert player_pos is not None, "Player should remain active"

            # Agents should maintain reasonable separation
            if explorer_pos and player_pos:
                distance = ((explorer_pos[0] - player_pos[0]) ** 2 +
                           (explorer_pos[1] - player_pos[1]) ** 2) ** 0.5
                # They might be close, but shouldn't be exactly overlapping
                assert distance > 0.1, "Agents should not overlap exactly"

    @pytest.mark.asyncio
    async def test_server_handles_client_disconnection_gracefully(self):
        """Test that server handles client disconnection without issues"""
        config = TestServerConfig(world_width=10, world_height=10)
        world_builder = PredefinedWorlds.empty_arena(10)

        async with IntegrationTestContext(config, world_builder) as ctx:
            # Connect multiple clients
            client1 = await ctx.add_client("player", 3.0, 3.0)
            client2 = await ctx.add_client("explorer", 7.0, 7.0)

            # Let them run briefly
            for _ in range(10):
                client1.update(0.1)
                client2.update(0.1)
                await asyncio.sleep(0.05)

            # Disconnect one client
            await client1.disconnect()

            # Continue with remaining client
            for _ in range(10):
                client2.update(0.1)
                await asyncio.sleep(0.05)

            # Remaining client should still function
            final_pos = ctx.server.get_agent_position(client2.agent_id)
            assert final_pos is not None, "Remaining client should still function after disconnection"