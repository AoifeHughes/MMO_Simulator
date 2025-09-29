#!/usr/bin/env python3
"""
Advanced simulation scenario demonstrating complex interactions.

This example shows:
1. Large-scale simulation with many agents
2. Advanced event handling and condition-based simulation
3. Real-time monitoring with callbacks
4. Analytics and reporting
5. Pause/resume functionality
"""

import tempfile
import os
import random
from typing import Dict, Any
from src.core.simulation import Simulation
from src.core.config import SimulationConfig
from src.entities.agent import Agent
from src.entities.npc import NPC
from src.ai.personality import Personality
from src.ai.character_class import get_character_class
from src.ai.goal import ExploreGoal, GatherResourceGoal


class SimulationMonitor:
    """Monitor simulation progress and events"""

    def __init__(self):
        self.tick_log = []
        self.events = []

    def on_tick_complete(self, tick: int):
        """Called after each simulation tick"""
        self.tick_log.append(tick)
        if tick % 10 == 0:
            print(f"  Tick {tick} completed...")

    def on_simulation_complete(self, simulation: Simulation):
        """Called when simulation completes"""
        stats = simulation.get_statistics()
        self.events.append(f"Simulation completed after {stats['current_tick']} ticks")
        print(f"Final statistics: {stats}")


def create_diverse_population(num_agents: int = 20) -> list[Agent]:
    """Create a diverse population of agents"""
    agents = []

    # Character class distribution
    class_names = ["Explorer", "Warrior", "Explorer", "Warrior", "Explorer"]  # More explorers
    archetype_names = [
        "balanced",
        "aggressive",
        "cautious",
        "social",
        "curious"
    ]

    for i in range(num_agents):
        # Random spawn position
        x = random.randint(2, 28)
        y = random.randint(2, 28)

        # Select character class and personality
        char_class = class_names[i % len(class_names)]
        archetype = archetype_names[i % len(archetype_names)]

        # Create agent
        agent = Agent(
            position=(x, y),
            name=f"Agent_{i+1:02d}",
            personality=Personality.create_archetype(archetype),
            character_class=get_character_class(char_class)
        )

        # Assign varied goals based on personality
        if archetype == "curious":
            agent.current_goals = [ExploreGoal()]
        elif archetype == "aggressive":
            agent.current_goals = [ExploreGoal()]  # Would use attack goals if we had targets
        else:
            if random.random() < 0.6:
                agent.current_goals = [ExploreGoal()]
            else:
                resource_type = random.choice(["wood", "stone", "food"])
                agent.current_goals = [GatherResourceGoal(resource_type=resource_type, target_quantity=3)]

        agents.append(agent)

    return agents


def create_npc_ecosystem(num_npcs: int = 15) -> list[NPC]:
    """Create a diverse NPC ecosystem"""
    npcs = []
    npc_types = ["goblin", "wolf", "goblin", "wolf", "goblin"]  # More goblins

    for i in range(num_npcs):
        # Cluster NPCs in certain areas
        if i % 3 == 0:  # Forest cluster
            x = random.randint(5, 12)
            y = random.randint(5, 12)
        elif i % 3 == 1:  # Mountain cluster
            x = random.randint(18, 25)
            y = random.randint(18, 25)
        else:  # Scattered
            x = random.randint(3, 27)
            y = random.randint(3, 27)

        npc_type = npc_types[i % len(npc_types)]
        npc = NPC(
            position=(x, y),
            name=f"{npc_type.title()}_{i+1:02d}",
            npc_type=npc_type
        )
        npcs.append(npc)

    return npcs


