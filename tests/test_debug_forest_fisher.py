#!/usr/bin/env python3
"""
Test script for debugging forest fisher cooperation scenario

This script runs the scenario for a short time and then generates
a comprehensive debug report to identify the positioning and
pathfinding issues.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent))

from debug_tracker import get_debugger, save_debug_report
from main import SimulatorApp

# Configure logging to be more verbose for debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("debug_test.log")],
)

logger = logging.getLogger(__name__)


async def run_debug_test():
    """Run the forest fisher scenario for debugging"""

    logger.info("🚀 Starting debug test for forest_fisher_cooperation scenario")

    # Create the simulator app with the problematic scenario
    app = SimulatorApp(
        mode="scenario",
        visualize=False,  # Disable visualization for headless testing
        scenario="forest_fisher_cooperation",
        timeout=60,  # Run for 60 seconds to gather debug data
    )

    # Set up debug tracking
    debugger = get_debugger()
    logger.info(f"Debug tracker initialized, database: {debugger.db_path}")

    try:
        # Run the scenario
        logger.info("⏱️  Running scenario for 60 seconds to collect debug data...")
        await app.run()

    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error during scenario run: {e}")
    finally:
        # Generate and save debug report
        logger.info("📊 Generating debug report...")

        # Wait a moment for any final debug data to be written
        await asyncio.sleep(1.0)

        # Generate the debug report
        report_filename = save_debug_report("forest_fisher_debug_report.txt")

        logger.info(f"📄 Debug report saved to: {report_filename}")

        # Print a summary to console
        print("\n" + "=" * 60)
        print("FOREST FISHER DEBUG TEST COMPLETED")
        print("=" * 60)
        print(f"Debug report saved to: {report_filename}")
        print(f"Debug database saved to: {debugger.db_path}")

        # Print a quick summary
        total_agents = len(debugger.agents)
        total_jumps = sum(
            len(tracker.get_position_jumps()) for tracker in debugger.agents.values()
        )
        total_distance_failures = sum(
            len(tracker.get_failed_actions_by_distance())
            for tracker in debugger.agents.values()
        )

        print(f"\nQUICK SUMMARY:")
        print(f"- Agents tracked: {total_agents}")
        print(f"- Position jumps detected: {total_jumps}")
        print(f"- Distance-related action failures: {total_distance_failures}")

        if total_jumps > 0:
            print("🚨 POSITION JUMPING DETECTED - Check the debug report for details")

        if total_distance_failures > 0:
            print(
                "🚨 DISTANCE VALIDATION ISSUES DETECTED - Check the debug report for details"
            )

        # Check if fixes are working
        if total_jumps == 0:
            print(
                "✅ NO POSITION JUMPING DETECTED - Position sync fixes appear to be working!"
            )

        if total_distance_failures == 0:
            print(
                "✅ NO DISTANCE VALIDATION FAILURES - Action validation fixes are working!"
            )

        # Check for wood harvesting behavior
        wood_harvesting_events = 0
        fishing_events = 0
        for tracker in debugger.agents.values():
            for event in tracker.resource_events:
                if event.resource_type == "wood" and event.event_type in [
                    "discovered",
                    "harvesting_attempt",
                ]:
                    wood_harvesting_events += 1
                elif event.resource_type == "water" and event.event_type in [
                    "discovered",
                    "fishing_attempt",
                ]:
                    fishing_events += 1

        if wood_harvesting_events > 0:
            print(
                f"✅ WOOD HARVESTING BEHAVIOR DETECTED - {wood_harvesting_events} events"
            )
        else:
            print("⚠️  NO WOOD HARVESTING BEHAVIOR DETECTED - May need investigation")

        if fishing_events > 0:
            print(f"✅ FISHING BEHAVIOR DETECTED - {fishing_events} events")

        print("\nReview the debug report and logs for detailed analysis.")


async def run_quick_test():
    """Run a shorter test for quick debugging"""

    logger.info("🚀 Starting quick debug test (30 seconds)")

    # Create the simulator app
    app = SimulatorApp(
        mode="scenario",
        visualize=True,  # Enable visualization for quick testing
        scenario="forest_fisher_cooperation",
        timeout=30,  # Run for 30 seconds
    )

    try:
        await app.run()
    except KeyboardInterrupt:
        logger.info("🛑 Quick test interrupted")
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        # Generate quick report
        debugger = get_debugger()
        print("\nQUICK DEBUG SUMMARY:")
        print(f"Agents tracked: {len(debugger.agents)}")

        for agent_id, tracker in debugger.agents.items():
            jumps = len(tracker.get_position_jumps())
            failures = len(tracker.get_failed_actions_by_distance())
            print(
                f"Agent {agent_id[:8]}: {jumps} position jumps, {failures} distance failures"
            )


def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(run_quick_test())
    else:
        asyncio.run(run_debug_test())


if __name__ == "__main__":
    main()
