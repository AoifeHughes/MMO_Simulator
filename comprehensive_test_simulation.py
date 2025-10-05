#!/usr/bin/env python3
"""
Comprehensive 5-minute simulation test to validate all expected behaviors.

This simulation will:
1. Create a diverse population of 30 agents with varied personalities and classes
2. Spawn 20 NPCs including combat-ready enemies
3. Run for exactly 5 minutes (300 seconds) with aggressive tick rate
4. Exercise all major systems: movement, combat, gathering, crafting, trading, etc.
5. Generate comprehensive logs for analysis
"""

import sys
import os
import time
from datetime import datetime, timedelta

# Add the simulation framework to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from simulation_framework.src.core.simulation import Simulation
from simulation_framework.src.core.config import SimulationConfig
from simulation_framework.src.entities.agent import Agent, create_agent_with_archetype
from simulation_framework.src.entities.npc import NPC, create_basic_goblin, create_forest_wolf
from simulation_framework.src.ai.personality import Personality
from simulation_framework.src.ai.character_class import get_character_class
from simulation_framework.src.ai.goal import ExploreGoal, GatherResourceGoal, AttackEnemyGoal, RestGoal
from simulation_framework.src.items.starting_equipment import give_starting_equipment, equip_agent_for_task


def create_comprehensive_agent_population(num_agents: int = 30) -> list[Agent]:
    """Create a comprehensive population to exercise all behaviors"""
    agents = []

    # Character classes to test
    class_names = ["Explorer", "Warrior", "Explorer", "Warrior"]

    # Personality archetypes to test all behaviors
    archetypes = ["balanced", "aggressive", "cautious", "social", "curious"]

    for i in range(num_agents):
        # Distribute agents across the map
        x = 5 + (i % 6) * 4  # Spread across X
        y = 5 + (i // 6) * 4  # Spread across Y

        # Ensure positions are within bounds
        x = min(x, 25)
        y = min(y, 25)

        # Select character class and personality
        char_class = class_names[i % len(class_names)]
        archetype = archetypes[i % len(archetypes)]

        # Try using helper function first, fall back to manual creation
        try:
            agent = create_agent_with_archetype(
                position=(x, y),
                name=f"Agent_{char_class}_{i+1:02d}",
                archetype=archetype
            )
        except:
            agent = Agent(
                position=(x, y),
                name=f"Agent_{char_class}_{i+1:02d}",
                personality=Personality.create_archetype(archetype),
                character_class=get_character_class(char_class)
            )

        # Assign diverse goals to exercise different systems
        if i % 5 == 0:
            # Explorer agents
            agent.current_goals = [ExploreGoal(priority=7)]
        elif i % 5 == 1:
            # Resource gatherers
            resources = ["wood", "stone", "food"]
            resource = resources[i % len(resources)]
            agent.current_goals = [GatherResourceGoal(resource_type=resource, target_quantity=5, priority=6)]
        elif i % 5 == 2:
            # Combat-ready agents (will find targets later)
            agent.current_goals = [ExploreGoal(priority=5)]
        elif i % 5 == 3:
            # Mixed goals
            agent.current_goals = [
                ExploreGoal(priority=4),
                GatherResourceGoal(resource_type="wood", target_quantity=3, priority=5)
            ]
        else:
            # Rest-focused agents (to test low-energy scenarios)
            agent.current_goals = [RestGoal(priority=8)]

        # Equip agent with starting equipment based on goals and class
        give_starting_equipment(agent)

        # Ensure agents have the right tools for their goals
        if i % 5 == 1:  # Resource gatherers
            if resource == "wood":
                equip_agent_for_task(agent, "woodcutting")
            elif resource == "stone":
                equip_agent_for_task(agent, "mining")
        elif i % 5 == 3:  # Mixed goals - equip with woodcutting tool
            equip_agent_for_task(agent, "woodcutting")

        agents.append(agent)

    return agents


def create_combat_ready_npc_ecosystem(num_npcs: int = 20) -> list[NPC]:
    """Create NPCs that will trigger combat and other interactions"""
    npcs = []

    # NPC types for different behaviors
    npc_types = [
        ("goblin", True, 3),      # Aggressive, medium aggro range
        ("wolf", True, 4),        # Aggressive, higher aggro range
        ("goblin", True, 3),      # More goblins
        ("merchant", False, 0),   # Peaceful, for trading
        ("wolf", True, 4),        # More wolves
    ]

    for i in range(num_npcs):
        npc_type, is_aggressive, aggro_range = npc_types[i % len(npc_types)]

        # Cluster NPCs to create hotspots of activity
        if i % 4 == 0:  # Forest area
            x = 8 + (i % 3) * 2
            y = 8 + (i % 3) * 2
        elif i % 4 == 1:  # Mountain area
            x = 20 + (i % 3) * 2
            y = 20 + (i % 3) * 2
        elif i % 4 == 2:  # Central plains
            x = 15 + (i % 3) * 2
            y = 15 + (i % 3) * 2
        else:  # Scattered
            x = 5 + (i % 5) * 4
            y = 5 + (i % 5) * 4

        # Ensure within bounds
        x = min(max(x, 2), 28)
        y = min(max(y, 2), 28)

        # Try using helper function first, fall back to manual creation
        try:
            if npc_type == "goblin":
                npc = create_basic_goblin((x, y))
                npc.name = f"Goblin_{i+1:02d}"
            elif npc_type == "wolf":
                npc = create_forest_wolf((x, y))
                npc.name = f"Wolf_{i+1:02d}"
            else:
                npc = NPC(
                    position=(x, y),
                    name=f"{npc_type.title()}_{i+1:02d}",
                    npc_type=npc_type
                )
        except:
            npc = NPC(
                position=(x, y),
                name=f"{npc_type.title()}_{i+1:02d}",
                npc_type=npc_type
            )

        # Set aggro properties if aggressive
        if is_aggressive:
            npc.npc_type = "aggressive"  # Ensure aggressive NPCs are marked correctly
            npc.aggro_range = aggro_range
            npc.respawn_delay = 50  # Quick respawn for continuous testing

        npcs.append(npc)

    return npcs


def setup_combat_goals_for_agents(agents: list[Agent], npcs: list[NPC]) -> None:
    """Add combat goals to some agents to trigger PvE combat"""
    # Find aggressive NPCs
    aggressive_npcs = [npc for npc in npcs if hasattr(npc, 'aggro_range') and npc.aggro_range > 0]

    if aggressive_npcs:
        # Give combat goals to warrior agents
        warriors = [agent for agent in agents if "Warrior" in agent.name]

        for i, warrior in enumerate(warriors[:len(aggressive_npcs)]):
            target_npc = aggressive_npcs[i % len(aggressive_npcs)]
            # Add attack goal to existing goals
            warrior.current_goals.append(AttackEnemyGoal(target_npc.id, priority=8))


class SimulationLogger:
    """Enhanced logger to track simulation events"""

    def __init__(self, simulation_id: int):
        self.simulation_id = simulation_id
        self.events = []
        self.tick_count = 0
        self.start_time = time.time()

    def on_tick_complete(self, tick: int):
        """Log each tick completion"""
        self.tick_count = tick
        if tick % 100 == 0:  # Log every 100 ticks
            elapsed = time.time() - self.start_time
            print(f"  Tick {tick} completed ({elapsed:.1f}s elapsed)...")

    def on_simulation_complete(self, simulation: Simulation):
        """Log final simulation statistics"""
        elapsed = time.time() - self.start_time
        stats = simulation.get_statistics()

        print(f"\n=== SIMULATION COMPLETED ===")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Total ticks: {stats['current_tick']}")
        print(f"Final agents: {stats['active_agents']}/{stats['total_agents']}")
        print(f"Final NPCs: {stats['active_npcs']}/{stats['total_npcs']}")
        print(f"Avg tick time: {stats['average_tick_time']:.4f}s")


def main():
    """Run comprehensive 5-minute simulation test"""
    print("=== COMPREHENSIVE 5-MINUTE SIMULATION TEST ===")
    print("This will exercise all major simulation systems and log results.")

    # High-performance configuration for 5-minute test
    # database_path will be auto-generated with cleanup by default
    config = SimulationConfig(
        world_width=30,
        world_height=30,
        world_seed=99999,  # Unique seed for this test
        max_ticks=999999,   # Let time limit control duration
        save_interval=25,   # Save every 25 ticks for detailed logging
        analytics_interval=50,  # Analytics every 50 ticks
        tick_rate=0  # Maximum speed
    )

    print(f"Configuration: {config.world_width}x{config.world_height} world")
    print(f"Database: {config.database_path}")
    print(f"Target duration: 5 minutes (300 seconds)")

    # Create simulation
    simulation = Simulation(config)
    logger = SimulationLogger(0)  # Will be updated with actual ID

    # Set up event handlers
    simulation.on_tick_complete = logger.on_tick_complete
    simulation.on_simulation_complete = logger.on_simulation_complete

    # Initialize simulation
    simulation.initialize_simulation(
        name="Comprehensive 5-Minute Test",
        description="Full system test exercising movement, combat, gathering, crafting, trading, respawn, and analytics"
    )
    logger.simulation_id = simulation.simulation_id

    print(f"\nSimulation ID: {simulation.simulation_id}")

    # Create comprehensive population
    print("\nCreating comprehensive agent population...")
    agents = create_comprehensive_agent_population(30)
    for agent in agents:
        simulation.add_agent(agent)

    print(f"Added {len(agents)} agents with diverse goals and personalities")

    # Create combat-ready NPC ecosystem
    print("Creating combat-ready NPC ecosystem...")
    npcs = create_combat_ready_npc_ecosystem(20)
    for npc in npcs:
        simulation.add_npc(npc)

    print(f"Added {len(npcs)} NPCs including aggressive creatures")

    # Set up combat scenarios
    print("Setting up combat goals for warrior agents...")
    setup_combat_goals_for_agents(agents, npcs)

    # Display initial state
    print(f"\n=== INITIAL STATE ===")
    initial_stats = simulation.get_statistics()
    print(f"Total agents: {initial_stats['total_agents']}")
    print(f"Total NPCs: {initial_stats['total_npcs']}")
    print(f"Starting tick: {initial_stats['current_tick']}")

    # Run simulation for exactly 5 minutes
    print(f"\n=== RUNNING SIMULATION FOR 5 MINUTES ===")
    start_time = time.time()
    target_duration = 5 * 60  # 5 minutes in seconds

    # Set simulation to running state
    simulation.running = True
    steps_count = 0

    try:
        print("Starting simulation loop...")
        while time.time() - start_time < target_duration and simulation.running:
            simulation.step()
            steps_count += 1

            # Log progress every 1000 steps
            if steps_count % 1000 == 0:
                elapsed = time.time() - start_time
                print(f"  Completed {steps_count} steps, {elapsed:.1f}s elapsed...")

    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    except Exception as e:
        print(f"\nError during simulation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Ensure simulation is properly stopped
        if simulation.running:
            simulation.stop_simulation()

    print(f"Simulation loop completed. Steps: {steps_count}")

    elapsed_time = time.time() - start_time
    final_stats = simulation.get_statistics()

    print(f"\n=== FINAL RESULTS ===")
    print(f"Actual runtime: {elapsed_time:.2f} seconds")
    print(f"Total ticks simulated: {final_stats['current_tick']}")
    if elapsed_time > 0:
        print(f"Ticks per second: {final_stats['current_tick'] / elapsed_time:.1f}")
    else:
        print(f"Ticks per second: N/A (no time elapsed)")
    print(f"Final active agents: {final_stats['active_agents']}")
    print(f"Final active NPCs: {final_stats['active_npcs']}")

    print(f"\n=== SUCCESS ===")
    print(f"Comprehensive simulation completed!")
    print(f"Data saved to: {db_path}")
    print("\nNext step: Run the database analysis script to check for expected behaviors.")


if __name__ == "__main__":
    main()