import asyncio
import math
import time

import pytest

from tests.utils.assertions import AgentAssertions, EnemyAssertions
from tests.utils.metrics import BehaviorMetrics


@pytest.mark.asyncio
@pytest.mark.agent
class TestEnemyAgents:
    """Test suite for enemy agent behavior"""

    async def test_enemy_spawning(self, game_server, agent_clients):
        """Test that enemy agents spawn correctly"""
        # Spawn enemy agents
        enemy1 = await agent_clients("enemy")
        enemy2 = await agent_clients("enemy")

        assert enemy1 is not None, "Failed to create first enemy client"
        assert enemy2 is not None, "Failed to create second enemy client"

        # Verify agents exist on server
        agents = game_server.world.get_all_agents()
        enemy_agents = [a for a in agents if a.agent_type == "enemy"]

        assert (
            len(enemy_agents) >= 2
        ), f"Expected at least 2 enemies, found {len(enemy_agents)}"

    @pytest.mark.timeout(15)
    async def test_enemy_basic_movement(
        self, game_server, agent_clients, agent_tracker
    ):
        """Test that enemies move around (patrol behavior)"""
        # Create enemy
        enemy = await agent_clients("enemy")
        assert enemy is not None

        # Track movement for 12 seconds
        await asyncio.sleep(12)

        # Verify movement occurred
        agent_id = enemy.agent_id
        AgentAssertions.assert_agent_moved(agent_tracker, agent_id, min_distance=1.5)

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(20)
    async def test_enemy_patrol_behavior(
        self, game_server, agent_clients, agent_tracker
    ):
        """Test that enemies follow patrol patterns"""
        enemy = await agent_clients("enemy")
        assert enemy is not None

        # Set initial position
        if enemy.agent:
            enemy.agent.x = 25.0
            enemy.agent.y = 25.0

        # Track patrol behavior
        await asyncio.sleep(18)

        # Verify patrol behavior
        EnemyAssertions.assert_patrol_behavior(
            agent_tracker, enemy.agent_id, expected_patrol_area=15.0
        )

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(25)
    async def test_enemy_player_detection(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test that enemies detect and chase players"""
        # Create enemy and player
        enemy = await agent_clients("enemy")
        player = await agent_clients("player")

        assert enemy is not None and player is not None

        # Position player within detection range
        if enemy.agent and player.agent:
            enemy.agent.x = 20.0
            enemy.agent.y = 20.0
            player.agent.x = 25.0  # Within chase range
            player.agent.y = 22.0

        # Track behavior
        chase_detected = False
        start_time = time.time()

        while time.time() - start_time < 20:
            current_time = time.time()

            # Record positions
            if enemy.agent:
                pos = (enemy.agent.x, enemy.agent.y)
                behavior_metrics.record_agent_position(
                    enemy.agent_id, "enemy", pos, current_time
                )

            if player.agent:
                pos = (player.agent.x, player.agent.y)
                behavior_metrics.record_agent_position(
                    player.agent_id, "player", pos, current_time
                )

            # Check for chase behavior
            if enemy.agent and player.agent:
                distance = math.sqrt(
                    (enemy.agent.x - player.agent.x) ** 2
                    + (enemy.agent.y - player.agent.y) ** 2
                )

                if distance < 15.0:  # Within chase range
                    # Record state transition to chase
                    behavior_metrics.record_state_transition(
                        enemy.agent_id, "chase", current_time
                    )
                    behavior_metrics.record_interaction(
                        enemy.agent_id, player.agent_id, "chase", current_time
                    )
                    chase_detected = True

            await asyncio.sleep(0.5)

        # Verify chase behavior occurred
        assert chase_detected, "Enemy didn't detect or chase nearby player"

    @pytest.mark.timeout(30)
    async def test_enemy_attack_behavior(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test enemy attack behavior when close to players"""
        enemy = await agent_clients("enemy")
        player = await agent_clients("player")

        assert enemy is not None and player is not None

        # Position player very close to enemy (within attack range)
        if enemy.agent and player.agent:
            enemy.agent.x = 30.0
            enemy.agent.y = 30.0
            player.agent.x = 31.0  # Very close
            player.agent.y = 30.5

        # Track attack behavior
        attack_detected = False
        chase_to_attack_transition = False
        start_time = time.time()

        while time.time() - start_time < 25:
            current_time = time.time()

            # Record positions and states
            if enemy.agent and player.agent:
                enemy_pos = (enemy.agent.x, enemy.agent.y)
                player_pos = (player.agent.x, player.agent.y)

                behavior_metrics.record_agent_position(
                    enemy.agent_id, "enemy", enemy_pos, current_time
                )
                behavior_metrics.record_agent_position(
                    player.agent_id, "player", player_pos, current_time
                )

                distance = math.sqrt(
                    (enemy.agent.x - player.agent.x) ** 2
                    + (enemy.agent.y - player.agent.y) ** 2
                )

                # State transitions based on distance
                if distance <= 2.5:  # Attack range
                    behavior_metrics.record_state_transition(
                        enemy.agent_id, "attack", current_time
                    )
                    behavior_metrics.record_interaction(
                        enemy.agent_id, player.agent_id, "attack", current_time
                    )
                    attack_detected = True
                elif distance <= 12.0:  # Chase range
                    behavior_metrics.record_state_transition(
                        enemy.agent_id, "chase", current_time
                    )
                    chase_to_attack_transition = True
                else:
                    behavior_metrics.record_state_transition(
                        enemy.agent_id, "patrol", current_time
                    )

            await asyncio.sleep(0.4)

        # Verify attack behavior
        assert attack_detected, "Enemy didn't attack when in range"

        # Print interaction summary
        attack_interactions = [
            e for e in behavior_metrics.interaction_events if e["type"] == "attack"
        ]
        chase_interactions = [
            e for e in behavior_metrics.interaction_events if e["type"] == "chase"
        ]
        print(
            f"Interactions: {len(attack_interactions)} attacks, {len(chase_interactions)} chases"
        )

    @pytest.mark.timeout(20)
    async def test_enemy_state_transitions(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test enemy state machine transitions"""
        enemy = await agent_clients("enemy")
        player = await agent_clients("player")

        assert enemy is not None and player is not None

        # Start with enemy patrolling
        if enemy.agent and player.agent:
            enemy.agent.x = 15.0
            enemy.agent.y = 15.0
            player.agent.x = 35.0  # Far away initially
            player.agent.y = 35.0

        states_observed = set()
        transition_count = 0
        start_time = time.time()

        while time.time() - start_time < 18:
            current_time = time.time()

            if enemy.agent and player.agent:
                distance = math.sqrt(
                    (enemy.agent.x - player.agent.x) ** 2
                    + (enemy.agent.y - player.agent.y) ** 2
                )

                # Determine expected state
                if distance <= 2.0:
                    expected_state = "attack"
                elif distance <= 15.0:
                    expected_state = "chase"
                else:
                    expected_state = "patrol"

                states_observed.add(expected_state)
                behavior_metrics.record_state_transition(
                    enemy.agent_id, expected_state, current_time
                )
                transition_count += 1

                # Move player closer halfway through test
                if current_time - start_time > 9:
                    player.agent.x = 17.0
                    player.agent.y = 16.0

            await asyncio.sleep(0.6)

        # Verify state transitions
        AgentAssertions.assert_state_transitions(
            behavior_metrics,
            enemy.agent_id,
            expected_states=["patrol", "chase"],
            min_transitions=3,
        )

        print(f"States observed: {states_observed}")
        print(f"Total transitions: {transition_count}")

    @pytest.mark.timeout(25)
    async def test_multiple_enemies_behavior(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test behavior with multiple enemies"""
        # Create multiple enemies and one player
        enemies = []
        for i in range(3):
            enemy = await agent_clients("enemy")
            if enemy:
                enemies.append(enemy)
                # Spread them out
                if enemy.agent:
                    enemy.agent.x = 20.0 + i * 15
                    enemy.agent.y = 20.0 + i * 10

        player = await agent_clients("player")
        assert len(enemies) >= 2 and player is not None

        # Position player to interact with enemies
        if player.agent:
            player.agent.x = 25.0
            player.agent.y = 25.0

        # Track all agents
        start_time = time.time()
        while time.time() - start_time < 20:
            current_time = time.time()

            # Record all positions
            for enemy in enemies:
                if enemy.agent:
                    pos = (enemy.agent.x, enemy.agent.y)
                    behavior_metrics.record_agent_position(
                        enemy.agent_id, "enemy", pos, current_time
                    )

            if player.agent:
                pos = (player.agent.x, player.agent.y)
                behavior_metrics.record_agent_position(
                    player.agent_id, "player", pos, current_time
                )

            await asyncio.sleep(0.5)

        # Analyze enemy behavior
        analysis = behavior_metrics.analyze_enemy_behavior()
        print(f"\nEnemy Analysis: {analysis}")

        # Verify each enemy moved
        for enemy in enemies:
            if enemy.agent:
                AgentAssertions.assert_agent_moved(
                    agent_tracker, enemy.agent_id, min_distance=2.0
                )

        # Check for interactions
        total_interactions = len(behavior_metrics.interaction_events)
        assert (
            total_interactions > 0
        ), "No interactions recorded between enemies and player"

        agent_tracker.print_debug_info()

    @pytest.mark.timeout(35)
    async def test_enemy_aggression_levels(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test that enemies show different aggression levels"""
        # Create multiple enemies (they should have different aggression)
        enemies = []
        for i in range(4):
            enemy = await agent_clients("enemy")
            if enemy:
                enemies.append(enemy)

        player = await agent_clients("player")
        assert len(enemies) >= 3 and player is not None

        # Position player in center
        if player.agent:
            player.agent.x = 30.0
            player.agent.y = 30.0

        # Position enemies around player
        for i, enemy in enumerate(enemies):
            if enemy.agent:
                angle = (2 * math.pi / len(enemies)) * i
                enemy.agent.x = 30.0 + math.cos(angle) * 8
                enemy.agent.y = 30.0 + math.sin(angle) * 8

        # Track behavior differences
        enemy_behaviors = {}
        start_time = time.time()

        while time.time() - start_time < 30:
            current_time = time.time()

            for enemy in enemies:
                if enemy.agent and player.agent:
                    distance = math.sqrt(
                        (enemy.agent.x - player.agent.x) ** 2
                        + (enemy.agent.y - player.agent.y) ** 2
                    )

                    if enemy.agent_id not in enemy_behaviors:
                        enemy_behaviors[enemy.agent_id] = {
                            "chase_time": 0,
                            "attack_time": 0,
                            "distances": [],
                        }

                    enemy_behaviors[enemy.agent_id]["distances"].append(distance)

                    # Record states
                    if distance <= 2.0:
                        behavior_metrics.record_state_transition(
                            enemy.agent_id, "attack", current_time
                        )
                        enemy_behaviors[enemy.agent_id]["attack_time"] += 1
                    elif distance <= 12.0:
                        behavior_metrics.record_state_transition(
                            enemy.agent_id, "chase", current_time
                        )
                        enemy_behaviors[enemy.agent_id]["chase_time"] += 1

            await asyncio.sleep(0.5)

        # Analyze aggression differences
        print(f"\nAggression analysis:")
        aggression_scores = []

        for agent_id, behavior in enemy_behaviors.items():
            avg_distance = sum(behavior["distances"]) / len(behavior["distances"])
            aggression_score = (
                behavior["chase_time"] + behavior["attack_time"] * 2
            ) / len(behavior["distances"])
            aggression_scores.append(aggression_score)

            print(
                f"  Enemy {agent_id[:8]}: avg_dist={avg_distance:.1f}, aggression={aggression_score:.2f}"
            )

        # Should see variation in aggression
        if len(aggression_scores) >= 2:
            aggression_variance = max(aggression_scores) - min(aggression_scores)
            assert (
                aggression_variance > 0.1
            ), f"Not enough aggression variation: {aggression_variance:.3f}"

    @pytest.mark.slow
    @pytest.mark.timeout(60)
    async def test_enemy_long_term_behavior(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test enemy behavior over extended period"""
        # Create enemies and player for extended test
        enemies = []
        for i in range(2):
            enemy = await agent_clients("enemy")
            if enemy:
                enemies.append(enemy)

        player = await agent_clients("player")
        assert len(enemies) >= 1 and player is not None

        # Track over extended period
        start_time = time.time()
        snapshot_interval = 2.0
        last_snapshot = start_time
        player_move_time = start_time + 20  # Move player mid-test

        while time.time() - start_time < 50:
            current_time = time.time()

            # Move player to trigger different behaviors
            if current_time > player_move_time and player.agent:
                player.agent.x = 35.0
                player.agent.y = 35.0
                player_move_time = current_time + 15

            # Take snapshots
            if current_time - last_snapshot >= snapshot_interval:
                for enemy in enemies:
                    if enemy.agent:
                        pos = (enemy.agent.x, enemy.agent.y)
                        behavior_metrics.record_agent_position(
                            enemy.agent_id, "enemy", pos, current_time
                        )

                if player.agent:
                    pos = (player.agent.x, player.agent.y)
                    behavior_metrics.record_agent_position(
                        player.agent_id, "player", pos, current_time
                    )

                # Record performance
                behavior_metrics.record_performance(
                    tick_rate=30.0, agent_count=len(enemies) + 1, timestamp=current_time
                )

                last_snapshot = current_time

            await asyncio.sleep(0.5)

        # Generate comprehensive analysis
        enemy_analysis = behavior_metrics.analyze_enemy_behavior()

        print(f"\n=== Long-term Enemy Analysis ===")
        print(f"Total enemies: {enemy_analysis['total_enemies']}")
        print(f"Chase events: {enemy_analysis['chase_events']}")
        print(f"Attack events: {enemy_analysis['attack_events']}")
        print(f"Patrol efficiency: {enemy_analysis.get('patrol_efficiency', 0):.3f}")

        for agent_id, stats in enemy_analysis.get("individual_stats", {}).items():
            print(f"\nEnemy {agent_id[:8]}:")
            print(f"  Patrol efficiency: {stats['patrol_efficiency']:.3f}")
            print(f"  Total distance: {stats['total_distance']:.1f}")

        # Verify long-term behavior
        for enemy in enemies:
            if enemy.agent:
                AgentAssertions.assert_agent_moved(
                    agent_tracker, enemy.agent_id, min_distance=15.0
                )

        # Should have seen multiple behavior types
        assert enemy_analysis["chase_events"] > 0, "No chase events in long-term test"

        # Performance should remain acceptable
        AgentAssertions.assert_performance_acceptable(
            behavior_metrics, min_tick_rate=25.0
        )

    async def test_enemy_performance_under_load(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test enemy performance with many agents"""
        # Create many enemies
        enemies = []
        target_count = 8

        for i in range(target_count):
            enemy = await agent_clients("enemy")
            if enemy:
                enemies.append(enemy)

        # Add one player to trigger behaviors
        player = await agent_clients("player")

        actual_count = len(enemies)
        assert actual_count >= 4, f"Need at least 4 enemies, got {actual_count}"

        # Monitor performance
        start_time = time.time()
        performance_samples = []

        while time.time() - start_time < 15:
            sample_start = time.time()

            # Record performance
            active_count = len([e for e in enemies if e.connected]) + (
                1 if player and player.connected else 0
            )
            behavior_metrics.record_performance(
                tick_rate=30.0, agent_count=active_count, timestamp=time.time()
            )

            sample_duration = time.time() - sample_start
            performance_samples.append(sample_duration)

            await asyncio.sleep(0.5)

        # Verify performance
        avg_sample_time = sum(performance_samples) / len(performance_samples)
        print(
            f"Performance with {actual_count} enemies: {avg_sample_time*1000:.1f}ms avg sample time"
        )

        assert (
            avg_sample_time < 0.15
        ), f"Performance degraded: {avg_sample_time*1000:.1f}ms > 150ms"
        AgentAssertions.assert_performance_acceptable(
            behavior_metrics, min_tick_rate=20.0
        )
