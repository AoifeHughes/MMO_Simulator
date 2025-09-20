#!/usr/bin/env python3
"""
Demonstration of the Integrated MMO Experience

This script demonstrates the complete integrated workflow:
1. Auto-detects and starts server if needed
2. Loads existing player data if available
3. Starts test simulation with agents
4. Shows live visualization with real-time updates
"""

import asyncio
import sys
import os
import time
import subprocess

# Add current directory to path
sys.path.append('.')

async def main():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                INTEGRATED MMO EXPERIENCE DEMO               ║
    ║                                                              ║
    ║  This demo shows the complete integrated workflow:           ║
    ║                                                              ║
    ║  ✅ All visualization issues have been fixed                ║
    ║  ✅ Player persistence and resumption implemented           ║
    ║  ✅ Auto-startup for server and simulation                  ║
    ║  ✅ Integrated live monitor experience                      ║
    ║                                                              ║
    ║  What will happen:                                           ║
    ║  1. 🔍 Check for existing server                            ║
    ║  2. 🚀 Start server if needed                               ║
    ║  3. 📊 Load any existing player data                        ║
    ║  4. 🎮 Start test simulation with agents                     ║
    ║  5. 📺 Show live visualization                               ║
    ║                                                              ║
    ║  Run: python run_monitor.py                                 ║
    ║  Or:  python demo_integrated_experience.py                  ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    print("Starting integrated MMO experience in 3 seconds...")
    await asyncio.sleep(3)

    # Import and run the integrated monitor
    from visualization.live_monitor import LiveServerMonitor

    print("🚀 Launching integrated MMO monitor...")
    monitor = LiveServerMonitor(auto_start=True)

    try:
        await monitor.start()
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo error: {e}")
        import logging
        logging.error(f"Demo error: {e}", exc_info=True)

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(main())