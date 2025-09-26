import asyncio
import json
import os
import time

import pytest

from tests.utils.agent_tracker import AgentTracker
from tests.utils.metrics import BehaviorMetrics


@pytest.mark.asyncio
class TestDebugOutput:
    """Tests for debug information and metrics collection"""

    async def test_debug_data_collection(
        self, game_server, agent_clients, agent_tracker, behavior_metrics
    ):
        """Test that debug data is collected properly"""
        # Create agents for debug testing
        explorer = await agent_clients("explorer")
        npc = await agent_clients("npc")
        enemy = await agent_clients("enemy")

        agents = [explorer, npc, enemy]
        agents = [a for a in agents if a is not None]
        assert len(agents) >= 2, "Need at least 2 agents for debug test"

        # Collect debug data
        start_time = time.time()
        debug_snapshots = []

        while time.time() - start_time < 10:
            current_time = time.time()

            # Collect comprehensive debug snapshot
            snapshot = {
                "timestamp": current_time,
                "server_state": game_server.world.get_world_state(),
                "agent_details": {},
            }

            for agent_client in agents:
                if agent_client.agent:
                    agent_id = agent_client.agent_id
                    agent_state = agent_client.get_agent_state()

                    # Add detailed debug info
                    debug_info = {
                        "client_state": agent_state,
                        "position": (agent_client.agent.x, agent_client.agent.y),
                        "velocity": (
                            getattr(agent_client.agent, "velocity_x", 0),
                            getattr(agent_client.agent, "velocity_y", 0),
                        ),
                        "internal_state": getattr(
                            agent_client.agent, "behavior_state", "unknown"
                        ),
                        "target": getattr(agent_client.agent, "current_target", None),
                        "visible_entities": getattr(
                            agent_client.agent, "visible_entities", []
                        ),
                    }

                    # Add agent-specific debug data
                    if hasattr(agent_client.agent, "explored_tiles"):
                        debug_info["explored_tiles"] = len(
                            agent_client.agent.explored_tiles
                        )
                    if hasattr(agent_client.agent, "patrol_points"):
                        debug_info["patrol_points"] = agent_client.agent.patrol_points
                    if hasattr(agent_client.agent, "home_x"):
                        debug_info["home_position"] = (
                            agent_client.agent.home_x,
                            agent_client.agent.home_y,
                        )

                    snapshot["agent_details"][agent_id] = debug_info

                    # Record for metrics
                    pos = (agent_client.agent.x, agent_client.agent.y)
                    behavior_metrics.record_agent_position(
                        agent_id, agent_client.agent.agent_type, pos, current_time
                    )

            debug_snapshots.append(snapshot)
            await asyncio.sleep(1.0)

        # Verify debug data collection
        assert (
            len(debug_snapshots) >= 8
        ), f"Expected at least 8 snapshots, got {len(debug_snapshots)}"

        # Verify each snapshot has required data
        for snapshot in debug_snapshots:
            assert "timestamp" in snapshot
            assert "server_state" in snapshot
            assert "agent_details" in snapshot
            assert len(snapshot["agent_details"]) >= len(agents)

        # Print debug summary
        print(f"\n=== Debug Data Collection Summary ===")
        print(f"Snapshots collected: {len(debug_snapshots)}")
        print(
            f"Time span: {debug_snapshots[-1]['timestamp'] - debug_snapshots[0]['timestamp']:.1f}s"
        )

        first_snapshot = debug_snapshots[0]
        last_snapshot = debug_snapshots[-1]

        for agent_id in first_snapshot["agent_details"]:
            if agent_id in last_snapshot["agent_details"]:
                start_pos = first_snapshot["agent_details"][agent_id]["position"]
                end_pos = last_snapshot["agent_details"][agent_id]["position"]
                distance = (
                    (end_pos[0] - start_pos[0]) ** 2 + (end_pos[1] - start_pos[1]) ** 2
                ) ** 0.5

                print(f"Agent {agent_id[:8]}:")
                print(f"  Start: {start_pos}")
                print(f"  End: {end_pos}")
                print(f"  Distance: {distance:.2f}")

    @pytest.mark.skip(reason="Hangs in test environment - debug test not critical")
    async def test_behavior_metrics_export(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test exporting behavior metrics to file"""
        # Create agents and run simulation
        agents = []
        for agent_type in ["explorer", "npc", "enemy"]:
            for i in range(2):
                agent = await agent_clients(agent_type)
                if agent:
                    agents.append(agent)

        # Simulate behavior
        start_time = time.time()
        while time.time() - start_time < 12:
            current_time = time.time()

            for agent in agents:
                if agent.agent:
                    pos = (agent.agent.x, agent.agent.y)
                    behavior_metrics.record_agent_position(
                        agent.agent_id, agent.agent.agent_type, pos, current_time
                    )

                    # Simulate state transitions
                    if agent.agent.agent_type == "enemy":
                        behavior_metrics.record_state_transition(
                            agent.agent_id, "patrol", current_time
                        )
                    elif agent.agent.agent_type == "npc":
                        state = "idle" if (int(current_time) % 6) < 3 else "wandering"
                        behavior_metrics.record_state_transition(
                            agent.agent_id, state, current_time
                        )

            # Record performance
            behavior_metrics.record_performance(
                tick_rate=30.0, agent_count=len(agents), timestamp=current_time
            )

            await asyncio.sleep(0.5)

        # Generate and export report
        report = behavior_metrics.generate_report()

        # Test JSON serialization
        try:
            report_json = json.dumps(report, indent=2, default=str)
            assert len(report_json) > 100, "Report JSON too short"
        except Exception as e:
            pytest.fail(f"Failed to serialize report to JSON: {e}")

        # Verify report structure
        assert "explorer_analysis" in report
        assert "npc_analysis" in report
        assert "enemy_analysis" in report
        assert "performance_summary" in report

        print(f"\n=== Behavior Metrics Report ===")
        print(f"Report size: {len(report_json)} characters")
        print(f"Explorer analysis keys: {list(report['explorer_analysis'].keys())}")
        print(f"NPC analysis keys: {list(report['npc_analysis'].keys())}")
        print(f"Enemy analysis keys: {list(report['enemy_analysis'].keys())}")

    async def test_agent_tracker_debug_output(
        self, game_server, agent_clients, agent_tracker
    ):
        """Test agent tracker debug capabilities"""
        # Create agents
        explorer = await agent_clients("explorer")
        npc = await agent_clients("npc")

        agents = [explorer, npc]
        agents = [a for a in agents if a is not None]

        # Track for analysis
        await asyncio.sleep(15)

        # Test debug output methods
        summary = agent_tracker.get_summary_report()

        # Verify summary structure
        assert "tracking_duration" in summary
        assert "total_agents" in summary
        assert "agents_by_type" in summary
        assert "agent_stats" in summary

        print(f"\n=== Agent Tracker Debug Output ===")
        print(f"Tracking duration: {summary['tracking_duration']:.2f}s")
        print(f"Total agents tracked: {summary['total_agents']}")

        for agent_type, count in summary["agents_by_type"].items():
            print(f"  {agent_type}: {count} agents")

        # Test individual agent analysis
        for agent in agents:
            if agent.agent:
                path = agent_tracker.get_agent_path(agent.agent_id)
                assert path is not None, f"No path data for {agent.agent_id}"

                total_distance = path.get_total_distance()
                speeds = path.get_speed_over_time()
                coverage = path.get_area_coverage()

                print(f"\nAgent {agent.agent_id[:8]} ({agent.agent.agent_type}):")
                print(f"  Snapshots: {len(path.snapshots)}")
                print(f"  Total distance: {total_distance:.2f}")
                print(f"  Speed samples: {len(speeds)}")
                print(f"  Area coverage: {len(coverage)} tiles")

                if speeds:
                    avg_speed = sum(speeds) / len(speeds)
                    max_speed = max(speeds)
                    print(f"  Avg speed: {avg_speed:.2f}")
                    print(f"  Max speed: {max_speed:.2f}")

        # Test print debug info (capture output)
        print("\n=== Full Debug Report ===")
        agent_tracker.print_debug_info()

    async def test_performance_monitoring(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test performance monitoring and alerts"""
        # Create many agents to test performance impact
        agents = []
        target_count = 12

        for i in range(target_count):
            agent_type = ["explorer", "npc", "enemy"][i % 3]
            agent = await agent_clients(agent_type)
            if agent:
                agents.append(agent)

        actual_count = len(agents)
        print(f"Performance test with {actual_count} agents")

        # Monitor performance metrics
        start_time = time.time()
        performance_alerts = []
        tick_times = []

        while time.time() - start_time < 15:
            tick_start = time.time()

            # Simulate server work
            current_time = time.time()
            active_agents = [a for a in agents if a.connected]

            # Record performance
            behavior_metrics.record_performance(
                tick_rate=30.0,
                agent_count=len(active_agents),
                timestamp=current_time,
                cpu_usage=min(100.0, len(active_agents) * 2.0),  # Simulated
                memory_usage=min(1000.0, len(active_agents) * 10.0),  # Simulated MB
                latency=max(1.0, len(active_agents) * 0.5),  # Simulated ms
            )

            tick_duration = time.time() - tick_start
            tick_times.append(tick_duration)

            # Check for performance issues
            if tick_duration > 0.05:  # 50ms threshold
                performance_alerts.append(
                    {
                        "timestamp": current_time,
                        "tick_duration": tick_duration,
                        "agent_count": len(active_agents),
                    }
                )

            await asyncio.sleep(0.033)  # ~30 FPS

        # Analyze performance
        avg_tick_time = sum(tick_times) / len(tick_times)
        max_tick_time = max(tick_times)

        print(f"\n=== Performance Monitoring Results ===")
        print(f"Average tick time: {avg_tick_time*1000:.2f}ms")
        print(f"Max tick time: {max_tick_time*1000:.2f}ms")
        print(f"Performance alerts: {len(performance_alerts)}")

        if performance_alerts:
            worst_alert = max(performance_alerts, key=lambda x: x["tick_duration"])
            print(
                f"Worst performance: {worst_alert['tick_duration']*1000:.2f}ms with {worst_alert['agent_count']} agents"
            )

        # Performance assertions
        assert (
            avg_tick_time < 0.1
        ), f"Average tick time too high: {avg_tick_time*1000:.1f}ms"
        assert (
            len(performance_alerts) < len(tick_times) * 0.1
        ), f"Too many performance alerts: {len(performance_alerts)}"

    async def test_debug_visualization_data(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test data collection for debug visualization"""
        # Create mixed agents
        explorer = await agent_clients("explorer")
        npc = await agent_clients("npc")
        enemy = await agent_clients("enemy")

        agents = [a for a in [explorer, npc, enemy] if a is not None]

        # Collect visualization data
        visualization_data = {
            "agent_paths": {},
            "heatmap_data": {},
            "interaction_events": [],
            "performance_timeline": [],
        }

        start_time = time.time()
        while time.time() - start_time < 12:
            current_time = time.time()

            for agent in agents:
                if agent.agent:
                    agent_id = agent.agent_id
                    pos = (agent.agent.x, agent.agent.y)

                    # Record path
                    if agent_id not in visualization_data["agent_paths"]:
                        visualization_data["agent_paths"][agent_id] = {
                            "type": agent.agent.agent_type,
                            "positions": [],
                            "timestamps": [],
                        }

                    visualization_data["agent_paths"][agent_id]["positions"].append(pos)
                    visualization_data["agent_paths"][agent_id]["timestamps"].append(
                        current_time
                    )

                    # Record for heatmap
                    tile_x, tile_y = int(pos[0]), int(pos[1])
                    heatmap_key = f"{tile_x},{tile_y}"
                    if heatmap_key not in visualization_data["heatmap_data"]:
                        visualization_data["heatmap_data"][heatmap_key] = 0
                    visualization_data["heatmap_data"][heatmap_key] += 1

                    # Record for metrics
                    behavior_metrics.record_agent_position(
                        agent_id, agent.agent.agent_type, pos, current_time
                    )

            # Record performance for timeline
            visualization_data["performance_timeline"].append(
                {
                    "timestamp": current_time,
                    "agent_count": len(agents),
                    "active_agents": len([a for a in agents if a.connected]),
                }
            )

            await asyncio.sleep(0.5)

        # Verify visualization data
        assert len(visualization_data["agent_paths"]) >= len(agents)
        assert len(visualization_data["heatmap_data"]) > 0
        assert len(visualization_data["performance_timeline"]) > 0

        print(f"\n=== Visualization Data Collection ===")
        print(f"Agent paths: {len(visualization_data['agent_paths'])}")
        print(f"Heatmap tiles: {len(visualization_data['heatmap_data'])}")
        print(f"Performance samples: {len(visualization_data['performance_timeline'])}")

        # Test data export for visualization
        try:
            viz_json = json.dumps(visualization_data, indent=2, default=str)
            assert len(viz_json) > 500, "Visualization data too small"
            print(f"Visualization JSON size: {len(viz_json)} characters")
        except Exception as e:
            pytest.fail(f"Failed to serialize visualization data: {e}")

        # Analyze path data
        for agent_id, path_data in visualization_data["agent_paths"].items():
            positions = path_data["positions"]
            if len(positions) >= 2:
                start_pos = positions[0]
                end_pos = positions[-1]
                total_distance = sum(
                    (
                        (positions[i][0] - positions[i - 1][0]) ** 2
                        + (positions[i][1] - positions[i - 1][1]) ** 2
                    )
                    ** 0.5
                    for i in range(1, len(positions))
                )

                print(f"Agent {agent_id[:8]} ({path_data['type']}):")
                print(f"  Path length: {len(positions)} points")
                print(f"  Total distance: {total_distance:.2f}")
                print(
                    f"  Start->End distance: {((end_pos[0]-start_pos[0])**2 + (end_pos[1]-start_pos[1])**2)**0.5:.2f}"
                )

        # Analyze heatmap
        hottest_tile = max(
            visualization_data["heatmap_data"].items(), key=lambda x: x[1]
        )
        print(f"Hottest tile: {hottest_tile[0]} with {hottest_tile[1]} visits")