def main():
    """Run an advanced simulation scenario"""
    print("=== Advanced Simulation Scenario ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        # Advanced configuration
        config = SimulationConfig(
            world_width=30,
            world_height=30,
            world_seed=54321,
            max_ticks=200,
            database_path=db_path,
            save_interval=5,  # More frequent saves
            analytics_interval=10,  # More frequent analytics
            tick_rate=0  # Maximum speed
        )

        print(f"World: {config.world_width}x{config.world_height}, Seed: {config.world_seed}")

        # Create simulation and monitor
        simulation = Simulation(config)
        monitor = SimulationMonitor()

        # Set up event handlers
        simulation.on_tick_complete = monitor.on_tick_complete
        simulation.on_simulation_complete = monitor.on_simulation_complete

        simulation.initialize_simulation(
            "Advanced Scenario",
            "Complex simulation demonstrating large-scale multi-agent interactions"
        )

        # Create large population
        print("\nCreating diverse population...")
        agents = create_diverse_population(25)
        for agent in agents:
            simulation.add_agent(agent)

        print(f"Added {len(agents)} agents with diverse personalities and goals")

        # Create NPC ecosystem
        print("Creating NPC ecosystem...")
        npcs = create_npc_ecosystem(18)
        for npc in npcs:
            simulation.add_npc(npc)

        print(f"Added {len(npcs)} NPCs forming an ecosystem")

        # Phase 1: Initial exploration
        print("\n=== Phase 1: Initial Exploration (50 ticks) ===")
        simulation.run(num_ticks=50)

        stats = simulation.get_statistics()
        print(f"Phase 1 complete. Active agents: {stats['active_agents']}, Active NPCs: {stats['active_npcs']}")

        # Pause and analyze
        simulation.pause_simulation()
        print("\nSimulation paused for mid-run analysis...")

        # Show agent distribution
        agent_positions = [(agent.position[0], agent.position[1]) for agent in simulation.agents if agent.stats.is_alive()]
        print(f"Agent positions: {len(agent_positions)} active agents spread across the world")

        # Phase 2: Continue with condition monitoring
        print("\n=== Phase 2: Continuing with Condition Monitoring ===")
        simulation.resume_simulation()

        # Define stopping condition: run until specific tick or low population
        def stopping_condition(sim):
            stats = sim.get_statistics()
            # Stop if population drops significantly or we reach tick 120
            return (stats['active_agents'] < len(agents) * 0.5 or
                   sim.time_manager.current_tick >= 120)

        print("Running until stopping condition met...")
        simulation.run_until(stopping_condition)

        # Final analysis
        final_stats = simulation.get_statistics()
        print(f"\n=== Final Results ===")
        print(f"Total ticks: {final_stats['current_tick']}")
        print(f"Final active agents: {final_stats['active_agents']}/{final_stats['total_agents']}")
        print(f"Final active NPCs: {final_stats['active_npcs']}/{final_stats['total_npcs']}")
        print(f"Average tick time: {final_stats['average_tick_time']:.4f}s")

        # Generate comprehensive analytics report
        print("\n=== Analytics Report ===")
        report = simulation.get_analytics_report()
        if report:
            for category, metrics in report.items():
                if isinstance(metrics, dict):
                    print(f"\n{category.replace('_', ' ').title()}:")
                    for key, value in metrics.items():
                        if isinstance(value, float):
                            print(f"  {key}: {value:.3f}")
                        else:
                            print(f"  {key}: {value}")

        # Show survival statistics
        print(f"\n=== Survival Statistics ===")
        survivors = [agent for agent in simulation.agents if agent.stats.is_alive()]
        casualties = len(simulation.agents) - len(survivors)

        print(f"Survivors: {len(survivors)}")
        print(f"Casualties: {casualties}")

        if survivors:
            print("Surviving agents:")
            for agent in survivors[:5]:  # Show first 5
                health_pct = (agent.stats.health / agent.stats.max_health) * 100
                print(f"  {agent.name}: {health_pct:.0f}% health at {agent.position}")

        print(f"\n=== Event Log ===")
        print(f"Monitored {len(monitor.tick_log)} ticks")
        for event in monitor.events:
            print(f"  {event}")

        print(f"\nAdvanced scenario completed! Data saved to: {db_path}")

    finally:
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()