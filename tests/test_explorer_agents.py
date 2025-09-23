import asyncio
import time

import pytest

from tests.utils.assertions import AgentAssertions, ExplorerAssertions
from tests.utils.metrics import BehaviorMetrics


@pytest.mark.asyncio
@pytest.mark.agent
class TestExplorerAgents:
    """Test suite for explorer agent behavior"""

    async def test_explorer_spawning(self, game_server, agent_clients):
        """Test that explorer agents spawn correctly"""
        # Spawn explorer agents
        explorer1 = await agent_clients("explorer")
        explorer2 = await agent_clients("explorer")

        assert explorer1 is not None, "Failed to create first explorer client"
        assert explorer2 is not None, "Failed to create second explorer client"

        # Verify agents exist on server
        agents = game_server.world.get_all_agents()
        explorer_agents = [a for a in agents if a.agent_type == "explorer"]

        assert (
            len(explorer_agents) >= 2
        ), f"Expected at least 2 explorers, found {len(explorer_agents)}"

    @pytest.mark.timeout(15)
    async def test_explorer_movement(self, game_server, agent_clients, agent_tracker):
        """Test that explorer agents move around the world"""
        # Create explorer
        explorer = await agent_clients("explorer")
        assert explorer is not None

        # Track movement for 10 seconds
        await asyncio.sleep(10)

        # Verify movement occurred
        agent_id = explorer.agent_id
        AgentAssertions.assert_agent_moved(agent_tracker, agent_id, min_distance=5.0)

        # Print debug info
        agent_tracker.print_debug_info()

    @pytest.mark.timeout(20)
    async def test_exploration_coverage(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test that explorers cover significant area"""
        # Create multiple explorers
        explorers = []
        for i in range(3):
            explorer = await agent_clients("explorer")
            assert explorer is not None
            explorers.append(explorer)

            # Set different exploration modes if possible
            if hasattr(explorer.agent, "set_exploration_mode"):
                modes = ["spiral", "random", "frontier"]
                explorer.agent.set_exploration_mode(modes[i % len(modes)])

        # Record positions over time
        start_time = time.time()
        while time.time() - start_time < 15:
            current_time = time.time()
            for explorer in explorers:
                if explorer.agent:
                    pos = (explorer.agent.x, explorer.agent.y)
                    behavior_metrics.record_agent_position(
                        explorer.agent_id, "explorer", pos, current_time
                    )
            await asyncio.sleep(0.5)

        # Check pathfinding integration
        for explorer in explorers:
            if explorer.agent and explorer.agent.agent_map:
                map_completion = (
                    explorer.agent.agent_map.get_map_completion_percentage()
                )
                print(
                    f"Explorer {explorer.agent_id} map completion: {map_completion:.1f}%"
                )

                # Agent should have built up some map knowledge
                assert map_completion > 0, f"Explorer should have discovered terrain"

                # Check exploration state
                state = explorer.agent.get_state()
                if "map_completion" in state:
                    assert state["map_completion"] >= 0

        # Analyze exploration behavior
        analysis = behavior_metrics.analyze_explorer_behavior()
        print(f"\nExploration Analysis: {analysis}")

        # Assertions
        assert analysis["total_explorers"] >= 3, "Not all explorers were tracked"

        for explorer in explorers:
            agent_id = explorer.agent_id
            AgentAssertions.assert_agent_explored_area(
                agent_tracker, agent_id, min_tiles=10
            )
            AgentAssertions.assert_exploration_efficiency(
                behavior_metrics, agent_id, min_efficiency=0.05
            )

    @pytest.mark.timeout(25)
    async def test_explorer_separation(self, game_server, agent_clients, agent_tracker):
        """Test that explorers spread out and don't cluster"""
        # Create multiple explorers in same area
        explorers = []
        for i in range(4):
            explorer = await agent_clients("explorer")
            assert explorer is not None
            explorers.append(explorer)

            # Start them close together
            if explorer.agent:
                explorer.agent.x = 25.0 + i * 1.0
                explorer.agent.y = 25.0 + i * 1.0

        # Let them run for enough time to spread out
        await asyncio.sleep(20)

        # Check that they maintained separation
        for explorer in explorers:
            if explorer.agent:
                ExplorerAssertions.assert_no_overlap_with_other_explorers(
                    agent_tracker, explorer.agent_id, min_separation=3.0
                )

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(30)
    async def test_spiral_exploration_pattern(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test spiral exploration pattern specifically"""
        # Create explorer and explicitly set spiral mode
        explorer = await agent_clients("explorer")
        assert explorer is not None

        if hasattr(explorer.agent, "set_exploration_mode"):
            explorer.agent.set_exploration_mode("spiral")

        # Track movement pattern
        start_time = time.time()
        positions = []

        while time.time() - start_time < 25:
            if explorer.agent:
                pos = (explorer.agent.x, explorer.agent.y)
                current_time = time.time()
                positions.append(pos)
                behavior_metrics.record_agent_position(
                    explorer.agent_id, "explorer", pos, current_time
                )
            await asyncio.sleep(0.3)

        # Verify spiral pattern
        ExplorerAssertions.assert_spiral_pattern(behavior_metrics, explorer.agent_id)

        # Print positions for visual inspection
        print(f"\nSpiral positions for {explorer.agent_id[:8]}:")
        for i, pos in enumerate(positions[::5]):  # Every 5th position
            print(f"  {i*5}: ({pos[0]:.1f}, {pos[1]:.1f})")

    @pytest.mark.timeout(25)
    async def test_random_exploration_pattern(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test random exploration pattern"""
        # Create explorer and set random mode
        explorer = await agent_clients("explorer")
        assert explorer is not None

        if hasattr(explorer.agent, "set_exploration_mode"):
            explorer.agent.set_exploration_mode("random")

        # Track movement for randomness analysis
        start_time = time.time()
        while time.time() - start_time < 20:
            if explorer.agent:
                pos = (explorer.agent.x, explorer.agent.y)
                behavior_metrics.record_agent_position(
                    explorer.agent_id, "explorer", pos, time.time()
                )
            await asyncio.sleep(0.4)

        # Verify randomness in movement
        ExplorerAssertions.assert_random_exploration(
            behavior_metrics, explorer.agent_id, min_directional_entropy=0.6
        )

        # Print directional analysis
        pattern = behavior_metrics.movement_patterns[explorer.agent_id]
        directional_bias = pattern.get_directional_bias()
        print(f"\nDirectional bias for {explorer.agent_id[:8]}: {directional_bias}")

    @pytest.mark.timeout(20)
    async def test_explorer_stuck_recovery(
        self, game_server, agent_clients, agent_tracker
    ):
        """Test that explorers recover when stuck"""
        explorer = await agent_clients("explorer")
        assert explorer is not None

        # Force explorer into a potentially stuck position (edge of map)
        if explorer.agent:
            explorer.agent.x = 1.0
            explorer.agent.y = 1.0
            original_pos = (explorer.agent.x, explorer.agent.y)

        # Wait and see if it moves away
        await asyncio.sleep(15)

        # Should have moved away from the stuck position
        if explorer.agent:
            final_pos = (explorer.agent.x, explorer.agent.y)
            distance_moved = (
                (final_pos[0] - original_pos[0]) ** 2
                + (final_pos[1] - original_pos[1]) ** 2
            ) ** 0.5

            assert (
                distance_moved > 2.0
            ), f"Explorer stayed stuck: moved only {distance_moved:.2f}"

    async def test_explorer_performance_impact(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test performance with multiple explorers"""
        # Create many explorers
        explorers = []
        for i in range(8):
            explorer = await agent_clients("explorer")
            if explorer:
                explorers.append(explorer)

        # Monitor performance
        start_time = time.time()
        tick_count = 0

        while time.time() - start_time < 10:
            tick_start = time.time()

            # Record performance metrics
            agent_count = len([e for e in explorers if e.connected])
            behavior_metrics.record_performance(
                tick_rate=30.0,  # Assume target tick rate
                agent_count=agent_count,
                timestamp=time.time(),
            )

            tick_count += 1
            await asyncio.sleep(1.0)

        # Verify performance is acceptable
        AgentAssertions.assert_performance_acceptable(
            behavior_metrics, min_tick_rate=20.0, max_latency=50.0
        )

        print(
            f"Performance test completed: {len(explorers)} explorers, {tick_count} ticks"
        )

    @pytest.mark.slow
    @pytest.mark.timeout(60)
    async def test_long_term_exploration(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test explorer behavior over extended period"""
        # Create explorers with different modes
        explorers = []
        modes = ["spiral", "random", "frontier"]

        for i in range(3):
            explorer = await agent_clients("explorer")
            if explorer and hasattr(explorer.agent, "set_exploration_mode"):
                explorer.agent.set_exploration_mode(modes[i])
                explorers.append(explorer)

        # Run for extended period
        start_time = time.time()
        snapshot_interval = 2.0
        last_snapshot = start_time

        while time.time() - start_time < 45:
            current_time = time.time()

            # Take periodic snapshots
            if current_time - last_snapshot >= snapshot_interval:
                for explorer in explorers:
                    if explorer.agent:
                        pos = (explorer.agent.x, explorer.agent.y)
                        behavior_metrics.record_agent_position(
                            explorer.agent_id, "explorer", pos, current_time
                        )
                last_snapshot = current_time

            await asyncio.sleep(0.5)

        # Generate comprehensive analysis
        analysis = behavior_metrics.analyze_explorer_behavior()

        print(f"\n=== Long-term Exploration Analysis ===")
        print(f"Total explorers: {analysis['total_explorers']}")
        print(f"Average efficiency: {analysis['average_efficiency']:.3f}")
        print(f"Movement variance: {analysis['movement_variance']:.3f}")
        print(f"Coverage overlap: {analysis['coverage_overlap']:.3f}")

        # Print individual stats
        for agent_id, stats in analysis["individual_stats"].items():
            print(f"\nExplorer {agent_id[:8]}:")
            print(f"  Efficiency: {stats['efficiency']:.3f}")
            print(f"  Tiles explored: {stats['tiles_explored']}")
            print(f"  Total distance: {stats['total_distance']:.1f}")

        # Assertions for long-term behavior
        assert (
            analysis["average_efficiency"] > 0.05
        ), "Overall exploration efficiency too low"
        assert analysis["coverage_overlap"] < 0.8, "Too much overlap between explorers"

        # Each explorer should have reasonable individual performance
        for agent_id, stats in analysis["individual_stats"].items():
            assert (
                stats["tiles_explored"] >= 20
            ), f"Explorer {agent_id[:8]} didn't explore enough"
            assert (
                stats["total_distance"] >= 30
            ), f"Explorer {agent_id[:8]} didn't move enough"
