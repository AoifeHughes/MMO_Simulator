#!/usr/bin/env python3
"""
Integrated MMO Monitor - Auto-starting server and simulation
"""

import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from visualization.live_monitor import LiveServerMonitor

async def main():
    """Run the integrated MMO monitor experience"""
    print("""
    ╔══════════════════════════════════════════╗
    ║         INTEGRATED MMO MONITOR          ║
    ║                                          ║
    ║  🚀 Auto-starting server if needed       ║
    ║  📊 Loading existing player data         ║
    ║  🎮 Starting test simulation             ║
    ║  📺 Real-time visualization              ║
    ║                                          ║
    ║  Press ESC in window to exit             ║
    ╚══════════════════════════════════════════╝
    """)

    # Create monitor with auto-start enabled
    monitor = LiveServerMonitor(auto_start=True)

    try:
        # Start the integrated experience
        await monitor.start()
    except KeyboardInterrupt:
        print("\n🛑 Monitor interrupted by user")
    except Exception as e:
        print(f"❌ Monitor error: {e}")
        logging.error(f"Monitor error: {e}", exc_info=True)

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Run the monitor
    asyncio.run(main())