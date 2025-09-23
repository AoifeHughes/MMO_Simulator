#!/usr/bin/env python3
"""
Debug script to isolate and demonstrate the jittering issue in basic_combat scenario.

This script runs the basic_combat scenario with enhanced logging to show
the frequency of movement updates and identify the source of jittering.
"""

import asyncio
import time
import logging
from scenarios.basic_combat import BasicCombatScenario
from server.server import GameServer
from client.client import GameClient

# Setup logging to capture movement updates
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DebugAgent:
    """Wrapper for agents to log movement changes"""

    def __init__(self, agent):
        self.agent = agent
        self.last_velocity = (0, 0)
        self.last_rotation = 0
        self.velocity_change_count = 0
        self.last_log_time = time.time()

    def __getattr__(self, name):
        return getattr(self.agent, name)

    def update_behavior_tree(self, delta_time):
        # Capture current state
        old_vx, old_vy = self.velocity_x, self.velocity_y
        old_rotation = self.rotation

        # Call original update
        result = self.agent.update_behavior_tree(delta_time)

        # Check for changes
        current_time = time.time()
        if (abs(self.velocity_x - old_vx) > 0.01 or
            abs(self.velocity_y - old_vy) > 0.01 or
            abs(self.rotation - old_rotation) > 1.0):

            self.velocity_change_count += 1

            # Log every 30 changes or every 5 seconds
            if (self.velocity_change_count % 30 == 0 or
                current_time - self.last_log_time > 5.0):

                logger.warning(f"[JITTER DEBUG] Agent {self.id[:8]} ({self.agent_type}) "
                             f"velocity changed {self.velocity_change_count} times in "
                             f"{current_time - self.last_log_time:.1f}s. "
                             f"Current: vel=({self.velocity_x:.2f}, {self.velocity_y:.2f}), "
                             f"rot={self.rotation:.1f}")
                self.last_log_time = current_time

        return result

async def debug_jitter_scenario():
    """Run a debug version of the basic combat scenario"""

    logger.info("=== Starting Jitter Debug Session ===")

    # Create server and scenario
    server = GameServer(100, 100)
    scenario = BasicCombatScenario()

    # Start server
    server_task = asyncio.create_task(server.start())
    await asyncio.sleep(1)  # Let server start

    # Setup scenario
    await scenario.setup(server)
    await scenario.spawn_agents()

    logger.info(f"Spawned {len(server.world.get_all_agents())} agents")

    # Connect AI clients for each agent
    clients = []
    debug_agents = []

    for agent_data in server.world.get_all_agents():
        client = GameClient()
        connected = await client.connect(agent_type=agent_data.agent_type)

        if connected and client.agent:
            # Wrap agent for debugging
            debug_agent = DebugAgent(client.agent)
            client.agent = debug_agent
            debug_agents.append(debug_agent)
            clients.append(client)
            logger.info(f"Connected debug client for {agent_data.agent_type} {agent_data.id[:8]}")

    # Run for 30 seconds to observe jittering
    logger.info("=== Running debug session for 30 seconds ===")
    start_time = time.time()

    try:
        while time.time() - start_time < 30.0:
            # Update all clients
            update_tasks = []
            for client in clients:
                if client.connected:
                    update_tasks.append(client.update())

            if update_tasks:
                await asyncio.gather(*update_tasks, return_exceptions=True)

            await asyncio.sleep(0.016)  # 60 FPS

    except KeyboardInterrupt:
        logger.info("Debug session interrupted")

    # Cleanup
    logger.info("=== Debug Session Complete ===")
    logger.info("Summary of velocity changes:")
    for debug_agent in debug_agents:
        logger.info(f"Agent {debug_agent.id[:8]} ({debug_agent.agent_type}): "
                   f"{debug_agent.velocity_change_count} velocity changes")

    for client in clients:
        if client.connected:
            await client.disconnect()

    server.stop()
    await asyncio.sleep(0.5)  # Let server cleanup

if __name__ == "__main__":
    asyncio.run(debug_jitter_scenario())