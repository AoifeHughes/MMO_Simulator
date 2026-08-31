#!/usr/bin/env python3
"""
Visual simulation example with persistent database for inspection.

This version saves the database to a permanent file that you can examine after
the simulation completes.

Controls:
- Left Click + Drag: Pan around the map
- Mouse Wheel: Zoom in/out
- Click on Agent: Show detailed information panel
- Space: Center camera on first agent
- ESC: Deselect agent and hide info panel

Database:
- The simulation database is saved to 'simulation_data.db'
- You can inspect it with SQLite tools after the simulation
"""

import argparse
import os
import sys
import time

# Add the simulation framework to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import the functions from visual_simulation
from visual_simulation import create_diverse_agents, create_varied_npcs  # noqa: E402

from simulation_framework.src.core.config import SimulationConfig  # noqa: E402
from simulation_framework.src.core.simulation import Simulation  # noqa: E402


def main():
    """Run a visual simulation with persistent database"""
    parser = argparse.ArgumentParser(
        description="MMO Simulator with Persistent Database"
    )
    parser.add_argument(
        "--width", type=int, default=25, help="World width (default: 25)"
    )
    parser.add_argument(
        "--height", type=int, default=25, help="World height (default: 25)"
    )
    parser.add_argument(
        "--agents", type=int, default=6, help="Number of agents (default: 6)"
    )
    parser.add_argument(
        "--npcs", type=int, default=4, help="Number of NPCs (default: 4)"
    )
    parser.add_argument("--ticks", type=int, default=50, help="Max ticks (default: 50)")
    parser.add_argument(
        "--seed", type=int, default=12345, help="World seed (default: 12345)"
    )
    parser.add_argument(
        "--no-visual", action="store_true", help="Run without visualization"
    )
    parser.add_argument(
        "--db-file", type=str, default="simulation_data.db", help="Database file path"
    )

    args = parser.parse_args()

    print("=== Persistent MMO Simulation ===")
    print(f"World Size: {args.width}x{args.height}")
    print(f"Agents: {args.agents}, NPCs: {args.npcs}")
    print(f"Max Ticks: {args.ticks}")
    print(f"Database: {args.db_file}")

    # Remove existing database if it exists
    if os.path.exists(args.db_file):
        os.remove(args.db_file)
        print(f"Removed existing database: {args.db_file}")

    try:
        # Create simulation configuration with persistent database
        config = SimulationConfig(
            world_width=args.width,
            world_height=args.height,
            world_seed=args.seed,
            max_ticks=args.ticks,
            database_path=args.db_file,  # Persistent database file
            save_interval=5,  # Save snapshots more frequently for inspection
            analytics_interval=10,
            tick_rate=5 if not args.no_visual else 0,  # Slower for better visualization
            # Visualization settings
            enable_visualizer=not args.no_visual,
            visualizer_width=1000,
            visualizer_height=700,
            visualizer_tile_size=20,
            # Agent settings for interesting simulation
            default_agent_vision_range=5,
            fog_of_war_enabled=True,
            log_actions=True,  # Enable action logging
        )

        print(f"Configuration: Seed={config.world_seed}, Tick Rate={config.tick_rate}")

        # Create simulation
        simulation = Simulation(config)
        simulation.initialize_simulation(
            "Persistent Database Demo",
            f"Demonstration simulation with database logging. World: {args.width}x{args.height}, "
            f"Agents: {args.agents}, NPCs: {args.npcs}",
        )

        print(f"Initialized simulation with ID: {simulation.simulation_id}")

        # Create and add diverse agents
        agents = create_diverse_agents(simulation.world, args.agents)
        for agent in agents:
            simulation.add_agent(agent)
            print(
                f"Added {agent.name} ({agent.character_class.name}) at {agent.position}"
            )

        # Create and add NPCs
        npcs = create_varied_npcs(simulation.world, args.npcs)
        for npc in npcs:
            simulation.add_npc(npc)
            print(f"Added {npc.name} ({npc.npc_type}) at {npc.position}")

        print(
            f"\\nStarting simulation with {len(agents)} agents and {len(npcs)} NPCs..."
        )

        # Record start time
        start_time = time.time()

        if args.no_visual:
            print("Running without visualization")
            simulation.run(num_ticks=args.ticks)
        else:
            print("\\n=== Visualization Controls ===")
            print("• Left Click + Drag: Pan around the map")
            print("• Mouse Wheel: Zoom in/out")
            print("• Click on Agent: Show detailed information")
            print("• Space: Center camera on first agent")
            print("• ESC: Deselect agent")
            print("• Close window: Stop simulation")
            print("\\nStarting visual simulation...")

            try:
                simulation.run_with_visualizer(num_ticks=args.ticks)
            except ImportError as e:
                print(f"\\nVisualization failed: {e}")
                print("Make sure pygame is installed: pip install pygame>=2.0.0")
                print("Falling back to non-visual simulation...")
                simulation.run(num_ticks=args.ticks)

        end_time = time.time()
        duration = end_time - start_time

        print(
            f"\\nSimulation completed after {simulation.time_manager.current_tick} ticks"
        )
        print(f"Runtime: {duration:.2f} seconds")

        # Display final statistics
        stats = simulation.get_statistics()
        print("\\n=== Final Statistics ===")
        print(f"Total Agents: {stats['total_agents']}")
        print(f"Active Agents: {stats['active_agents']}")
        print(f"Total NPCs: {stats['total_npcs']}")
        print(f"Active NPCs: {stats['active_npcs']}")
        print(f"Average Tick Time: {stats['average_tick_time']:.4f}s")

        # Show final agent status
        print("\\n=== Final Agent Status ===")
        for agent in simulation.agents:
            status = "Alive" if agent.stats.is_alive else "Dead"
            goals = len(agent.current_goals)
            print(
                f"{agent.name}: {status}, Health {agent.stats.health}/{agent.stats.max_health}, "
                f"Position {agent.position}, {goals} goals"
            )

        # Database information
        print("\\n=== Database Information ===")
        print(f"Database saved to: {os.path.abspath(args.db_file)}")
        print(f"Database size: {os.path.getsize(args.db_file) / 1024:.1f} KB")

        # Display some database contents
        print("\\n=== Database Contents Preview ===")
        try:
            import sqlite3

            conn = sqlite3.connect(args.db_file)
            cursor = conn.cursor()

            # Show tables
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = cursor.fetchall()
            print(f"Tables: {', '.join([table[0] for table in tables])}")

            # Show action count
            cursor.execute("SELECT COUNT(*) FROM action_logs")
            action_count = cursor.fetchone()[0]
            print(f"Total actions logged: {action_count}")

            # Show agent snapshots
            cursor.execute("SELECT COUNT(*) FROM agent_snapshots")
            snapshot_count = cursor.fetchone()[0]
            print(f"Agent snapshots: {snapshot_count}")

            # Show some recent actions
            cursor.execute("""
                SELECT tick, agent_id, action_type, success, result_message
                FROM action_logs
                ORDER BY tick DESC
                LIMIT 5
            """)
            recent_actions = cursor.fetchall()

            if recent_actions:
                print("\\nRecent actions:")
                for tick, agent_id, action_type, success, message in recent_actions:
                    status = "✓" if success else "✗"
                    print(
                        f"  Tick {tick}: Agent {agent_id} {action_type} {status} - {message}"
                    )

            conn.close()

        except Exception as e:
            print(f"Error reading database preview: {e}")

        print("\\n=== How to Inspect the Database ===")
        print("You can examine the database using:")
        print(f"1. SQLite command line: sqlite3 {args.db_file}")
        print("2. SQLite browser: https://sqlitebrowser.org/")
        print("3. Python script:")
        print("   import sqlite3")
        print(f"   conn = sqlite3.connect('{args.db_file}')")
        print("   cursor = conn.cursor()")
        print("   cursor.execute('SELECT * FROM action_logs LIMIT 10')")
        print("   print(cursor.fetchall())")

        print("\\nPersistent simulation completed successfully!")

    except KeyboardInterrupt:
        print("\\nSimulation interrupted by user")
    except Exception as e:
        print(f"\\nError during simulation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
