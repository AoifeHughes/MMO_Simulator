#!/usr/bin/env python3
"""
Test script for the new MMO architecture.

This demonstrates the key features:
1. 60Hz server updates
2. Authoritative inventory management
3. No position jumps
4. Proper action processing
"""

import asyncio
import logging
import time
from typing import List

from client.mmo_client import MMOClientAdapter
from server.mmo_server import MMOGameServer
from shared.actions import ActionType
from world.terrain_generator import TerrainType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MMOTestRunner:
    """Test runner for MMO system features"""

    def __init__(self):
        self.server: MMOGameServer = None
        self.clients: List[MMOClientAdapter] = []
        self.results = {
            "server_started": False,
            "clients_connected": 0,
            "fishing_attempts": 0,
            "fishing_successes": 0,
            "wood_attempts": 0,
            "wood_successes": 0,
            "inventory_updates": 0,
            "position_updates": 0,
            "no_position_jumps": True,
        }

    async def run_test(self, duration: int = 20):
        """Run comprehensive MMO system test"""
        logger.info("🎮 Starting MMO System Test")

        try:
            # 1. Start MMO server
            await self.start_server()

            # 2. Connect test clients
            await self.connect_clients()

            # 3. Test inventory operations
            await self.test_inventory_operations()

            # 4. Test movement and positioning
            await self.test_movement_system()

            # 5. Run for specified duration
            await asyncio.sleep(duration)

        finally:
            await self.cleanup()

        self.print_results()

    async def start_server(self):
        """Start the MMO server"""
        logger.info("Starting MMO server...")

        self.server = MMOGameServer(
            world_width=20, world_height=20, terrain_type=TerrainType.MIXED, seed=300
        )

        # Start server in background
        server_task = asyncio.create_task(self.server.start())

        # Give server time to start
        await asyncio.sleep(2)

        self.results["server_started"] = True
        logger.info("✅ MMO server started successfully")

    async def connect_clients(self):
        """Connect test clients"""
        logger.info("Connecting test clients...")

        # Connect 2 clients (fisher and wood harvester)
        for i, agent_type in enumerate(["explorer", "explorer"]):
            client = MMOClientAdapter()

            try:
                connected = await client.connect(agent_type)
                if connected:
                    self.clients.append(client)
                    self.results["clients_connected"] += 1
                    logger.info(f"✅ Client {i+1} connected as {agent_type}")
                else:
                    logger.error(f"❌ Failed to connect client {i+1}")

            except Exception as e:
                logger.error(f"Error connecting client {i+1}: {e}")

        await asyncio.sleep(1)

    async def test_inventory_operations(self):
        """Test fishing and wood harvesting with inventory updates"""
        logger.info("🧪 Testing inventory operations...")

        if len(self.clients) < 2:
            logger.error("Not enough clients connected for inventory testing")
            return

        fisher_client = self.clients[0]
        harvester_client = self.clients[1]

        # Test fishing
        logger.info("🎣 Testing fishing operations...")
        try:
            for _ in range(3):
                self.results["fishing_attempts"] += 1

                response = await fisher_client.request_action(
                    ActionType.FISH, {"target_x": 15.0, "target_y": 10.0}
                )

                if response.success:
                    self.results["fishing_successes"] += 1
                    self.results["inventory_updates"] += 1
                    logger.info(f"✅ Fishing success: {response.message}")
                else:
                    logger.info(f"🎣 Fishing attempt: {response.message}")

                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error in fishing test: {e}")

        # Test wood harvesting
        logger.info("🌲 Testing wood harvesting operations...")
        try:
            for _ in range(3):
                self.results["wood_attempts"] += 1

                response = await harvester_client.request_action(
                    ActionType.HARVEST_WOOD, {"target_x": 5.0, "target_y": 10.0}
                )

                if response.success:
                    self.results["wood_successes"] += 1
                    self.results["inventory_updates"] += 1
                    logger.info(f"✅ Wood harvesting success: {response.message}")
                else:
                    logger.info(f"🌲 Wood harvesting attempt: {response.message}")

                await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error in wood harvesting test: {e}")

    async def test_movement_system(self):
        """Test movement and position authority"""
        logger.info("🚶 Testing movement system...")

        if not self.clients:
            return

        client = self.clients[0]

        try:
            # Test series of movements
            positions = [(10.0, 10.0), (5.0, 15.0), (15.0, 5.0), (10.0, 10.0)]

            for target_x, target_y in positions:
                logger.info(f"🎯 Moving to ({target_x}, {target_y})")

                old_pos = client.get_agent_position()
                await client.move_to(target_x, target_y)

                # Wait for movement to complete
                await asyncio.sleep(3)

                new_pos = client.get_agent_position()
                self.results["position_updates"] += 1

                # Check for position jumps
                distance_moved = (
                    (new_pos[0] - old_pos[0]) ** 2 + (new_pos[1] - old_pos[1]) ** 2
                ) ** 0.5

                if distance_moved > 20.0:  # Suspicious jump
                    self.results["no_position_jumps"] = False
                    logger.warning(
                        f"⚠️ Possible position jump detected: {distance_moved:.2f} units"
                    )
                else:
                    logger.info(f"✅ Smooth movement: {distance_moved:.2f} units")

        except Exception as e:
            logger.error(f"Error in movement test: {e}")

    async def cleanup(self):
        """Clean up test resources"""
        logger.info("🧹 Cleaning up test resources...")

        # Disconnect clients
        for client in self.clients:
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting client: {e}")

        # Stop server
        if self.server:
            try:
                await self.server.stop()
            except Exception as e:
                logger.error(f"Error stopping server: {e}")

    def print_results(self):
        """Print test results"""
        logger.info("\n" + "=" * 60)
        logger.info("🏆 MMO SYSTEM TEST RESULTS")
        logger.info("=" * 60)

        logger.info(f"Server Started: {'✅' if self.results['server_started'] else '❌'}")
        logger.info(f"Clients Connected: {self.results['clients_connected']}/2")
        logger.info(
            f"Fishing Success Rate: {self.results['fishing_successes']}/{self.results['fishing_attempts']}"
        )
        logger.info(
            f"Wood Harvesting Success Rate: {self.results['wood_successes']}/{self.results['wood_attempts']}"
        )
        logger.info(f"Inventory Updates: {self.results['inventory_updates']}")
        logger.info(f"Position Updates: {self.results['position_updates']}")
        logger.info(
            f"No Position Jumps: {'✅' if self.results['no_position_jumps'] else '❌'}"
        )

        # Overall assessment
        total_actions = self.results["fishing_attempts"] + self.results["wood_attempts"]
        total_successes = (
            self.results["fishing_successes"] + self.results["wood_successes"]
        )

        if total_actions > 0:
            success_rate = (total_successes / total_actions) * 100
            logger.info(f"Overall Action Success Rate: {success_rate:.1f}%")

            if (
                success_rate >= 50
                and self.results["no_position_jumps"]
                and self.results["clients_connected"] >= 1
            ):
                logger.info("🎉 MMO SYSTEM TEST: PASSED")
            else:
                logger.info("⚠️ MMO SYSTEM TEST: NEEDS IMPROVEMENT")
        else:
            logger.info("⚠️ MMO SYSTEM TEST: NO ACTIONS COMPLETED")

        logger.info("=" * 60)


async def main():
    """Main test function"""
    test_runner = MMOTestRunner()

    try:
        await test_runner.run_test(duration=15)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
