"""
Load testing and performance benchmarks

These tests measure system performance under various load conditions
using lightweight mocks to avoid network overhead.
"""

import pytest
import asyncio
import time
import statistics
from typing import List, Dict
from dataclasses import dataclass

from tests.fixtures.mock_server import FastTestFixture
from tests.fixtures.test_maps import TestMaps
from shared.actions import ActionRequest, ActionType, move_to_params


@dataclass
class PerformanceMetrics:
    """Performance measurement results"""
    avg_response_time: float
    max_response_time: float
    min_response_time: float
    throughput: float  # actions per second
    success_rate: float
    total_actions: int
    test_duration: float

    def __str__(self):
        return (f"Performance: {self.throughput:.1f} actions/sec, "
                f"avg latency: {self.avg_response_time*1000:.1f}ms, "
                f"success rate: {self.success_rate*100:.1f}%")


class TestActionSystemPerformance:
    """Test action system under load"""

    @pytest.mark.asyncio
    async def test_single_agent_action_throughput(self):
        """Test maximum throughput for single agent"""
        fixture = FastTestFixture()
        client = await fixture.add_client("player", 10, 10)

        action_count = 50
        response_times = []
        successful_actions = 0

        start_time = time.time()

        for i in range(action_count):
            # Alternate between different action types to avoid cooldowns
            if i % 2 == 0:
                action_type = ActionType.MOVE_TO
                params = move_to_params(10 + (i % 5), 10)
            else:
                action_type = ActionType.QUERY_INVENTORY
                params = {}

            request = ActionRequest(
                action_id=f"perf_{i}",
                agent_id=client.agent_id,
                action_type=action_type,
                parameters=params
            )

            action_start = time.time()
            response = await fixture.server.action_processor.submit_action(request)
            action_end = time.time()

            response_times.append(action_end - action_start)
            if response.result.value in ["approved", "modified"]:
                successful_actions += 1

        total_time = time.time() - start_time

        metrics = PerformanceMetrics(
            avg_response_time=statistics.mean(response_times),
            max_response_time=max(response_times),
            min_response_time=min(response_times),
            throughput=action_count / total_time,
            success_rate=successful_actions / action_count,
            total_actions=action_count,
            test_duration=total_time
        )

        print(f"\nSingle agent throughput: {metrics}")

        # Performance assertions
        assert metrics.avg_response_time < 0.1, f"Average response time too high: {metrics.avg_response_time:.3f}s"
        assert metrics.throughput > 20, f"Throughput too low: {metrics.throughput:.1f} actions/sec"
        assert metrics.success_rate > 0.8, f"Success rate too low: {metrics.success_rate:.2%}"

    @pytest.mark.asyncio
    async def test_multi_agent_concurrent_actions(self):
        """Test concurrent actions from multiple agents"""
        fixture = FastTestFixture(30, 30)
        agent_count = 10

        # Create multiple agents
        clients = []
        for i in range(agent_count):
            client = await fixture.add_client("player", 15 + (i % 5), 15 + (i // 5))
            clients.append(client)

        actions_per_agent = 10
        total_actions = agent_count * actions_per_agent

        async def agent_workload(client, agent_index):
            """Workload for a single agent"""
            response_times = []
            successful = 0

            for action_index in range(actions_per_agent):
                request = ActionRequest(
                    action_id=f"agent_{agent_index}_action_{action_index}",
                    agent_id=client.agent_id,
                    action_type=ActionType.MOVE_TO,
                    parameters=move_to_params(
                        15 + (action_index % 10),
                        15 + (action_index % 10)
                    )
                )

                start = time.time()
                response = await fixture.server.action_processor.submit_action(request)
                end = time.time()

                response_times.append(end - start)
                if response.result.value in ["approved", "modified"]:
                    successful += 1

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.01)

            return response_times, successful

        # Run all agents concurrently
        start_time = time.time()
        tasks = [
            asyncio.create_task(agent_workload(client, i))
            for i, client in enumerate(clients)
        ]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Aggregate results
        all_response_times = []
        total_successful = 0

        for response_times, successful in results:
            all_response_times.extend(response_times)
            total_successful += successful

        metrics = PerformanceMetrics(
            avg_response_time=statistics.mean(all_response_times),
            max_response_time=max(all_response_times),
            min_response_time=min(all_response_times),
            throughput=total_actions / total_time,
            success_rate=total_successful / total_actions,
            total_actions=total_actions,
            test_duration=total_time
        )

        print(f"\nMulti-agent concurrent: {metrics}")

        # Performance assertions for concurrent load
        assert metrics.avg_response_time < 0.2, f"Concurrent avg response too high: {metrics.avg_response_time:.3f}s"
        assert metrics.throughput > 50, f"Concurrent throughput too low: {metrics.throughput:.1f} actions/sec"
        assert metrics.success_rate > 0.7, f"Concurrent success rate too low: {metrics.success_rate:.2%}"

    @pytest.mark.asyncio
    async def test_action_validation_performance(self):
        """Test performance of action validation under load"""
        fixture = FastTestFixture()
        client = await fixture.add_client("player", 10, 10)

        # Test different types of validation scenarios
        test_cases = [
            ("valid_move", ActionType.MOVE_TO, move_to_params(15, 15)),
            ("invalid_bounds", ActionType.MOVE_TO, move_to_params(50, 50)),
            ("inventory_query", ActionType.QUERY_INVENTORY, {}),
        ]

        validation_times = {}

        for case_name, action_type, params in test_cases:
            times = []

            for i in range(20):  # Multiple runs for each case
                request = ActionRequest(
                    action_id=f"{case_name}_{i}",
                    agent_id=client.agent_id,
                    action_type=action_type,
                    parameters=params
                )

                start = time.time()
                response = await fixture.server.action_processor.submit_action(request)
                end = time.time()

                times.append(end - start)

            validation_times[case_name] = {
                'avg': statistics.mean(times),
                'max': max(times),
                'min': min(times)
            }

        print(f"\nValidation performance:")
        for case, metrics in validation_times.items():
            print(f"  {case}: avg={metrics['avg']*1000:.2f}ms, max={metrics['max']*1000:.2f}ms")

        # All validation should be very fast
        for case, metrics in validation_times.items():
            assert metrics['avg'] < 0.05, f"{case} validation too slow: {metrics['avg']:.3f}s"
            assert metrics['max'] < 0.1, f"{case} max validation too slow: {metrics['max']:.3f}s"

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self):
        """Test that memory usage remains stable under load"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        fixture = FastTestFixture()
        client = await fixture.add_client("player", 10, 10)

        # Generate sustained load
        for batch in range(5):  # 5 batches
            tasks = []
            for i in range(20):  # 20 actions per batch
                request = ActionRequest(
                    action_id=f"memory_test_{batch}_{i}",
                    agent_id=client.agent_id,
                    action_type=ActionType.MOVE_TO,
                    parameters=move_to_params(10 + (i % 8), 10 + (i % 8))
                )
                task = asyncio.create_task(
                    fixture.server.action_processor.submit_action(request)
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Check memory after each batch
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = current_memory - initial_memory

            print(f"Batch {batch}: Memory usage = {current_memory:.1f}MB (growth: +{memory_growth:.1f}MB)")

            # Small delay to allow garbage collection
            await asyncio.sleep(0.1)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_growth = final_memory - initial_memory

        print(f"\nMemory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB (growth: +{total_growth:.1f}MB)")

        # Memory growth should be reasonable
        assert total_growth < 50, f"Excessive memory growth: {total_growth:.1f}MB"

    @pytest.mark.asyncio
    async def test_rate_limiting_performance(self):
        """Test performance of rate limiting under burst load"""
        fixture = FastTestFixture()
        client = await fixture.add_client("player", 10, 10)

        # Create burst of actions to trigger rate limiting
        burst_size = 50
        response_times = []
        rate_limited_count = 0

        start_time = time.time()

        for i in range(burst_size):
            request = ActionRequest(
                action_id=f"burst_{i}",
                agent_id=client.agent_id,
                action_type=ActionType.MOVE_TO,
                parameters=move_to_params(10 + (i % 3), 10)
            )

            action_start = time.time()
            response = await fixture.server.action_processor.submit_action(request)
            action_end = time.time()

            response_times.append(action_end - action_start)

            if "rate limit" in response.message.lower():
                rate_limited_count += 1

        total_time = time.time() - start_time
        avg_response_time = statistics.mean(response_times)

        print(f"\nRate limiting test:")
        print(f"  Total actions: {burst_size}")
        print(f"  Rate limited: {rate_limited_count}")
        print(f"  Avg response time: {avg_response_time*1000:.2f}ms")
        print(f"  Total time: {total_time:.2f}s")

        # Rate limiting should be fast and effective
        assert avg_response_time < 0.015, f"Rate limiting adds too much latency: {avg_response_time:.3f}s"
        # Note: Rate limiting may not trigger in mock environment
        if rate_limited_count > 0:
            assert rate_limited_count < burst_size, "Rate limiting shouldn't block everything"

    @pytest.mark.asyncio
    async def test_complex_scenario_performance(self):
        """Test performance with complex multi-agent scenario"""
        fixture = FastTestFixture(50, 50)

        # Use complex terrain
        terrain = TestMaps.get_multi_room_dungeon(40, 30)
        fixture.set_terrain(terrain)

        # Create agents of different types
        agent_types = ["player", "explorer", "enemy"] * 3  # 9 agents total
        clients = []

        for i, agent_type in enumerate(agent_types):
            # Spread agents across the map
            x = 5 + (i % 3) * 15
            y = 5 + (i // 3) * 8
            client = await fixture.add_client(agent_type, x, y)
            clients.append(client)

        async def complex_agent_behavior(client, duration=2.0):
            """Simulate complex agent behavior"""
            actions_completed = 0
            start_time = time.time()

            while time.time() - start_time < duration:
                # Mix of different actions
                action_choice = actions_completed % 4

                if action_choice == 0:
                    # Movement
                    target_x = client.agent.x + (-3 + (actions_completed % 7))
                    target_y = client.agent.y + (-2 + (actions_completed % 5))
                    request = ActionRequest(
                        action_id=f"complex_{client.agent_id}_{actions_completed}",
                        agent_id=client.agent_id,
                        action_type=ActionType.MOVE_TO,
                        parameters=move_to_params(target_x, target_y)
                    )
                elif action_choice == 1:
                    # Inventory query
                    request = ActionRequest(
                        action_id=f"complex_{client.agent_id}_{actions_completed}",
                        agent_id=client.agent_id,
                        action_type=ActionType.QUERY_INVENTORY,
                        parameters={}
                    )
                elif action_choice == 2:
                    # Stop movement
                    request = ActionRequest(
                        action_id=f"complex_{client.agent_id}_{actions_completed}",
                        agent_id=client.agent_id,
                        action_type=ActionType.STOP_MOVEMENT,
                        parameters={}
                    )
                else:
                    # Another movement
                    request = ActionRequest(
                        action_id=f"complex_{client.agent_id}_{actions_completed}",
                        agent_id=client.agent_id,
                        action_type=ActionType.MOVE_TO,
                        parameters=move_to_params(client.agent.x + 1, client.agent.y)
                    )

                await fixture.server.action_processor.submit_action(request)
                actions_completed += 1

                # Realistic delay between actions
                await asyncio.sleep(0.05)

            return actions_completed

        # Run complex scenario
        scenario_start = time.time()
        tasks = [
            asyncio.create_task(complex_agent_behavior(client))
            for client in clients
        ]
        results = await asyncio.gather(*tasks)
        scenario_time = time.time() - scenario_start

        total_actions = sum(results)
        throughput = total_actions / scenario_time

        print(f"\nComplex scenario performance:")
        print(f"  Agents: {len(clients)}")
        print(f"  Total actions: {total_actions}")
        print(f"  Duration: {scenario_time:.2f}s")
        print(f"  Throughput: {throughput:.1f} actions/sec")
        print(f"  Per-agent throughput: {throughput/len(clients):.1f} actions/sec")

        # Complex scenario should still perform reasonably
        assert throughput > 30, f"Complex scenario throughput too low: {throughput:.1f} actions/sec"
        assert scenario_time < 5.0, f"Complex scenario took too long: {scenario_time:.2f}s"

        # Get final stats
        stats = fixture.server.action_processor.get_stats()
        print(f"  Final processor stats: {stats['total_processed']} processed, "
              f"{stats['total_approved']} approved, {stats['total_rejected']} rejected")


class TestBehaviorTreePerformance:
    """Test behavior tree performance under load"""

    @pytest.mark.asyncio
    async def test_behavior_tree_update_performance(self):
        """Test behavior tree update performance"""
        fixture = FastTestFixture()

        # Create agents with behavior trees
        clients = []
        for i in range(5):
            client = await fixture.add_client("explorer", 10 + i*2, 10)
            clients.append(client)

        # Time behavior tree updates
        update_times = []
        update_count = 100

        for update_cycle in range(update_count):
            cycle_start = time.time()

            for client in clients:
                if client.agent and hasattr(client.agent, 'update'):
                    client.agent.update(0.1)  # 100ms delta

            cycle_end = time.time()
            update_times.append(cycle_end - cycle_start)

            # Small delay between cycles
            await asyncio.sleep(0.01)

        avg_update_time = statistics.mean(update_times)
        max_update_time = max(update_times)

        print(f"\nBehavior tree performance:")
        print(f"  Agents: {len(clients)}")
        print(f"  Updates: {update_count}")
        print(f"  Avg update time: {avg_update_time*1000:.2f}ms")
        print(f"  Max update time: {max_update_time*1000:.2f}ms")
        print(f"  Per-agent update time: {(avg_update_time/len(clients))*1000:.2f}ms")

        # Behavior tree updates should be fast
        assert avg_update_time < 0.01, f"Behavior tree updates too slow: {avg_update_time:.4f}s"
        assert max_update_time < 0.05, f"Worst-case update too slow: {max_update_time:.4f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])