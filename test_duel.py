#!/usr/bin/env python3
"""
Test script for monitoring the simple duel scenario.
This script runs the duel and outputs detailed information about agent behavior.
"""

import asyncio
import sys
import time
from server.server import GameServer
from client.client import GameClient
from scenarios.scenario_manager import ScenarioManager
import logging

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class DuelMonitor:
    """Monitor and report on the duel scenario"""

    def __init__(self):
        self.server = None
        self.clients = []
        self.start_time = 0
        self.update_count = 0

    async def start_server(self):
        """Start the game server with duel scenario"""
        self.server = GameServer(100, 100)

        # Load the duel scenario
        manager = ScenarioManager()
        scenario = await manager.load_scenario("simple_duel", self.server)
        if not scenario:
            logger.error("Failed to load simple_duel scenario!")
            return False

        # Start server
        server_task = asyncio.create_task(self.server.start())
        await asyncio.sleep(1)  # Give server time to start

        return True

    async def connect_agents(self):
        """Connect AI clients for the agents"""
        # Get all spawned agents
        agents = self.server.world.get_all_agents()

        for agent_data in agents:
            agent_type = agent_data.agent_type
            logger.info(f"Connecting AI client for {agent_type} agent {agent_data.id[:8]}")

            client = GameClient()
            connected = await client.connect(agent_type=agent_type)

            if connected:
                self.clients.append(client)
                logger.info(f"✓ Connected {agent_type} agent")
            else:
                logger.error(f"✗ Failed to connect {agent_type} agent")

        return len(self.clients) == 2

    async def monitor_battle(self, duration: float = 30.0):
        """Monitor the battle for a specified duration"""
        self.start_time = time.time()
        end_time = self.start_time + duration

        logger.info("="*70)
        logger.info("BATTLE MONITORING STARTED")
        logger.info(f"Duration: {duration} seconds")
        logger.info("="*70)

        last_report_time = self.start_time
        report_interval = 2.0  # Report every 2 seconds

        while time.time() < end_time:
            current_time = time.time()
            elapsed = current_time - self.start_time

            # Update all clients
            update_tasks = []
            for client in self.clients:
                if client.connected:
                    update_tasks.append(client.update())

            if update_tasks:
                await asyncio.gather(*update_tasks, return_exceptions=True)

            self.update_count += 1

            # Periodic status report
            if current_time - last_report_time >= report_interval:
                await self.report_status(elapsed)
                last_report_time = current_time

            await asyncio.sleep(0.016)  # ~60 FPS update rate

        # Final report
        logger.info("="*70)
        logger.info("BATTLE MONITORING COMPLETE")
        await self.report_final_status()
        logger.info("="*70)

    async def report_status(self, elapsed: float):
        """Report current battle status"""
        logger.info(f"\n--- Status Report at {elapsed:.1f}s ---")

        agents = self.server.world.get_all_agents()

        for i, agent in enumerate(agents, 1):
            logger.info(f"\nAgent {i} ({agent.agent_type}):")
            logger.info(f"  ID: {agent.id[:8]}")
            logger.info(f"  Position: ({agent.x:.1f}, {agent.y:.1f})")
            logger.info(f"  Health: {agent.health:.0f}/100")
            logger.info(f"  Velocity: ({agent.velocity_x:.1f}, {agent.velocity_y:.1f})")

            # Calculate distance between agents
            if len(agents) == 2:
                other = agents[1] if i == 1 else agents[0]
                dx = other.x - agent.x
                dy = other.y - agent.y
                distance = (dx**2 + dy**2)**0.5
                logger.info(f"  Distance to opponent: {distance:.1f} units")

        # Check for combat events
        if len(agents) == 2:
            agent1, agent2 = agents

            # Check if they're in combat range
            dx = agent2.x - agent1.x
            dy = agent2.y - agent1.y
            distance = (dx**2 + dy**2)**0.5

            if distance < 5:
                logger.info("\n⚔️  AGENTS IN CLOSE COMBAT RANGE!")
            elif distance < 10:
                logger.info("\n🎯 Agents approaching combat range")
            elif distance < 20:
                logger.info("\n👀 Agents should be aware of each other")
            else:
                logger.info("\n🔍 Agents searching for targets")

    async def report_final_status(self):
        """Report final battle statistics"""
        agents = self.server.world.get_all_agents()

        logger.info("\n=== FINAL BATTLE STATISTICS ===")
        logger.info(f"Total updates: {self.update_count}")
        logger.info(f"Average FPS: {self.update_count / (time.time() - self.start_time):.1f}")

        for agent in agents:
            logger.info(f"\n{agent.agent_type.upper()} Agent {agent.id[:8]}:")
            logger.info(f"  Final Health: {agent.health:.0f}/100")
            logger.info(f"  Final Position: ({agent.x:.1f}, {agent.y:.1f})")

            if agent.health <= 0:
                logger.info("  Status: DEFEATED ☠️")
            elif agent.health < 50:
                logger.info("  Status: WOUNDED 🩹")
            else:
                logger.info("  Status: HEALTHY ✅")

        # Determine winner
        alive_agents = [a for a in agents if a.health > 0]
        if len(alive_agents) == 1:
            winner = alive_agents[0]
            logger.info(f"\n🏆 WINNER: {winner.agent_type.upper()} Agent {winner.id[:8]}!")
        elif len(alive_agents) == 2:
            logger.info("\n⏸️  BATTLE ONGOING - Both agents still alive")
        else:
            logger.info("\n💀 DRAW - Both agents defeated")

    async def cleanup(self):
        """Clean up connections and server"""
        logger.info("\nCleaning up...")

        for client in self.clients:
            if client.connected:
                await client.disconnect()

        if self.server:
            self.server.stop()

        logger.info("Cleanup complete")

    async def run(self):
        """Main execution method"""
        try:
            # Start server
            logger.info("Starting duel server...")
            if not await self.start_server():
                return

            await asyncio.sleep(1)

            # Connect agents
            logger.info("Connecting agent clients...")
            if not await self.connect_agents():
                logger.error("Failed to connect all agents!")
                return

            await asyncio.sleep(1)

            # Monitor battle
            await self.monitor_battle(duration=20.0)

        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        except Exception as e:
            logger.error(f"Error during execution: {e}")
        finally:
            await self.cleanup()

def main():
    """Entry point"""
    monitor = DuelMonitor()
    asyncio.run(monitor.run())

if __name__ == "__main__":
    main()