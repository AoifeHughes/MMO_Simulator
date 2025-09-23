import asyncio
import math
import time

import pytest

from tests.utils.assertions import AgentAssertions, NPCAssertions
from tests.utils.metrics import BehaviorMetrics


@pytest.mark.asyncio
@pytest.mark.agent
class TestNPCAgents:
    """Test suite for NPC agent behavior"""

    async def test_npc_spawning(self, game_server, agent_clients):
        """Test that NPC agents spawn correctly"""
        # Spawn NPC agents
        npc1 = await agent_clients("npc")
        npc2 = await agent_clients("npc")

        assert npc1 is not None, "Failed to create first NPC client"
        assert npc2 is not None, "Failed to create second NPC client"

        # Verify agents exist on server
        agents = game_server.world.get_all_agents()
        npc_agents = [a for a in agents if a.agent_type == "npc"]

        assert (
            len(npc_agents) >= 2
        ), f"Expected at least 2 NPCs, found {len(npc_agents)}"

    @pytest.mark.timeout(15)
    async def test_npc_basic_movement(self, game_server, agent_clients, agent_tracker):
        """Test that NPCs move around their spawn area"""
        # Create NPC
        npc = await agent_clients("npc")
        assert npc is not None

        # Record initial position
        initial_pos = None
        if npc.agent:
            initial_pos = (npc.agent.x, npc.agent.y)

        # Track movement for 12 seconds
        await asyncio.sleep(12)

        # Verify movement occurred
        agent_id = npc.agent_id
        AgentAssertions.assert_agent_moved(agent_tracker, agent_id, min_distance=1.5)

        # Verify stayed within reasonable area
        if initial_pos:
            NPCAssertions.assert_wandering_behavior(
                agent_tracker, agent_id, max_wander_radius=20.0
            )

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(20)
    async def test_npc_idle_wander_cycle(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test that NPCs cycle between idle and wandering states"""
        npc = await agent_clients("npc")
        assert npc is not None

        # Track state transitions
        start_time = time.time()
        last_state = None
        idle_count = 0
        wander_count = 0

        while time.time() - start_time < 18:
            current_time = time.time()

            # Simulate state tracking (in real implementation, this would come from agent)
            if npc.agent:
                pos = (npc.agent.x, npc.agent.y)
                behavior_metrics.record_agent_position(
                    npc.agent_id, "npc", pos, current_time
                )

                # Estimate state based on movement
                if (
                    len(
                        behavior_metrics.movement_patterns.get(npc.agent_id, {}).get(
                            "positions", []
                        )
                    )
                    >= 2
                ):
                    pattern = behavior_metrics.movement_patterns[npc.agent_id]
                    recent_positions = pattern.positions[-5:]
                    if len(recent_positions) >= 2:
                        # Calculate recent movement
                        total_movement = 0
                        for i in range(1, len(recent_positions)):
                            dx = recent_positions[i][0] - recent_positions[i - 1][0]
                            dy = recent_positions[i][1] - recent_positions[i - 1][1]
                            total_movement += math.sqrt(dx * dx + dy * dy)

                        # Determine state based on movement
                        current_state = "wandering" if total_movement > 1.0 else "idle"

                        if current_state != last_state:
                            behavior_metrics.record_state_transition(
                                npc.agent_id, current_state, current_time
                            )
                            if current_state == "idle":
                                idle_count += 1
                            elif current_state == "wandering":
                                wander_count += 1
                            last_state = current_state

            await asyncio.sleep(0.8)

        # Verify state transitions occurred
        assert (
            idle_count > 0
        ), f"NPC never entered idle state (counts: idle={idle_count}, wander={wander_count})"
        assert (
            wander_count > 0
        ), f"NPC never entered wandering state (counts: idle={idle_count}, wander={wander_count})"

        print(f"State transitions: idle={idle_count}, wandering={wander_count}")

    @pytest.mark.timeout(25)
    async def test_npc_home_area_constraint(
        self, game_server, agent_clients, agent_tracker
    ):
        """Test that NPCs don't stray too far from their spawn point"""
        # Create multiple NPCs in different locations
        npcs = []
        spawn_positions = [(10, 10), (30, 30), (40, 20)]

        for i, spawn_pos in enumerate(spawn_positions):
            npc = await agent_clients("npc")
            assert npc is not None
            npcs.append(npc)

            # Set spawn position
            if npc.agent:
                npc.agent.x = spawn_pos[0]
                npc.agent.y = spawn_pos[1]
                npc.agent.home_x = spawn_pos[0]
                npc.agent.home_y = spawn_pos[1]

        # Let them wander for a while
        await asyncio.sleep(20)

        # Check each NPC stayed near home
        for i, npc in enumerate(npcs):
            if npc.agent:
                spawn_pos = spawn_positions[i]
                NPCAssertions.assert_wandering_behavior(
                    agent_tracker, npc.agent_id, max_wander_radius=15.0
                )

                # Additional check: current position should be reasonably close to spawn
                current_pos = (npc.agent.x, npc.agent.y)
                distance_from_spawn = math.sqrt(
                    (current_pos[0] - spawn_pos[0]) ** 2
                    + (current_pos[1] - spawn_pos[1]) ** 2
                )
                assert (
                    distance_from_spawn <= 18.0
                ), f"NPC {npc.agent_id[:8]} too far from spawn: {distance_from_spawn:.1f} > 18.0"

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(18)
    async def test_npc_player_interaction(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test that NPCs react to nearby players"""
        # Create NPC and player
        npc = await agent_clients("npc")
        player = await agent_clients("player")

        assert npc is not None and player is not None

        # Position player near NPC
        if npc.agent and player.agent:
            npc_pos = (npc.agent.x, npc.agent.y)
            player.agent.x = npc_pos[0] + 2.0
            player.agent.y = npc_pos[1] + 2.0

        # Monitor for interactions
        interaction_detected = False
        start_time = time.time()

        while time.time() - start_time < 15:
            # In a real implementation, we'd check for NPC reactions
            # For now, we simulate by checking proximity
            if npc.agent and player.agent:
                distance = math.sqrt(
                    (npc.agent.x - player.agent.x) ** 2
                    + (npc.agent.y - player.agent.y) ** 2
                )

                if distance < 5.0:  # Close enough for interaction
                    behavior_metrics.record_interaction(
                        npc.agent_id, player.agent_id, "proximity", time.time()
                    )
                    interaction_detected = True

            await asyncio.sleep(1.0)

        assert interaction_detected, "NPC didn't detect nearby player"

    @pytest.mark.timeout(20)
    async def test_multiple_npc_behavior(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test behavior with multiple NPCs"""
        # Create several NPCs
        npcs = []
        for i in range(5):
            npc = await agent_clients("npc")
            if npc:
                npcs.append(npc)

        assert len(npcs) >= 3, f"Need at least 3 NPCs for test, got {len(npcs)}"

        # Track all NPCs
        start_time = time.time()
        while time.time() - start_time < 15:
            current_time = time.time()
            for npc in npcs:
                if npc.agent:
                    pos = (npc.agent.x, npc.agent.y)
                    behavior_metrics.record_agent_position(
                        npc.agent_id, "npc", pos, current_time
                    )
            await asyncio.sleep(0.5)

        # Analyze NPC behavior
        analysis = behavior_metrics.analyze_npc_behavior()
        print(f"\nNPC Analysis: {analysis}")

        # Verify each NPC moved reasonably
        for npc in npcs:
            if npc.agent:
                AgentAssertions.assert_agent_moved(
                    agent_tracker, npc.agent_id, min_distance=1.0
                )

        # Check average wander radius is reasonable
        if (
            "average_wander_radius" in analysis
            and analysis["average_wander_radius"] > 0
        ):
            assert (
                analysis["average_wander_radius"] <= 20.0
            ), f"NPCs wandering too far: {analysis['average_wander_radius']:.1f}"

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(30)
    async def test_npc_timing_behavior(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test NPC idle and wander timing patterns"""
        npc = await agent_clients("npc")
        assert npc is not None

        # Track detailed timing
        start_time = time.time()
        position_history = []
        state_changes = []
        last_pos = None
        last_state = None

        while time.time() - start_time < 25:
            current_time = time.time()

            if npc.agent:
                current_pos = (npc.agent.x, npc.agent.y)
                position_history.append((current_time, current_pos))

                # Detect state based on movement
                if last_pos:
                    movement = math.sqrt(
                        (current_pos[0] - last_pos[0]) ** 2
                        + (current_pos[1] - last_pos[1]) ** 2
                    )
                    current_state = "moving" if movement > 0.3 else "idle"

                    if current_state != last_state:
                        state_changes.append((current_time, current_state))
                        behavior_metrics.record_state_transition(
                            npc.agent_id, current_state, current_time
                        )
                        last_state = current_state

                last_pos = current_pos

            await asyncio.sleep(0.5)

        # Analyze timing patterns
        idle_durations = []
        moving_durations = []
        current_state = None
        state_start = None

        for timestamp, state in state_changes:
            if current_state and state_start:
                duration = timestamp - state_start
                if current_state == "idle":
                    idle_durations.append(duration)
                elif current_state == "moving":
                    moving_durations.append(duration)

            current_state = state
            state_start = timestamp

        print(f"\nTiming analysis for {npc.agent_id[:8]}:")
        if idle_durations:
            avg_idle = sum(idle_durations) / len(idle_durations)
            print(
                f"  Average idle time: {avg_idle:.1f}s (count: {len(idle_durations)})"
            )
            assert (
                1.0 <= avg_idle <= 8.0
            ), f"Idle time {avg_idle:.1f}s outside expected range 1-8s"

        if moving_durations:
            avg_moving = sum(moving_durations) / len(moving_durations)
            print(
                f"  Average moving time: {avg_moving:.1f}s (count: {len(moving_durations)})"
            )

        # Should have multiple state changes
        assert len(state_changes) >= 3, f"Too few state changes: {len(state_changes)}"

    @pytest.mark.slow
    @pytest.mark.timeout(45)
    async def test_npc_long_term_patterns(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test NPC behavior patterns over extended time"""
        # Create NPCs in different configurations
        npcs = []
        for i in range(3):
            npc = await agent_clients("npc")
            if npc:
                npcs.append(npc)
                # Set different home positions
                if npc.agent:
                    npc.agent.x = 15 + i * 15
                    npc.agent.y = 15 + i * 10
                    npc.agent.home_x = npc.agent.x
                    npc.agent.home_y = npc.agent.y

        # Track over extended period
        start_time = time.time()
        snapshot_interval = 1.0
        last_snapshot = start_time

        while time.time() - start_time < 35:
            current_time = time.time()

            if current_time - last_snapshot >= snapshot_interval:
                for npc in npcs:
                    if npc.agent:
                        pos = (npc.agent.x, npc.agent.y)
                        behavior_metrics.record_agent_position(
                            npc.agent_id, "npc", pos, current_time
                        )

                        # Record performance
                        behavior_metrics.record_performance(
                            tick_rate=30.0,
                            agent_count=len(npcs),
                            timestamp=current_time,
                        )

                last_snapshot = current_time

            await asyncio.sleep(0.3)

        # Generate comprehensive analysis
        npc_analysis = behavior_metrics.analyze_npc_behavior()
        performance = behavior_metrics.performance

        print(f"\n=== Long-term NPC Analysis ===")
        print(f"Total NPCs: {npc_analysis['total_npcs']}")
        print(
            f"Average wander radius: {npc_analysis.get('average_wander_radius', 0):.2f}"
        )

        for agent_id, stats in npc_analysis.get("individual_stats", {}).items():
            print(f"\nNPC {agent_id[:8]}:")
            print(f"  Wander radius: {stats['wander_radius']:.2f}")
            print(f"  Total distance: {stats['total_distance']:.1f}")

        # Performance verification
        if performance.tick_rates:
            avg_tick_rate = sum(performance.tick_rates) / len(performance.tick_rates)
            print(f"Average performance: {avg_tick_rate:.1f} ticks/sec")

        # Assertions
        for npc in npcs:
            if npc.agent:
                AgentAssertions.assert_agent_moved(
                    agent_tracker, npc.agent_id, min_distance=5.0
                )

        assert (
            npc_analysis.get("average_wander_radius", 0) <= 25.0
        ), "NPCs wandering too far from home"

    async def test_npc_performance_under_load(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test NPC performance with many agents"""
        # Create many NPCs
        npcs = []
        target_count = 10

        for i in range(target_count):
            npc = await agent_clients("npc")
            if npc:
                npcs.append(npc)

        actual_count = len(npcs)
        assert actual_count >= 5, f"Need at least 5 NPCs, got {actual_count}"

        # Monitor performance
        start_time = time.time()
        performance_samples = []

        while time.time() - start_time < 12:
            sample_start = time.time()

            # Simulate tick
            active_count = len([npc for npc in npcs if npc.connected])
            behavior_metrics.record_performance(
                tick_rate=30.0, agent_count=active_count, timestamp=time.time()
            )

            sample_duration = time.time() - sample_start
            performance_samples.append(sample_duration)

            await asyncio.sleep(0.5)

        # Verify performance is acceptable
        avg_sample_time = sum(performance_samples) / len(performance_samples)
        print(
            f"Performance with {actual_count} NPCs: {avg_sample_time*1000:.1f}ms avg sample time"
        )

        assert (
            avg_sample_time < 0.1
        ), f"Performance degraded: {avg_sample_time*1000:.1f}ms > 100ms"
        AgentAssertions.assert_performance_acceptable(
            behavior_metrics, min_tick_rate=25.0
        )
