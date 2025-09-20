#!/usr/bin/env python3
"""
Quick test to add some agents to the running server
"""

import asyncio
import sys
import time
sys.path.append('.')

from client.core.agent_client import AgentClient, AgentConfig
from shared.math_utils import Vector2

class SimpleTestAgent(AgentClient):
    def __init__(self, name: str):
        config = AgentConfig(name=name, agent_class="TestAgent")
        super().__init__(config)

    async def make_decision(self):
        # Simple wandering
        if self.state == "idle" and time.time() % 5 < 0.5:
            import random
            target = Vector2(
                self.position.x + random.uniform(-100, 100),
                self.position.y + random.uniform(-100, 100)
            )
            self.action_queue.append({'type': 'move', 'target': target})

async def main():
    agents = [
        SimpleTestAgent("TestAgent_A"),
        SimpleTestAgent("TestAgent_B"),
        SimpleTestAgent("TestAgent_C"),
    ]

    # Connect agents
    connected = []
    for agent in agents:
        success = await agent.connect()
        if success:
            connected.append(agent)
            print(f"Connected {agent.config.name}")

    if not connected:
        print("No agents connected!")
        return

    # Run for 60 seconds
    tasks = [asyncio.create_task(agent.run()) for agent in connected]
    await asyncio.sleep(60)

    # Cleanup
    for task in tasks:
        task.cancel()
    for agent in connected:
        if agent.connected:
            await agent.disconnect()

if __name__ == "__main__":
    asyncio.run(main())