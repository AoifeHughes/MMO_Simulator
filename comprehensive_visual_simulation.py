#!/usr/bin/env python3
"""
Visual version of the comprehensive 5-minute simulation test.

This provides the same comprehensive testing as comprehensive_test_simulation.py
but with real-time pygame visualization so you can watch the simulation unfold.
"""

import sys
import os
import time
import tempfile

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


def create_comprehensive_agent_population_visual(num_agents: int = 30) -> list[Agent]:
    """Create a comprehensive population to exercise all behaviors (same as original)"""
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


def create_combat_ready_npc_ecosystem_visual(num_npcs: int = 20) -> list[NPC]:
    """Create NPCs that will trigger combat and other interactions (same as original)"""
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


def setup_combat_goals_for_agents_visual(agents: list[Agent], npcs: list[NPC]) -> None:
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


def main():
    """Run comprehensive visual simulation"""
    print("=== COMPREHENSIVE VISUAL SIMULATION ===")
    print("This will run the comprehensive test with pygame visualization!")

    try:
        # Visual simulation configuration
        # database_path will be auto-generated with cleanup by default
        config = SimulationConfig(
            world_width=30,
            world_height=30,
            world_seed=99999,  # Same seed as comprehensive test
            max_ticks=50000,   # 5+ minutes at 10 TPS
            save_interval=25,
            analytics_interval=50,
            tick_rate=10,  # 10 TPS for smooth visualization

            # Visualization settings
            enable_visualizer=True,
            visualizer_width=1400,  # Larger window for better view
            visualizer_height=1000,
            visualizer_tile_size=18,  # Bigger tiles for detail

            # Enhanced visual features
            default_agent_vision_range=6,
            fog_of_war_enabled=True
        )

        db_path = config.database_path  # Get the auto-generated path
        print(f"Configuration: {config.world_width}x{config.world_height} world")
        print(f"Database: {db_path}")
        print(f"Visualization: {config.visualizer_width}x{config.visualizer_height}")

        # Create simulation
        simulation = Simulation(config)
        simulation.initialize_simulation(
            name="Visual Comprehensive Test",
            description="Full system test with visual interface - combat, gathering, crafting, trading, respawn, analytics"
        )

        print(f"\nSimulation ID: {simulation.simulation_id}")

        # Create comprehensive population
        print("\nCreating comprehensive agent population...")
        agents = create_comprehensive_agent_population_visual(30)
        for agent in agents:
            simulation.add_agent(agent)

        print(f"Added {len(agents)} agents with diverse goals and personalities")

        # Create combat-ready NPC ecosystem
        print("Creating combat-ready NPC ecosystem...")
        npcs = create_combat_ready_npc_ecosystem_visual(20)
        for npc in npcs:
            simulation.add_npc(npc)

        print(f"Added {len(npcs)} NPCs including aggressive creatures")

        # Set up combat scenarios
        print("Setting up combat goals for warrior agents...")
        setup_combat_goals_for_agents_visual(agents, npcs)

        # Display initial state
        print(f"\n=== INITIAL STATE ===")
        initial_stats = simulation.get_statistics()
        print(f"Total agents: {initial_stats['total_agents']}")
        print(f"Total NPCs: {initial_stats['total_npcs']}")
        print(f"Starting tick: {initial_stats['current_tick']}")

        # Visual controls
        print(f"\n=== VISUAL CONTROLS ===")
        print("• Left Click + Drag: Pan around the map")
        print("• Mouse Wheel: Zoom in/out")
        print("• Click on Agent: Show detailed information")
        print("• Space: Center camera on first agent")
        print("• ESC: Deselect agent")
        print("• Close window: Stop simulation")

        # Run visual simulation
        print(f"\n=== STARTING VISUAL SIMULATION ===")
        print("Watch the comprehensive test unfold in real-time!")

        try:
            simulation.run_with_visualizer(num_ticks=None)  # Run until window closed
        except ImportError as e:
            print(f"\nVisualization failed: {e}")
            print("Make sure pygame is installed: pip install pygame>=2.0.0")
            return
        except KeyboardInterrupt:
            print("\nSimulation interrupted by user")

        final_stats = simulation.get_statistics()

        print(f"\n=== FINAL RESULTS ===")
        print(f"Total ticks: {final_stats['current_tick']}")
        print(f"Final active agents: {final_stats['active_agents']}")
        print(f"Final active NPCs: {final_stats['active_npcs']}")

        print(f"\n=== SUCCESS ===")
        print(f"Visual comprehensive simulation completed!")
        print(f"Data saved to: {db_path}")

    except Exception as e:
        print(f"Error during visual simulation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Keep the database for analysis
        print(f"\nDatabase saved permanently at: {db_path}")
        print("You can now run: python analyze_simulation_results.py")


if __name__ == "__main__":
    main()