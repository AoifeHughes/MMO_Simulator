#!/usr/bin/env python3
import asyncio
import logging
from server.mmo_server import MMOGameServer
from world.terrain_generator import TerrainType

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test():
    print("Creating server...")
    server = MMOGameServer(10, 10, TerrainType.MIXED, 42)
    print("Server created, attempting to start...")

    try:
        # Start the server with a timeout
        await asyncio.wait_for(server.start(), timeout=5.0)
    except asyncio.TimeoutError:
        print("Server start timed out")
    except Exception as e:
        print(f"Server start failed: {e}")

    print("Test complete")

if __name__ == "__main__":
    asyncio.run(test())