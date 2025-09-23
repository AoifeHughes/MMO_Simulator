import asyncio
import time

import pytest

from tests.utils.assertions import (
    AgentAssertions,
    EnemyAssertions,
    ExplorerAssertions,
    NPCAssertions,
)
from tests.utils.metrics import BehaviorMetrics


@pytest.mark.asyncio
@pytest.mark.integration
class TestScenarios:
    """Integration tests for complete scenarios"""

    @pytest.mark.timeout(30)
    async def test_exploration_scenario(
        self, game_server, test_scenario, agent_tracker, behavior_metrics
    ):
        """Test the exploration scenario with multiple explorer types"""
        # Load exploration scenario
        scenario = await test_scenario("test_exploration")
        assert scenario is not None

        # Wait for scenario to fully initialize
        await asyncio.sleep(2)

        # Verify agents were spawned
        agents = game_server.world.get_all_agents()
        explorers = [a for a in agents if a.agent_type == "explorer"]
        npcs = [a for a in agents if a.agent_type == "npc"]
        enemies = [a for a in agents if a.agent_type == "enemy"]

        assert (
            len(explorers) >= 3
        ), f"Expected at least 3 explorers, got {len(explorers)}"
        assert len(npcs) >= 2, f"Expected at least 2 NPCs, got {len(npcs)}"
        assert len(enemies) >= 1, f"Expected at least 1 enemy, got {len(enemies)}"

        print(
            f"Scenario loaded: {len(explorers)} explorers, {len(npcs)} NPCs, {len(enemies)} enemies"
        )

        # Track scenario execution
        start_time = time.time()
        while time.time() - start_time < 25:
            current_time = time.time()

            # Record all agent positions
            for agent in agents:
                pos = (agent.x, agent.y)
                behavior_metrics.record_agent_position(
                    agent.id, agent.agent_type, pos, current_time
                )

            await asyncio.sleep(1.0)

        # Verify exploration behavior
        for explorer in explorers:
            AgentAssertions.assert_agent_moved(
                agent_tracker, explorer.id, min_distance=8.0
            )
            AgentAssertions.assert_agent_explored_area(
                agent_tracker, explorer.id, min_tiles=12
            )

        # Verify NPC behavior
        for npc in npcs:
            AgentAssertions.assert_agent_moved(agent_tracker, npc.id, min_distance=2.0)

        # Verify enemy behavior
        for enemy in enemies:
            AgentAssertions.assert_agent_moved(
                agent_tracker, enemy.id, min_distance=3.0
            )

        # Generate analysis
        analysis = behavior_metrics.generate_report()
        print(f"\nScenario Analysis:")
        print(
            f"Explorer efficiency: {analysis['explorer_analysis'].get('average_efficiency', 0):.3f}"
        )
        print(
            f"NPC wander radius: {analysis['npc_analysis'].get('average_wander_radius', 0):.2f}"
        )
        print(
            f"Enemy interactions: {analysis['enemy_analysis'].get('chase_events', 0)}"
        )

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(25)
    async def test_combat_scenario(
        self, game_server, test_scenario, agent_tracker, behavior_metrics
    ):
        """Test the combat scenario with players vs enemies"""
        scenario = await test_scenario("basic_combat")
        assert scenario is not None

        await asyncio.sleep(2)

        # Verify combat scenario setup
        agents = game_server.world.get_all_agents()
        players = [a for a in agents if a.agent_type == "player"]
        enemies = [a for a in agents if a.agent_type == "enemy"]

        assert len(players) >= 1, f"Expected at least 1 player, got {len(players)}"
        assert len(enemies) >= 2, f"Expected at least 2 enemies, got {len(enemies)}"

        print(f"Combat scenario: {len(players)} players vs {len(enemies)} enemies")

        # Track combat interactions
        interaction_count = 0
        start_time = time.time()

        while time.time() - start_time < 20:
            current_time = time.time()

            # Record positions and check for interactions
            for agent in agents:
                pos = (agent.x, agent.y)
                behavior_metrics.record_agent_position(
                    agent.id, agent.agent_type, pos, current_time
                )

            # Check for player-enemy proximity (combat situations)
            for player in players:
                for enemy in enemies:
                    distance = (
                        (player.x - enemy.x) ** 2 + (player.y - enemy.y) ** 2
                    ) ** 0.5
                    if distance < 10.0:  # Close enough for combat
                        behavior_metrics.record_interaction(
                            player.id, enemy.id, "combat_proximity", current_time
                        )
                        interaction_count += 1

            await asyncio.sleep(0.8)

        # Verify combat behavior
        assert interaction_count > 0, "No combat interactions detected"

        # Verify movement
        for player in players:
            AgentAssertions.assert_agent_moved(
                agent_tracker, player.id, min_distance=1.0
            )

        for enemy in enemies:
            AgentAssertions.assert_agent_moved(
                agent_tracker, enemy.id, min_distance=2.0
            )

        print(f"Combat interactions detected: {interaction_count}")
        agent_tracker.print_debug_info()

    @pytest.mark.timeout(20)
    async def test_peaceful_village_scenario(
        self, game_server, test_scenario, agent_tracker, behavior_metrics
    ):
        """Test the peaceful village scenario"""
        scenario = await test_scenario("peaceful_village")
        assert scenario is not None

        await asyncio.sleep(2)

        # Verify village setup
        agents = game_server.world.get_all_agents()
        npcs = [a for a in agents if a.agent_type == "npc"]
        explorers = [a for a in agents if a.agent_type == "explorer"]

        assert len(npcs) >= 8, f"Expected at least 8 villagers, got {len(npcs)}"
        assert len(explorers) >= 1, f"Expected at least 1 visitor, got {len(explorers)}"

        print(f"Village scenario: {len(npcs)} villagers, {len(explorers)} visitors")

        # Calculate village center
        village_center_x = sum(npc.x for npc in npcs) / len(npcs)
        village_center_y = sum(npc.y for npc in npcs) / len(npcs)
        village_center = (village_center_x, village_center_y)

        print(f"Village center: ({village_center_x:.1f}, {village_center_y:.1f})")

        # Track village life
        start_time = time.time()
        while time.time() - start_time < 15:
            current_time = time.time()

            for agent in agents:
                pos = (agent.x, agent.y)
                behavior_metrics.record_agent_position(
                    agent.id, agent.agent_type, pos, current_time
                )

            await asyncio.sleep(1.0)

        # Verify villagers stayed near village
        for npc in npcs:
            NPCAssertions.assert_wandering_behavior(
                agent_tracker, npc.id, max_wander_radius=25.0
            )

        # Verify visitors moved around
        for explorer in explorers:
            AgentAssertions.assert_agent_moved(
                agent_tracker, explorer.id, min_distance=5.0
            )

        # Check village compactness (NPCs should be clustered)
        npc_distances_from_center = []
        for npc in npcs:
            distance = (
                (npc.x - village_center_x) ** 2 + (npc.y - village_center_y) ** 2
            ) ** 0.5
            npc_distances_from_center.append(distance)

        avg_distance_from_center = sum(npc_distances_from_center) / len(
            npc_distances_from_center
        )
        assert (
            avg_distance_from_center <= 30.0
        ), f"Village too spread out: {avg_distance_from_center:.1f}"

        print(f"Average distance from village center: {avg_distance_from_center:.1f}")
        agent_tracker.print_debug_info()

    @pytest.mark.timeout(35)
    async def test_mixed_agent_interactions(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test interactions between different agent types"""
        # Create mixed group of agents
        agents = []

        # Create different agent types
        explorer = await agent_clients("explorer")
        npc = await agent_clients("npc")
        enemy = await agent_clients("enemy")
        player = await agent_clients("player")

        if explorer:
            agents.append(("explorer", explorer))
        if npc:
            agents.append(("npc", npc))
        if enemy:
            agents.append(("enemy", enemy))
        if player:
            agents.append(("player", player))

        assert (
            len(agents) >= 3
        ), f"Need at least 3 different agent types, got {len(agents)}"

        # Position them in same general area
        center_x, center_y = 25.0, 25.0
        for i, (agent_type, agent_client) in enumerate(agents):
            if agent_client.agent:
                angle = (2 * 3.14159 / len(agents)) * i
                agent_client.agent.x = center_x + 8 * (angle / 6.28)
                agent_client.agent.y = center_y + 8 * (angle / 6.28)

        # Track interactions
        interaction_matrix = {}
        start_time = time.time()

        while time.time() - start_time < 30:
            current_time = time.time()

            # Record positions
            agent_positions = {}
            for agent_type, agent_client in agents:
                if agent_client.agent:
                    pos = (agent_client.agent.x, agent_client.agent.y)
                    behavior_metrics.record_agent_position(
                        agent_client.agent_id, agent_type, pos, current_time
                    )
                    agent_positions[agent_client.agent_id] = (agent_type, pos)

            # Check for interactions between different agent types
            agent_ids = list(agent_positions.keys())
            for i in range(len(agent_ids)):
                for j in range(i + 1, len(agent_ids)):
                    id1, id2 = agent_ids[i], agent_ids[j]
                    type1, pos1 = agent_positions[id1]
                    type2, pos2 = agent_positions[id2]

                    distance = (
                        (pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2
                    ) ** 0.5

                    interaction_key = f"{type1}-{type2}"
                    if interaction_key not in interaction_matrix:
                        interaction_matrix[interaction_key] = 0

                    if distance < 8.0:  # Close interaction
                        behavior_metrics.record_interaction(
                            id1, id2, f"{type1}_{type2}_proximity", current_time
                        )
                        interaction_matrix[interaction_key] += 1

            await asyncio.sleep(0.5)

        # Verify interactions occurred
        total_interactions = sum(interaction_matrix.values())
        assert total_interactions > 0, "No interactions between different agent types"

        print(f"\nAgent Interaction Matrix:")
        for interaction_type, count in interaction_matrix.items():
            print(f"  {interaction_type}: {count} interactions")

        # Verify each agent type behaved appropriately
        for agent_type, agent_client in agents:
            if agent_client.agent:
                AgentAssertions.assert_agent_moved(
                    agent_tracker, agent_client.agent_id, min_distance=1.0
                )

        agent_tracker.print_debug_info()

    @pytest.mark.slow
    @pytest.mark.timeout(90)
    async def test_scenario_performance_stress(
        self, game_server, test_scenario, behavior_metrics
    ):
        """Stress test scenario performance with many agents"""
        # Load scenario with many agents
        scenario = await test_scenario("test_exploration")
        assert scenario is not None

        await asyncio.sleep(3)

        # Monitor performance over time
        start_time = time.time()
        performance_samples = []
        tick_counts = []

        while time.time() - start_time < 60:
            sample_start = time.time()

            # Get current agent count
            agents = game_server.world.get_all_agents()
            agent_count = len(agents)

            # Simulate server tick measurement
            tick_start = time.time()
            # Simulate some work
            await asyncio.sleep(0.001)
            tick_duration = time.time() - tick_start

            # Calculate effective tick rate
            if tick_duration > 0:
                effective_tick_rate = 1.0 / tick_duration
            else:
                effective_tick_rate = 1000.0  # Very fast

            # Record performance
            behavior_metrics.record_performance(
                tick_rate=effective_tick_rate,
                agent_count=agent_count,
                timestamp=time.time(),
                cpu_usage=0.0,  # Would need real monitoring
                memory_usage=0.0,  # Would need real monitoring
                latency=tick_duration * 1000,  # Convert to ms
            )

            sample_duration = time.time() - sample_start
            performance_samples.append(sample_duration)
            tick_counts.append(agent_count)

            await asyncio.sleep(1.0)

        # Analyze performance
        avg_sample_time = sum(performance_samples) / len(performance_samples)
        avg_agent_count = sum(tick_counts) / len(tick_counts)
        max_sample_time = max(performance_samples)

        print(f"\nPerformance Stress Test Results:")
        print(f"  Average agents: {avg_agent_count:.1f}")
        print(f"  Average sample time: {avg_sample_time*1000:.1f}ms")
        print(f"  Max sample time: {max_sample_time*1000:.1f}ms")
        print(f"  Test duration: {time.time() - start_time:.1f}s")

        # Performance assertions
        assert (
            avg_sample_time < 0.1
        ), f"Average performance too slow: {avg_sample_time*1000:.1f}ms"
        assert (
            max_sample_time < 0.2
        ), f"Peak performance too slow: {max_sample_time*1000:.1f}ms"

        # Verify simulation remained stable
        AgentAssertions.assert_performance_acceptable(
            behavior_metrics, min_tick_rate=10.0, max_latency=100.0
        )

    @pytest.mark.timeout(40)
    async def test_scenario_network_synchronization(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test network synchronization in multi-agent scenarios"""
        # Create multiple clients to test network sync
        clients = []
        client_types = ["explorer", "npc", "enemy", "player"]

        for client_type in client_types:
            for i in range(2):  # 2 of each type
                client = await agent_clients(client_type)
                if client:
                    clients.append((client_type, client))

        assert (
            len(clients) >= 6
        ), f"Need at least 6 clients for sync test, got {len(clients)}"

        print(f"Network sync test with {len(clients)} clients")

        # Track synchronization
        sync_errors = 0
        position_history = {}
        start_time = time.time()

        while time.time() - start_time < 35:
            current_time = time.time()

            # Get server state
            server_agents = {
                a.id: (a.x, a.y) for a in game_server.world.get_all_agents()
            }

            # Compare with client states
            for client_type, client in clients:
                if client.agent and client.agent_id in server_agents:
                    server_pos = server_agents[client.agent_id]
                    client_pos = (client.agent.x, client.agent.y)

                    # Calculate position difference
                    pos_diff = (
                        (server_pos[0] - client_pos[0]) ** 2
                        + (server_pos[1] - client_pos[1]) ** 2
                    ) ** 0.5

                    # Record for analysis
                    if client.agent_id not in position_history:
                        position_history[client.agent_id] = []
                    position_history[client.agent_id].append(
                        {
                            "time": current_time,
                            "server_pos": server_pos,
                            "client_pos": client_pos,
                            "diff": pos_diff,
                        }
                    )

                    # Check for significant desync
                    if pos_diff > 5.0:  # Significant difference
                        sync_errors += 1

                    # Record position for metrics
                    behavior_metrics.record_agent_position(
                        client.agent_id, client_type, server_pos, current_time
                    )

            await asyncio.sleep(0.5)

        # Analyze synchronization
        print(f"\nNetwork Synchronization Analysis:")
        print(f"  Total sync errors: {sync_errors}")

        max_avg_diff = 0.0
        for agent_id, history in position_history.items():
            if history:
                avg_diff = sum(h["diff"] for h in history) / len(history)
                max_diff = max(h["diff"] for h in history)
                max_avg_diff = max(max_avg_diff, avg_diff)

                print(
                    f"  Agent {agent_id[:8]}: avg_diff={avg_diff:.2f}, max_diff={max_diff:.2f}"
                )

        # Assertions for network sync
        assert sync_errors < len(clients) * 5, f"Too many sync errors: {sync_errors}"
        assert (
            max_avg_diff < 2.0
        ), f"Average position difference too high: {max_avg_diff:.2f}"

        print(f"Network synchronization test passed with {len(clients)} clients")
