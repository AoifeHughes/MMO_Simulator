#!/usr/bin/env python3
"""
Quick demo to show the fixed visualization scaling
"""

import asyncio
import subprocess
import sys
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Quick visualization demo"""
    print("""
    ╔══════════════════════════════════════════╗
    ║     VISUALIZATION SCALING DEMO          ║
    ║                                          ║
    ║  1. Server starts with agents           ║
    ║  2. Monitor shows proper world view      ║
    ║  3. Use controls to explore the world    ║
    ╚══════════════════════════════════════════╝

    VISUALIZATION CONTROLS:
    • SPACE - Reset view to default
    • +/- Keys - Zoom in/out
    • Mouse Wheel - Zoom in/out
    • Mouse Drag - Pan around the world
    • ESC - Exit monitor

    Starting server and test agents...
    """)

    # Start server and test
    server_process = subprocess.Popen(
        [sys.executable, "test_client_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        # Give server time to start and agents to connect
        await asyncio.sleep(5)

        print("""
    ✅ Server is running with test agents!

    Now run in another terminal:
        python run_monitor.py

    The monitor will show:
    • Properly scaled world view (10000x10000 world)
    • Agents moving around spawn area (~500,500)
    • Zoom controls to explore different areas
    • Real-time entity positions and states

    The view starts zoomed in on the spawn area where
    agents appear, so you should see them immediately!
        """)

        # Keep running for demo
        await asyncio.sleep(30)

    except KeyboardInterrupt:
        logger.info("Demo interrupted")
    finally:
        if server_process:
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait()

        print("\n✅ Demo complete!")

if __name__ == "__main__":
    asyncio.run(main())