#!/usr/bin/env python3
"""
Run the MMO server
"""

import asyncio
import logging
import sys

# Fix import paths
sys.path.append('.')

from server.core.world_server import WorldServer
from shared.constants import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Run the server"""
    print("""
    ╔══════════════════════════════════════════╗
    ║     MMO SERVER v2.0 (Client-Server)     ║
    ║                                          ║
    ║  Authoritative server with agent clients ║
    ╚══════════════════════════════════════════╝
    """)

    # Check for config directory argument
    config_dir = "config"
    if len(sys.argv) > 1:
        config_dir = sys.argv[1]

    server = WorldServer(DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT, config_dir)

    try:
        logger.info("Starting MMO server...")
        await server.start()
    except KeyboardInterrupt:
        logger.info("Server interrupted, shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())