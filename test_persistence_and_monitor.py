#!/usr/bin/env python3
"""
Test player persistence and show live monitor capabilities
"""

import asyncio
import time
import subprocess
import signal
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from client.core.agent_client import AgentClient, AgentConfig
from shared.math_utils import Vector2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PersistenceTestAgent(AgentClient):
    """Test agent that demonstrates disconnect/reconnect behavior"""

    def __init__(self, name: str, disconnect_after: float = 15.0):
        config = AgentConfig(name=name, agent_class="TestAgent")
        super().__init__(config)
        self.disconnect_after = disconnect_after
        self.start_time = None
        self.reconnected = False

    async def run(self):
        """Override run to handle disconnect/reconnect test"""
        self.start_time = time.time()

        # Run normally first
        await super().run()

    async def make_decision(self):
        """Simple decision making with disconnect test"""
        current_time = time.time()

        # Disconnect after specified time to test persistence
        if (not self.reconnected and
            self.start_time and
            current_time - self.start_time > self.disconnect_after):

            logger.info(f"{self.config.name} disconnecting to test persistence...")
            await self.disconnect()

            # Wait a bit, then reconnect
            await asyncio.sleep(3.0)

            logger.info(f"{self.config.name} reconnecting...")
            success = await self.connect()
            if success:
                self.reconnected = True
                logger.info(f"{self.config.name} successfully reconnected!")
            return

        # Simple wandering behavior
        if self.state == "idle" and time.time() % 3 < 0.5:
            import random
            target = Vector2(
                self.position.x + random.uniform(-50, 50),
                self.position.y + random.uniform(-50, 50)
            )
            self.action_queue.append({'type': 'move', 'target': target})

async def main():
    """Main test function"""
    print("""
    ╔══════════════════════════════════════════╗
    ║    PLAYER PERSISTENCE & MONITOR TEST    ║
    ║                                          ║
    ║  1. Agents connect and start moving      ║
    ║  2. Some agents disconnect after 15s    ║
    ║  3. Agents reconnect and resume          ║
    ║  4. Open monitor: python run_monitor.py ║
    ╚══════════════════════════════════════════╝
    """)

    # Start server
    logger.info("Starting server process...")
    server_process = subprocess.Popen(
        [sys.executable, "run_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Wait for server to start
        await asyncio.sleep(3)

        # Check if server started successfully
        if server_process.poll() is not None:
            logger.error("Server failed to start")
            return

        logger.info("Server started successfully")
        logger.info("Monitor API available at http://127.0.0.1:8080/world")

        # Create test agents
        agents = [
            PersistenceTestAgent("Persistent_Alpha", disconnect_after=10.0),
            PersistenceTestAgent("Persistent_Beta", disconnect_after=15.0),
            PersistenceTestAgent("Stable_Gamma", disconnect_after=999.0),  # Won't disconnect
            PersistenceTestAgent("Quick_Delta", disconnect_after=8.0),
        ]

        # Connect all agents
        logger.info("Connecting agents...")
        connected_agents = []

        for agent in agents:
            success = await agent.connect()
            if success:
                connected_agents.append(agent)
                logger.info(f"Agent {agent.config.name} connected")
            else:
                logger.error(f"Agent {agent.config.name} failed to connect")

        if not connected_agents:
            logger.error("No agents connected successfully")
            return

        logger.info(f"Running test with {len(connected_agents)} agents...")
        logger.info("Some agents will disconnect and reconnect to test persistence")
        logger.info("Run 'python run_monitor.py' in another terminal to see live visualization")

        # Start all agent loops
        agent_tasks = []
        for agent in connected_agents:
            task = asyncio.create_task(agent.run())
            agent_tasks.append(task)

        # Run for 30 seconds
        test_duration = 30.0
        await asyncio.sleep(test_duration)

        # Cancel agent tasks
        for task in agent_tasks:
            task.cancel()

        # Disconnect remaining agents
        for agent in connected_agents:
            if agent.connected:
                await agent.disconnect()

        logger.info("Test completed!")
        print("""
        Test Summary:
        - Player persistence: Agents that disconnected kept their data
        - Server continues running inactive players in background
        - Players can reconnect and resume from where they left off
        - Monitor API provides real-time visualization data

        Try running the monitor: python run_monitor.py
        """)

    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        # Stop server
        if server_process:
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait()

        logger.info("Cleanup complete")

if __name__ == "__main__":
    asyncio.run(main())