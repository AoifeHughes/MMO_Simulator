#!/usr/bin/env python3
"""
Quick 2-minute verification test to check if our fixes work.
"""

import sys
import os
import time

# Add the simulation framework to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from simulation_framework.src.core.simulation import Simulation
from simulation_framework.src.core.config import SimulationConfig
from simulation_framework.src.entities.agent import Agent, create_agent_with_archetype
from simulation_framework.src.entities.npc import NPC, create_basic_goblin, create_forest_wolf
from simulation_framework.src.ai.personality import Personality
from simulation_framework.src.ai.character_class import get_character_class
from simulation_framework.src.ai.goal import ExploreGoal, GatherResourceGoal, AttackEnemyGoal


def main():
    """Run quick verification test"""
    print("=== VERIFICATION TEST (2 MINUTES) ===")
    print("Testing our combat and resource gathering fixes...")

    db_path = "/Users/aoife/git/MMO_Simulator/simulation_data.db"

    # Quick test configuration
    config = SimulationConfig(
        world_width=20,
        world_height=20,
        world_seed=12345,
        max_ticks=999999,
        database_path=db_path,
        save_interval=10,
        analytics_interval=25,
        tick_rate=0
    )

    simulation = Simulation(config)
    simulation.initialize_simulation(
        name="Verification Test",
        description="2-minute test to verify combat and resource gathering fixes"
    )

    print(f"Simulation ID: {simulation.simulation_id}")

    # Create fewer agents for focused testing
    agents = []
    for i in range(8):
        x = 5 + (i % 4) * 3
        y = 5 + (i // 4) * 3

        try:
            agent = create_agent_with_archetype(
                position=(x, y),
                name=f"TestAgent_{i+1:02d}",
                archetype=["aggressive", "curious"][i % 2]
            )
        except:
            agent = Agent(
                position=(x, y),
                name=f"TestAgent_{i+1:02d}",
                personality=Personality.randomize(),
                character_class=get_character_class("Warrior" if i % 2 == 0 else "Explorer")
            )

        # Mix of goals to test different systems
        if i % 3 == 0:
            agent.current_goals = [GatherResourceGoal(resource_type="wood", target_quantity=3, priority=7)]
        elif i % 3 == 1:
            agent.current_goals = [GatherResourceGoal(resource_type="stone", target_quantity=2, priority=7)]
        else:
            agent.current_goals = [ExploreGoal(priority=5)]

        agents.append(agent)
        simulation.add_agent(agent)

    print(f"Added {len(agents)} test agents")

    # Create aggressive NPCs for combat testing
    npcs = []
    for i in range(6):
        x = 10 + (i % 3) * 2
        y = 10 + (i // 3) * 2

        try:
            if i % 2 == 0:
                npc = create_basic_goblin((x, y))
                npc.name = f"TestGoblin_{i+1:02d}"
            else:
                npc = create_forest_wolf((x, y))
                npc.name = f"TestWolf_{i+1:02d}"
        except:
            npc = NPC(position=(x, y), name=f"TestNPC_{i+1:02d}", npc_type="goblin")

        # Make all NPCs aggressive for testing
        npc.npc_type = "aggressive"
        npc.aggro_range = 4
        print(f"Created aggressive {npc.name} with aggro range {npc.aggro_range}")

        npcs.append(npc)
        simulation.add_npc(npc)

    print(f"Added {len(npcs)} aggressive NPCs")

    # Run for 2 minutes
    print("\n=== RUNNING 2-MINUTE VERIFICATION TEST ===")
    simulation.running = True
    start_time = time.time()
    target_duration = 2 * 60  # 2 minutes

    step_count = 0
    try:
        while time.time() - start_time < target_duration and simulation.running:
            simulation.step()
            step_count += 1

            if step_count % 500 == 0:
                elapsed = time.time() - start_time
                print(f"  Step {step_count}, {elapsed:.1f}s elapsed...")

    except Exception as e:
        print(f"Error during simulation: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if simulation.running:
            simulation.stop_simulation()

    elapsed_time = time.time() - start_time
    final_stats = simulation.get_statistics()

    print(f"\n=== VERIFICATION RESULTS ===")
    print(f"Runtime: {elapsed_time:.1f} seconds")
    print(f"Total ticks: {final_stats['current_tick']}")
    print(f"Active agents: {final_stats['active_agents']}/{final_stats['total_agents']}")
    print(f"Active NPCs: {final_stats['active_npcs']}/{final_stats['total_npcs']}")

    print("\nVerification complete! Run analyze_simulation_results.py to check if fixes worked.")


if __name__ == "__main__":
    main()