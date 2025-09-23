#!/usr/bin/env python3
"""
Debug script for basic_combat scenario to identify why agents aren't detecting each other.
This script will monitor vision system and entity visibility.
"""

import asyncio
import sys
import time
import math
from server.server import GameServer
from client.client import GameClient
from scenarios.scenario_manager import ScenarioManager
import logging

# Setup detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class BasicCombatDebugger:
    """Debug basic combat visibility issues"""

    def __init__(self):
        self.server = None
        self.clients = []
        self.start_time = 0

    async def start_server(self):
        """Start server with basic combat scenario"""
        self.server = GameServer(100, 100)

        # Load basic combat scenario
        manager = ScenarioManager()
        scenario = await manager.load_scenario("basic_combat", self.server)
        if not scenario:
            logger.error("Failed to load basic_combat scenario!")
            return False

        # Start server
        server_task = asyncio.create_task(self.server.start())
        await asyncio.sleep(1)

        return True

    async def connect_agents(self):
        """Connect AI clients for agents"""
        agents = self.server.world.get_all_agents()

        logger.info(f"📍 Server has {len(agents)} total agents:")
        for agent in agents:
            logger.info(f"   {agent.agent_type} {agent.id[:8]} at ({agent.x:.1f}, {agent.y:.1f})")

        for agent_data in agents:
            agent_type = agent_data.agent_type
            logger.info(f"🤖 Connecting {agent_type} agent {agent_data.id[:8]}")

            client = GameClient()
            connected = await client.connect(agent_type=agent_type)

            if connected:
                self.clients.append(client)
                logger.info(f"✅ Connected {agent_type} agent")
            else:
                logger.error(f"❌ Failed to connect {agent_type} agent")

        return len(self.clients) == len(agents)

    async def analyze_visibility(self, duration: float = 10.0):
        """Analyze visibility between agents"""
        self.start_time = time.time()
        end_time = self.start_time + duration

        logger.info("="*80)
        logger.info("🔍 VISIBILITY ANALYSIS STARTED")
        logger.info(f"📊 Duration: {duration} seconds")
        logger.info("🎯 Focus: Why agents aren't detecting each other")
        logger.info("="*80)

        last_report_time = self.start_time
        report_interval = 2.0

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

            # Periodic visibility report
            if current_time - last_report_time >= report_interval:
                await self.report_visibility_status(elapsed)
                last_report_time = current_time

            await asyncio.sleep(0.1)  # 10 FPS for analysis

        logger.info("="*80)
        logger.info("📊 VISIBILITY ANALYSIS COMPLETE")
        logger.info("="*80)

    async def report_visibility_status(self, elapsed: float):
        """Report current visibility status"""
        logger.info(f"\n🔍 --- VISIBILITY STATUS at {elapsed:.1f}s ---")

        agents = self.server.world.get_all_agents()

        # Calculate all distances
        logger.info(f"📍 Current Agent Positions:")
        for agent in agents:
            logger.info(f"   {agent.agent_type} {agent.id[:8]} at ({agent.x:.1f}, {agent.y:.1f})")

        # Calculate distances between all agents
        logger.info(f"\n📏 Distance Matrix:")
        for i, agent1 in enumerate(agents):
            for j, agent2 in enumerate(agents):
                if i < j:  # Only calculate each pair once
                    dx = agent2.x - agent1.x
                    dy = agent2.y - agent1.y
                    distance = math.sqrt(dx*dx + dy*dy)

                    # Check if they should detect each other
                    player_range = 20.0
                    enemy_range = 15.0

                    agent1_detects = False
                    agent2_detects = False

                    if agent1.agent_type == "player" and agent2.agent_type == "enemy":
                        agent1_detects = distance <= player_range
                        agent2_detects = distance <= enemy_range
                    elif agent1.agent_type == "enemy" and agent2.agent_type == "player":
                        agent1_detects = distance <= enemy_range
                        agent2_detects = distance <= player_range

                    status = "🔴"
                    if agent1_detects or agent2_detects:
                        status = "🟡" if not (agent1_detects and agent2_detects) else "🟢"

                    logger.info(f"   {status} {agent1.agent_type} vs {agent2.agent_type}: {distance:.1f}u (A1:{agent1_detects}, A2:{agent2_detects})")

        # Check what each client sees
        logger.info(f"\n👁️ Client Visible Entities:")
        for client in self.clients:
            if client.agent and hasattr(client.agent, 'visible_entities'):
                visible_count = len(client.agent.visible_entities)
                agent_type = client.agent.agent_type
                agent_id = client.agent_id[:8]

                logger.info(f"   {agent_type} {agent_id} sees {visible_count} entities:")

                for entity in client.agent.visible_entities:
                    entity_type = entity.get('agent_type', 'unknown')
                    entity_id = entity.get('id', 'unknown')[:8]
                    entity_x = entity.get('x', 0)
                    entity_y = entity.get('y', 0)

                    # Calculate distance from this client's agent
                    dx = entity_x - client.agent.x
                    dy = entity_y - client.agent.y
                    distance = math.sqrt(dx*dx + dy*dy)

                    logger.info(f"     - {entity_type} {entity_id} at ({entity_x:.1f}, {entity_y:.1f}) dist={distance:.1f}")

        # Server-side visibility check
        logger.info(f"\n🔬 Server-Side Visibility Check:")
        for agent in agents:
            visible_agents = self.server.world.get_visible_agents(agent.id)
            logger.info(f"   {agent.agent_type} {agent.id[:8]} should see {len(visible_agents)} agents:")
            for visible_agent in visible_agents:
                dx = visible_agent.x - agent.x
                dy = visible_agent.y - agent.y
                distance = math.sqrt(dx*dx + dy*dy)
                logger.info(f"     - {visible_agent.agent_type} {visible_agent.id[:8]} at distance {distance:.1f}")

    async def cleanup(self):
        """Clean up connections"""
        logger.info("🧹 Cleaning up...")

        for client in self.clients:
            if client.connected:
                await client.disconnect()

        if self.server:
            self.server.stop()

        logger.info("✅ Cleanup complete")

    async def run(self):
        """Main execution"""
        try:
            # Start server
            logger.info("🚀 Starting basic combat debug server...")
            if not await self.start_server():
                return

            await asyncio.sleep(1)

            # Connect agents
            logger.info("🔗 Connecting all agents...")
            if not await self.connect_agents():
                logger.error("❌ Failed to connect all agents!")
                return

            await asyncio.sleep(2)

            # Analyze visibility
            await self.analyze_visibility(duration=10.0)

        except KeyboardInterrupt:
            logger.info("\n⏹️ Interrupted by user")
        except Exception as e:
            logger.error(f"💥 Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()

def main():
    debugger = BasicCombatDebugger()
    asyncio.run(debugger.run())

if __name__ == "__main__":
    main()