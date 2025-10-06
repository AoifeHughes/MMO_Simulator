#!/usr/bin/env python3
"""
Basic simulation example demonstrating core functionality.

This example shows how to:
1. Create a simulation configuration
2. Initialize a simulation
3. Create and add agents with different character classes
4. Run the simulation for a specified duration
5. Extract statistics and analytics
"""

import os
import tempfile

from src.ai.character_class import get_character_class
from src.ai.goal import ExploreGoal, GatherResourceGoal
from src.ai.personality import Personality
from src.core.config import SimulationConfig
from src.core.simulation import Simulation
from src.entities.agent import Agent
from src.entities.npc import NPC


def main():
    """Run a basic simulation example"""
    print("=== Basic Simulation Example ===")

    # Create a temporary database for this example
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Create simulation configuration
        config = SimulationConfig(
            world_width=30,
            world_height=30,
            world_seed=12345,
            max_ticks=100,
            database_path=db_path,
            save_interval=10,
            analytics_interval=20,
            tick_rate=0,  # Run as fast as possible
        )

        print(
            f"Configuration: {config.world_width}x{config.world_height} world, max {config.max_ticks} ticks"
        )

        # Create simulation
        simulation = Simulation(config)
        simulation.initialize_simulation(
            "Basic Example", "A simple demonstration of the simulation framework"
        )

        print(f"Initialized simulation with ID: {simulation.simulation_id}")

        # Create diverse agents
        agents = [
            Agent(
                position=(5, 5),
                name="Explorer Alice",
                personality=Personality.randomize(),
                character_class=get_character_class("Explorer"),
            ),
            Agent(
                position=(25, 5),
                name="Warrior Bob",
                personality=Personality.randomize(),
                character_class=get_character_class("Warrior"),
            ),
            Agent(
                position=(5, 25),
                name="Explorer Carol",
                personality=Personality.randomize(),
                character_class=get_character_class("Explorer"),
            ),
            Agent(
                position=(25, 25),
                name="Warrior Dave",
                personality=Personality.randomize(),
                character_class=get_character_class("Warrior"),
            ),
        ]

        # Give agents goals and add to simulation
        for i, agent in enumerate(agents):
            if i % 2 == 0:
                agent.current_goals = [ExploreGoal()]
                print(f"Added {agent.name} with exploration goal")
            else:
                agent.current_goals = [
                    GatherResourceGoal(resource_type="wood", target_quantity=5)
                ]
                print(f"Added {agent.name} with wood gathering goal")

            simulation.add_agent(agent)

        # Add some NPCs for interaction
        npcs = [
            NPC(position=(15, 10), name="Forest Goblin", npc_type="goblin"),
            NPC(position=(10, 15), name="Wild Wolf", npc_type="wolf"),
            NPC(position=(20, 20), name="Cave Goblin", npc_type="goblin"),
        ]

        for npc in npcs:
            simulation.add_npc(npc)
            print(f"Added NPC: {npc.name}")

        print(
            f"\nStarting simulation with {len(agents)} agents and {len(npcs)} NPCs..."
        )

        # Run simulation
        simulation.run(num_ticks=50)

        print(
            f"Simulation completed after {simulation.time_manager.current_tick} ticks"
        )

        # Display statistics
        stats = simulation.get_statistics()
        print("\n=== Simulation Statistics ===")
        print(f"Total Agents: {stats['total_agents']}")
        print(f"Active Agents: {stats['active_agents']}")
        print(f"Total NPCs: {stats['total_npcs']}")
        print(f"Active NPCs: {stats['active_npcs']}")
        print(f"Average Tick Time: {stats['average_tick_time']:.4f}s")

        # Display analytics report
        report = simulation.get_analytics_report()
        if report:
            print("\n=== Analytics Report ===")
            if "population_metrics" in report:
                pop_metrics = report["population_metrics"]
                print(
                    f"Population Growth Rate: {pop_metrics.get('growth_rate', 0):.2%}"
                )
                print(f"Population Density: {pop_metrics.get('density', 0):.2f}")

        # Show agent status
        print("\n=== Agent Status ===")
        for agent in simulation.agents:
            print(
                f"{agent.name}: Health {agent.stats.health}/{agent.stats.max_health}, "
                f"Position {agent.position}"
            )

        print(f"\nSimulation data saved to database: {db_path}")
        print("Example completed successfully!")

    finally:
        # Clean up temporary database
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
