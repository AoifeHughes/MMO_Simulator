#!/usr/bin/env python3
"""
Visual simulation example demonstrating pygame integration.

This example shows how to:
1. Create a simulation configuration with visualization enabled
2. Initialize a simulation with the visualizer
3. Create and add agents with different character classes
4. Run the simulation with real-time visualization
5. Interact with agents through the visual interface

Controls:
- Left Click + Drag: Pan around the map
- Mouse Wheel: Zoom in/out
- Click on Agent: Show detailed information panel
- Space: Center camera on first agent
- ESC: Deselect agent and hide info panel
"""

import argparse
import os
import sys
import tempfile

# Add the simulation framework to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation_framework.src.ai.goal import (  # noqa: E402
    ExploreGoal,
    GatherResourceGoal,
)
from simulation_framework.src.core.config import SimulationConfig  # noqa: E402
from simulation_framework.src.core.simulation import Simulation  # noqa: E402
from simulation_framework.src.entities.agent import (  # noqa: E402
    Agent,
    create_agent_with_archetype,
    create_random_agent,
)
from simulation_framework.src.entities.npc import (  # noqa: E402
    NPC,
    create_basic_goblin,
    create_forest_wolf,
)


def find_valid_spawn_positions(world, num_positions: int) -> list[tuple[int, int]]:
    """Find valid spawn positions that are not in water"""
    positions = []
    max_attempts = num_positions * 10  # Avoid infinite loop
    attempts = 0

    import random

    while len(positions) < num_positions and attempts < max_attempts:
        x = random.randint(1, world.width - 2)  # Stay away from edges
        y = random.randint(1, world.height - 2)

        # Check if position is valid and passable (not water)
        if world.is_valid_position(x, y) and world.is_passable(x, y):
            # Check that position is not too close to existing positions
            too_close = False
            for existing_x, existing_y in positions:
                if abs(x - existing_x) < 2 and abs(y - existing_y) < 2:
                    too_close = True
                    break

            if not too_close:
                positions.append((x, y))

        attempts += 1

    # If we couldn't find enough positions, fill with basic grid positions
    # and let the world generation handle any water issues
    while len(positions) < num_positions:
        i = len(positions)
        x = (i % 4) * (world.width // 4) + (world.width // 8)
        y = (i // 4) * (world.height // 4) + (world.height // 8)
        # Clamp to world bounds
        x = max(1, min(world.width - 2, x))
        y = max(1, min(world.height - 2, y))
        positions.append((x, y))

    return positions


def create_diverse_agents(world, num_agents: int = 8) -> list[Agent]:
    """Create a diverse set of agents for the simulation"""
    agents = []

    # Create some specific archetypes
    archetypes = [
        "explorer",
        "warrior",
        "crafter",
        "social",
        "aggressive",
        "peaceful",
        "curious",
        "merchant",
    ]

    # Find valid spawn positions
    positions = find_valid_spawn_positions(world, num_agents)

    for i in range(num_agents):
        position = positions[i]

        # Create agent with specific archetype if available
        if i < len(archetypes):
            agent = create_agent_with_archetype(
                position=position,
                name=f"{archetypes[i].title()} Agent {i+1}",
                archetype=archetypes[i],
            )
        else:
            agent = create_random_agent(position=position, name=f"Random Agent {i+1}")

        # Add some initial goals based on agent type
        if i % 3 == 0:
            agent.current_goals.append(ExploreGoal(priority=3))
        elif i % 3 == 1:
            agent.current_goals.append(
                GatherResourceGoal(
                    resource_type="wood" if i % 2 == 0 else "stone", target_quantity=10
                )
            )
        else:
            # Some agents start without specific goals
            pass

        agents.append(agent)

    return agents


def create_varied_npcs(world, num_npcs: int = 6) -> list[NPC]:
    """Create various NPCs for interaction"""
    npcs = []

    # Find valid spawn positions for NPCs
    positions = find_valid_spawn_positions(world, num_npcs)

    for i in range(num_npcs):
        position = positions[i]

        if i % 2 == 0:
            npc = create_basic_goblin(position)
            npc.name = f"Goblin {i//2 + 1}"
        else:
            npc = create_forest_wolf(position)
            npc.name = f"Wolf {i//2 + 1}"

        npcs.append(npc)

    return npcs


def main():
    """Run a visual simulation example"""
    parser = argparse.ArgumentParser(
        description="MMO Simulator with Pygame Visualization"
    )
    parser.add_argument(
        "--width", type=int, default=40, help="World width (default: 40)"
    )
    parser.add_argument(
        "--height", type=int, default=40, help="World height (default: 40)"
    )
    parser.add_argument(
        "--agents", type=int, default=8, help="Number of agents (default: 8)"
    )
    parser.add_argument(
        "--npcs", type=int, default=6, help="Number of NPCs (default: 6)"
    )
    parser.add_argument(
        "--ticks", type=int, default=None, help="Max ticks (default: unlimited)"
    )
    parser.add_argument(
        "--seed", type=int, default=12345, help="World seed (default: 12345)"
    )
    parser.add_argument(
        "--no-visual", action="store_true", help="Run without visualization"
    )

    args = parser.parse_args()

    print("=== Visual MMO Simulation Example ===")
    print(f"World Size: {args.width}x{args.height}")
    print(f"Agents: {args.agents}, NPCs: {args.npcs}")
    if args.ticks:
        print(f"Max Ticks: {args.ticks}")
    else:
        print("Max Ticks: Unlimited (close window to stop)")

    # Create a temporary database for this example
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create simulation configuration
        config = SimulationConfig(
            world_width=args.width,
            world_height=args.height,
            world_seed=args.seed,
            max_ticks=args.ticks or 50000,  # Large number for "unlimited"
            database_path=db_path,
            save_interval=25,
            analytics_interval=50,
            tick_rate=10,  # 10 ticks per second for smooth visualization
            # Visualization settings
            enable_visualizer=not args.no_visual,
            visualizer_width=1200,
            visualizer_height=800,
            visualizer_tile_size=16,
            # Agent settings for interesting simulation
            default_agent_vision_range=6,
            fog_of_war_enabled=True,
        )

        print(f"Configuration: Seed={config.world_seed}, Tick Rate={config.tick_rate}")

        # Create simulation
        simulation = Simulation(config)
        simulation.initialize_simulation(
            "Visual Simulation Example",
            "A demonstration of the pygame visualizer with diverse agents and NPCs",
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

        if args.no_visual:
            print("Running without visualization (use --help to see visual options)")
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
                simulation.run(num_ticks=args.ticks or 100)

        print(
            f"\\nSimulation completed after {simulation.time_manager.current_tick} ticks"
        )

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

        print(f"\\nSimulation data saved to: {db_path}")
        print("Visual simulation example completed successfully!")

    except KeyboardInterrupt:
        print("\\nSimulation interrupted by user")
    except Exception as e:
        print(f"\\nError during simulation: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Clean up temporary database
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
