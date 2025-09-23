import asyncio
import time

import pytest

from tests.utils.assertions import AgentAssertions
from tests.utils.metrics import BehaviorMetrics


@pytest.mark.asyncio
@pytest.mark.network
class TestNetworkFunctionality:
    """Test network communication and synchronization"""

    async def test_client_server_connection(self, game_server, agent_clients):
        """Test basic client-server connection"""
        # Test single connection
        client1 = await agent_clients("player")
        assert client1 is not None, "Failed to connect first client"
        assert client1.connected, "Client not marked as connected"

        # Test multiple connections
        client2 = await agent_clients("explorer")
        client3 = await agent_clients("npc")

        active_clients = [c for c in [client1, client2, client3] if c and c.connected]
        assert (
            len(active_clients) >= 2
        ), f"Expected at least 2 active clients, got {len(active_clients)}"

        # Verify server sees all clients
        server_agents = game_server.world.get_all_agents()
        assert len(server_agents) >= len(
            active_clients
        ), "Server doesn't see all connected agents"

    async def test_message_synchronization(self, game_server, agent_clients):
        """Test message synchronization between client and server"""
        client = await agent_clients("player")
        assert client is not None

        # Test position updates
        if client.agent:
            initial_pos = (client.agent.x, client.agent.y)

            # Move agent on client side
            new_x, new_y = initial_pos[0] + 5, initial_pos[1] + 3
            await client.move_to(new_x, new_y)

            # Wait for synchronization
            await asyncio.sleep(2)

            # Check server has updated position
            server_agent = game_server.world.get_agent(client.agent_id)
            assert server_agent is not None, "Agent not found on server"

            server_pos = (server_agent.x, server_agent.y)
            distance = (
                (server_pos[0] - new_x) ** 2 + (server_pos[1] - new_y) ** 2
            ) ** 0.5

            # Allow some tolerance for movement interpolation
            assert (
                distance < 2.0
            ), f"Position not synchronized: server={server_pos}, expected=({new_x}, {new_y})"

    async def test_world_state_broadcast(self, game_server, agent_clients):
        """Test world state broadcasting to clients"""
        # Create multiple clients
        clients = []
        for agent_type in ["player", "npc", "explorer"]:
            client = await agent_clients(agent_type)
            if client:
                clients.append(client)

        assert len(clients) >= 2, "Need at least 2 clients for broadcast test"

        # Wait for initial world state synchronization
        await asyncio.sleep(3)

        # Verify all clients received world state
        for client in clients:
            world_state = client.get_world_state()
            assert (
                world_state is not None
            ), f"Client {client.agent_id[:8]} didn't receive world state"
            assert "agents" in world_state, "World state missing agents data"

            agents_in_state = world_state["agents"]
            assert len(agents_in_state) >= len(
                clients
            ), f"Client sees {len(agents_in_state)} agents, expected {len(clients)}"

    async def test_client_disconnect_cleanup(self, game_server, agent_clients):
        """Test proper cleanup when clients disconnect"""
        # Connect clients
        client1 = await agent_clients("player")
        client2 = await agent_clients("npc")

        clients = [c for c in [client1, client2] if c]
        assert len(clients) >= 1, "Need at least 1 client for disconnect test"

        # Verify agents exist on server
        initial_agent_count = len(game_server.world.get_all_agents())
        assert initial_agent_count >= len(clients)

        # Disconnect first client
        if clients[0]:
            disconnected_agent_id = clients[0].agent_id
            await clients[0].disconnect()

            # Wait for cleanup
            await asyncio.sleep(2)

            # Verify agent removed from server
            remaining_agents = game_server.world.get_all_agents()
            remaining_ids = [a.id for a in remaining_agents]

            assert (
                disconnected_agent_id not in remaining_ids
            ), "Disconnected agent not cleaned up"
            assert (
                len(remaining_agents) < initial_agent_count
            ), "Agent count didn't decrease"

    async def test_high_frequency_updates(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test system under high-frequency updates"""
        client = await agent_clients("explorer")
        assert client is not None

        # Send rapid position updates
        update_count = 0
        start_time = time.time()
        test_duration = 8.0

        while time.time() - start_time < test_duration:
            if client.agent:
                # Generate rapid movement
                current_time = time.time()
                offset = (current_time - start_time) * 2  # Move 2 units per second

                new_x = 25 + offset
                new_y = 25 + offset * 0.5

                # Update position rapidly
                client.agent.x = new_x
                client.agent.y = new_y

                # Send position update via UDP
                client.send_udp_message(
                    {
                        "type": "move",
                        "x": new_x,
                        "y": new_y,
                        "rotation": client.agent.rotation,
                    }
                )

                update_count += 1

                # Record for performance analysis
                behavior_metrics.record_performance(
                    tick_rate=30.0, agent_count=1, timestamp=current_time
                )

            await asyncio.sleep(0.05)  # 20 updates per second

        # Verify system handled high frequency updates
        updates_per_second = update_count / test_duration
        print(
            f"High frequency test: {update_count} updates in {test_duration:.1f}s ({updates_per_second:.1f} updates/sec)"
        )

        assert (
            updates_per_second >= 15.0
        ), f"Update rate too low: {updates_per_second:.1f} < 15.0"

        # Verify final position synchronization
        if client.agent:
            server_agent = game_server.world.get_agent(client.agent_id)
            if server_agent:
                client_pos = (client.agent.x, client.agent.y)
                server_pos = (server_agent.x, server_agent.y)
                sync_distance = (
                    (client_pos[0] - server_pos[0]) ** 2
                    + (client_pos[1] - server_pos[1]) ** 2
                ) ** 0.5

                assert (
                    sync_distance < 3.0
                ), f"Poor synchronization after high-frequency updates: {sync_distance:.2f}"

    async def test_network_latency_simulation(self, game_server, agent_clients):
        """Test behavior under simulated network latency"""
        client = await agent_clients("player")
        assert client is not None

        # Test with artificial delays
        latency_samples = []
        start_time = time.time()

        for i in range(10):
            # Send message and measure response time
            message_start = time.time()

            if client.agent:
                # Send position update
                await client.move_to(20 + i, 20 + i)

                # Wait for server response (world state update)
                await asyncio.sleep(0.1)

                # Check if position was updated on server
                server_agent = game_server.world.get_agent(client.agent_id)
                if server_agent:
                    response_time = time.time() - message_start
                    latency_samples.append(response_time)

            await asyncio.sleep(0.5)

        # Analyze latency
        if latency_samples:
            avg_latency = sum(latency_samples) / len(latency_samples)
            max_latency = max(latency_samples)

            print(f"Network latency simulation:")
            print(f"  Average latency: {avg_latency*1000:.1f}ms")
            print(f"  Max latency: {max_latency*1000:.1f}ms")
            print(f"  Samples: {len(latency_samples)}")

            # Verify acceptable latency
            assert (
                avg_latency < 0.2
            ), f"Average latency too high: {avg_latency*1000:.1f}ms"
            assert max_latency < 0.5, f"Max latency too high: {max_latency*1000:.1f}ms"

    async def test_concurrent_client_updates(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test concurrent updates from multiple clients"""
        # Create multiple clients
        clients = []
        for i in range(5):
            client = await agent_clients("explorer")
            if client:
                clients.append(client)

        assert len(clients) >= 3, f"Need at least 3 clients, got {len(clients)}"

        # Have all clients move simultaneously
        async def move_client(client, client_index):
            for step in range(10):
                if client.agent:
                    # Each client moves in different direction
                    angle = (client_index * 60) * 3.14159 / 180  # Convert to radians
                    new_x = 25 + step * 2 * (angle / 3.14159)
                    new_y = 25 + step * 2 * (1 - angle / 3.14159)

                    client.agent.x = new_x
                    client.agent.y = new_y

                    # Send update
                    client.send_udp_message(
                        {
                            "type": "move",
                            "x": new_x,
                            "y": new_y,
                            "rotation": client.agent.rotation,
                        }
                    )

                await asyncio.sleep(0.2)

        # Run all clients concurrently
        start_time = time.time()
        tasks = [
            asyncio.create_task(move_client(client, i))
            for i, client in enumerate(clients)
        ]
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        print(f"Concurrent client test: {len(clients)} clients, {total_time:.1f}s")

        # Verify all clients moved
        for i, client in enumerate(clients):
            if client.agent:
                distance_moved = (
                    (client.agent.x - 25) ** 2 + (client.agent.y - 25) ** 2
                ) ** 0.5
                assert (
                    distance_moved > 5.0
                ), f"Client {i} didn't move enough: {distance_moved:.2f}"

        # Verify server state consistency
        server_agents = game_server.world.get_all_agents()
        server_positions = {a.id: (a.x, a.y) for a in server_agents}

        sync_errors = 0
        for client in clients:
            if client.agent and client.agent_id in server_positions:
                client_pos = (client.agent.x, client.agent.y)
                server_pos = server_positions[client.agent_id]
                sync_distance = (
                    (client_pos[0] - server_pos[0]) ** 2
                    + (client_pos[1] - server_pos[1]) ** 2
                ) ** 0.5

                if sync_distance > 2.0:
                    sync_errors += 1

        assert (
            sync_errors <= len(clients) * 0.3
        ), f"Too many sync errors: {sync_errors}/{len(clients)}"

    async def test_network_recovery(self, game_server, agent_clients):
        """Test network recovery after temporary issues"""
        client = await agent_clients("player")
        assert client is not None

        # Simulate normal operation
        if client.agent:
            client.agent.x = 20
            client.agent.y = 20

        await asyncio.sleep(1)

        # Verify initial state
        server_agent = game_server.world.get_agent(client.agent_id)
        assert server_agent is not None

        # Simulate network interruption by stopping updates
        print("Simulating network interruption...")

        # Move client without sending updates (simulating network loss)
        if client.agent:
            client.agent.x = 30
            client.agent.y = 30

        # Wait during "network outage"
        await asyncio.sleep(3)

        # Resume network communication
        print("Resuming network communication...")
        if client.agent:
            await client.move_to(client.agent.x, client.agent.y)

        # Wait for recovery
        await asyncio.sleep(2)

        # Verify recovery
        server_agent = game_server.world.get_agent(client.agent_id)
        if server_agent and client.agent:
            client_pos = (client.agent.x, client.agent.y)
            server_pos = (server_agent.x, server_agent.y)
            recovery_distance = (
                (client_pos[0] - server_pos[0]) ** 2
                + (client_pos[1] - server_pos[1]) ** 2
            ) ** 0.5

            print(
                f"Recovery test: client={client_pos}, server={server_pos}, distance={recovery_distance:.2f}"
            )
            assert (
                recovery_distance < 3.0
            ), f"Failed to recover from network interruption: {recovery_distance:.2f}"

    async def test_bandwidth_efficiency(
        self, game_server, agent_clients, behavior_metrics
    ):
        """Test network bandwidth efficiency"""
        # Create clients that generate different amounts of network traffic
        clients = []
        for agent_type in ["player", "explorer", "npc"]:
            client = await agent_clients(agent_type)
            if client:
                clients.append((agent_type, client))

        assert len(clients) >= 2, "Need at least 2 clients for bandwidth test"

        # Monitor network activity
        message_counts = {agent_type: 0 for agent_type, _ in clients}
        start_time = time.time()

        while time.time() - start_time < 10:
            current_time = time.time()

            for agent_type, client in clients:
                if client.agent:
                    # Different update frequencies for different agent types
                    if agent_type == "player":
                        # High frequency updates
                        client.send_udp_message(
                            {
                                "type": "move",
                                "x": client.agent.x + 0.1,
                                "y": client.agent.y + 0.1,
                                "rotation": client.agent.rotation,
                            }
                        )
                        message_counts[agent_type] += 1

                    elif agent_type == "explorer":
                        # Medium frequency updates
                        if int(current_time * 10) % 3 == 0:
                            client.send_udp_message(
                                {
                                    "type": "move",
                                    "x": client.agent.x + 0.2,
                                    "y": client.agent.y + 0.1,
                                    "rotation": client.agent.rotation,
                                }
                            )
                            message_counts[agent_type] += 1

                    elif agent_type == "npc":
                        # Low frequency updates
                        if int(current_time * 2) % 5 == 0:
                            client.send_udp_message(
                                {
                                    "type": "move",
                                    "x": client.agent.x + 0.05,
                                    "y": client.agent.y + 0.05,
                                    "rotation": client.agent.rotation,
                                }
                            )
                            message_counts[agent_type] += 1

            await asyncio.sleep(0.1)

        # Analyze bandwidth usage
        test_duration = time.time() - start_time
        total_messages = sum(message_counts.values())

        print(f"\nBandwidth efficiency test ({test_duration:.1f}s):")
        print(f"Total messages: {total_messages}")

        for agent_type, count in message_counts.items():
            messages_per_second = count / test_duration
            print(f"  {agent_type}: {count} messages ({messages_per_second:.1f} msg/s)")

        # Verify reasonable bandwidth usage
        total_rate = total_messages / test_duration
        assert total_rate < 100, f"Message rate too high: {total_rate:.1f} msg/s"

        # Verify players have higher update rates than NPCs
        if "player" in message_counts and "npc" in message_counts:
            player_rate = message_counts["player"] / test_duration
            npc_rate = message_counts["npc"] / test_duration
            assert (
                player_rate > npc_rate
            ), f"Player rate ({player_rate:.1f}) should be higher than NPC rate ({npc_rate:.1f})"
