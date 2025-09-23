#!/usr/bin/env python3
"""
Quick combat test bypassing launcher
"""
import sys
import asyncio
import time
sys.path.append('.')

from server.core.world_server import WorldServer
from config.config_loader import ConfigLoader
from examples.simple_agent import CombatAgent
from client.core.agent_client import AgentConfig

async def test_combat():
    # Start server
    config_loader = ConfigLoader()
    config_loader.load_all_configs()

    print("Starting server...")
    server = WorldServer(config_loader)
    await server.start()

    await asyncio.sleep(1)

    print("Creating test warrior...")
    warrior = CombatAgent("TestWarrior")

    print("Connecting warrior...")
    success = await warrior.connect()
    if not success:
        print("Failed to connect warrior")
        return

    print("Warrior connected! Running for 15 seconds...")

    # Run for 15 seconds
    start_time = time.time()
    while time.time() - start_time < 15:
        await asyncio.sleep(0.1)

    print("Test completed!")
    await warrior.disconnect()
    await server.stop()

if __name__ == "__main__":
    asyncio.run(test_combat())