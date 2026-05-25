#!/usr/bin/env python3
"""
Complex MMO Simulation with Rich Interactions

This simulation demonstrates:
- 15-20 diverse agents with varied personalities and classes
- 10-15 NPCs (hostile enemies and neutral creatures)
- Resource gathering, crafting, trading, and combat
- Respawn system for fallen entities
- Market dynamics and economy
- Comprehensive database logging every 60 ticks (1 minute)
- Real-time visualization with pygame

Features:
- Agents gather resources (wood, stone, berries, herbs, fish)
- Agents craft items from gathered materials
- Agents trade with each other
- Combat with hostile NPCs
- Automatic respawning of defeated entities
- Persistent database for post-simulation analysis
"""

import argparse
import os
import random
import sys
import time

# Add the simulation framework to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulation_framework.src.ai.character_class import (  # noqa: E402
    get_character_class,
)
from simulation_framework.src.ai.goal import (  # noqa: E402
    CraftItemGoal,
    ExploreGoal,
    GatherResourceGoal,
    TradeGoal,
)
from simulation_framework.src.core.config import SimulationConfig  # noqa: E402
from simulation_framework.src.core.simulation import Simulation  # noqa: E402
from simulation_framework.src.entities.agent import (  # noqa: E402
    create_agent_with_archetype,
)
from simulation_framework.src.entities.npc import (  # noqa: E402
    create_basic_goblin,
    create_forest_wolf,
)


def find_valid_spawn_positions(
    world, num_positions: int, min_separation: int = 3
) -> list:
    """Find valid spawn positions that are not in water and properly separated"""
    positions = []
    max_attempts = num_positions * 20

    for _ in range(max_attempts):
        if len(positions) >= num_positions:
            break

        x = random.randint(2, world.width - 3)
        y = random.randint(2, world.height - 3)

        # Check if position is valid and passable
        if not world.is_valid_position(x, y) or not world.is_passable(x, y):
            continue

        # Check minimum separation from existing positions
        too_close = False
        for existing_x, existing_y in positions:
            if (
                abs(x - existing_x) < min_separation
                and abs(y - existing_y) < min_separation
            ):
                too_close = True
                break

        if not too_close:
            positions.append((x, y))

    # If we couldn't find enough positions, fill with fallback positions
    while len(positions) < num_positions:
        i = len(positions)
        x = (i % 6) * (world.width // 6) + (world.width // 12)
        y = (i // 6) * (world.height // 6) + (world.height // 12)
        x = max(2, min(world.width - 3, x))
        y = max(2, min(world.height - 3, y))
        positions.append((x, y))

    return positions


def create_specialized_agents(world, num_agents: int = 18) -> list:
    """Create a diverse set of specialized agents"""
    agents = []
    positions = find_valid_spawn_positions(world, num_agents, min_separation=4)

    # Define specialized roles with goals
    agent_configs = [
        # Gatherers
        {
            "name": "Woodcutter Alice",
            "archetype": "explorer",
            "class": "Hunter",
            "goals": [GatherResourceGoal("wood", 20, priority=7)],
        },
        {
            "name": "Miner Bob",
            "archetype": "warrior",
            "class": "Warrior",
            "goals": [GatherResourceGoal("stone", 15, priority=7)],
        },
        {
            "name": "Herbalist Carol",
            "archetype": "peaceful",
            "class": "Alchemist",
            "goals": [GatherResourceGoal("herbs", 10, priority=7)],
        },
        {
            "name": "Fisher Dave",
            "archetype": "curious",
            "class": "Hunter",
            "goals": [GatherResourceGoal("fish", 12, priority=6)],
        },
        # Crafters
        {
            "name": "Blacksmith Emma",
            "archetype": "crafter",
            "class": "Blacksmith",
            "goals": [
                GatherResourceGoal("iron_ore", 8),
                CraftItemGoal("Iron Sword", 1),
            ],
        },
        {
            "name": "Alchemist Frank",
            "archetype": "crafter",
            "class": "Alchemist",
            "goals": [
                GatherResourceGoal("herbs", 5),
                CraftItemGoal("Health Potion", 3),
            ],
        },
        # Traders
        {
            "name": "Merchant Grace",
            "archetype": "merchant",
            "class": "Trader",
            "goals": [TradeGoal(priority=6)],
        },
        {
            "name": "Trader Henry",
            "archetype": "social",
            "class": "Trader",
            "goals": [GatherResourceGoal("berries", 10), TradeGoal(priority=5)],
        },
        # Warriors
        {
            "name": "Warrior Ivy",
            "archetype": "aggressive",
            "class": "Warrior",
            "goals": [ExploreGoal(priority=6)],
        },
        {
            "name": "Knight Jack",
            "archetype": "warrior",
            "class": "Warrior",
            "goals": [ExploreGoal(priority=5)],
        },
        {
            "name": "Ranger Kate",
            "archetype": "warrior",
            "class": "Hunter",
            "goals": [ExploreGoal(priority=6)],
        },
        # Explorers
        {
            "name": "Explorer Leo",
            "archetype": "explorer",
            "class": "Explorer",
            "goals": [ExploreGoal(priority=8)],
        },
        {
            "name": "Scout Maya",
            "archetype": "curious",
            "class": "Explorer",
            "goals": [ExploreGoal(priority=7)],
        },
        # Mixed roles
        {
            "name": "Adventurer Noah",
            "archetype": "explorer",
            "class": "Warrior",
            "goals": [ExploreGoal(priority=5), GatherResourceGoal("wood", 5)],
        },
        {
            "name": "Survivor Olivia",
            "archetype": "peaceful",
            "class": "Hunter",
            "goals": [GatherResourceGoal("berries", 15, priority=6)],
        },
        {
            "name": "Wanderer Paul",
            "archetype": "social",
            "class": "Explorer",
            "goals": [ExploreGoal(priority=4), TradeGoal(priority=3)],
        },
        # Additional varied agents
        {
            "name": "Farmer Quinn",
            "archetype": "peaceful",
            "class": "Farmer",
            "goals": [GatherResourceGoal("berries", 20, priority=7)],
        },
        {
            "name": "Hunter Riley",
            "archetype": "aggressive",
            "class": "Hunter",
            "goals": [GatherResourceGoal("fish", 10), ExploreGoal(priority=5)],
        },
    ]

    for i, config in enumerate(agent_configs[:num_agents]):
        position = positions[i]

        # Create agent with specified archetype and class
        agent = create_agent_with_archetype(
            position=position, name=config["name"], archetype=config["archetype"]
        )

        # Set character class if specified
        if config.get("class"):
            char_class = get_character_class(config["class"])
            if char_class:
                agent.character_class = char_class

        # Add initial goals
        for goal in config.get("goals", []):
            agent.current_goals.append(goal)

        agents.append(agent)

    return agents


def create_diverse_npcs(world, num_npcs: int = 12) -> list:
    """Create a diverse set of NPCs for combat and interaction"""
    npcs = []
    positions = find_valid_spawn_positions(world, num_npcs, min_separation=5)

    # Mix of hostile and neutral NPCs
    npc_types = [
        # Hostile enemies
        ("Goblin Raider", create_basic_goblin),
        ("Goblin Warrior", create_basic_goblin),
        ("Forest Wolf", create_forest_wolf),
        ("Alpha Wolf", create_forest_wolf),
        ("Goblin Scout", create_basic_goblin),
        ("Wild Wolf", create_forest_wolf),
        # More variety
        ("Goblin Shaman", create_basic_goblin),
        ("Pack Wolf", create_forest_wolf),
        ("Goblin Archer", create_basic_goblin),
        ("Dire Wolf", create_forest_wolf),
        ("Goblin Berserker", create_basic_goblin),
        ("Shadow Wolf", create_forest_wolf),
    ]

    for i in range(min(num_npcs, len(npc_types))):
        position = positions[i]
        name, creator_func = npc_types[i]

        npc = creator_func(position)
        npc.name = name

        # Vary NPC stats for diversity
        npc.stats.max_health = npc.stats.max_health + random.randint(-10, 20)
        npc.stats.health = npc.stats.max_health
        npc.stats.attack_power = npc.stats.attack_power + random.randint(-2, 5)

        npcs.append(npc)

    return npcs


def setup_respawn_system(simulation):
    """Configure the respawn system with safe zones"""
    respawn_mgr = simulation.respawn_manager

    # Add safe spawn zones around the map
    world_w = simulation.world.width
    world_h = simulation.world.height

    # Corner safe zones
    respawn_mgr.add_safe_zone(world_w // 4, world_h // 4, 8)
    respawn_mgr.add_safe_zone(3 * world_w // 4, world_h // 4, 8)
    respawn_mgr.add_safe_zone(world_w // 4, 3 * world_h // 4, 8)
    respawn_mgr.add_safe_zone(3 * world_w // 4, 3 * world_h // 4, 8)

    # Central safe zone
    respawn_mgr.add_safe_zone(world_w // 2, world_h // 2, 10)

    # Set respawn delays
    respawn_mgr.agent_respawn_delay = 150  # Agents respawn after 150 ticks
    respawn_mgr.npc_respawn_delay = 100  # NPCs respawn after 100 ticks


def print_simulation_info(simulation, start_time):
    """Print detailed simulation information"""
    duration = time.time() - start_time
    stats = simulation.get_statistics()

    print("\n" + "=" * 60)
    print("SIMULATION COMPLETED")
    print("=" * 60)
    print(f"Total Runtime: {duration:.2f} seconds")
    print(f"Total Ticks: {stats['current_tick']}")
    print(f"Average Tick Time: {stats['average_tick_time']:.4f}s")
    print("\nEntities:")
    print(f"  Total Agents: {stats['total_agents']}")
    print(f"  Active Agents: {stats['active_agents']}")
    print(f"  Total NPCs: {stats['total_npcs']}")
    print(f"  Active NPCs: {stats['active_npcs']}")

    # Agent status summary
    print("\nAgent Status:")
    alive_count = 0
    dead_count = 0
    for agent in simulation.agents:
        if agent.stats.is_alive:
            alive_count += 1
        else:
            dead_count += 1
    print(f"  Alive: {alive_count}")
    print(f"  Dead: {dead_count}")


def inspect_database(db_path):
    """Inspect and display database contents"""
    import sqlite3

    print("\n" + "=" * 60)
    print("DATABASE INSPECTION")
    print("=" * 60)
    print(f"Database: {os.path.abspath(db_path)}")
    print(f"Size: {os.path.getsize(db_path) / 1024:.1f} KB")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [table[0] for table in cursor.fetchall()]
        print(f"\nTables: {', '.join(tables)}")

        # Row counts
        print("\nTable Row Counts:")
        for table in tables:
            if table.startswith("sqlite_"):
                continue
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count:,}")

        # Action summary
        print("\nAction Types Distribution:")
        cursor.execute("""
            SELECT action_type, COUNT(*) as count,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM action_logs
            GROUP BY action_type
            ORDER BY count DESC
            LIMIT 10
        """)
        for action_type, count, successful in cursor.fetchall():
            success_rate = (successful / count * 100) if count > 0 else 0
            print(f"  {action_type}: {count} ({success_rate:.1f}% success)")

        # Combat summary
        cursor.execute("SELECT COUNT(*) FROM combat_logs")
        combat_count = cursor.fetchone()[0]
        if combat_count > 0:
            print(f"\nCombat Events: {combat_count}")
            cursor.execute("""
                SELECT SUM(damage_dealt), AVG(damage_dealt),
                       SUM(CASE WHEN was_critical = 1 THEN 1 ELSE 0 END),
                       SUM(CASE WHEN target_died = 1 THEN 1 ELSE 0 END)
                FROM combat_logs
            """)
            total_dmg, avg_dmg, crits, kills = cursor.fetchone()
            print(f"  Total Damage: {total_dmg:,.0f}")
            print(f"  Average Damage: {avg_dmg:.1f}")
            print(f"  Critical Hits: {crits}")
            print(f"  Kills: {kills}")

        # Trade summary
        cursor.execute("SELECT COUNT(*) FROM trade_logs WHERE completed = 1")
        trade_count = cursor.fetchone()[0]
        print(f"\nCompleted Trades: {trade_count}")

        # Recent events
        print("\nRecent Events (Last 10):")
        cursor.execute("""
            SELECT tick, agent_id, action_type, success, result_message
            FROM action_logs
            ORDER BY tick DESC, id DESC
            LIMIT 10
        """)
        for tick, agent_id, action_type, success, message in cursor.fetchall():
            status = "✓" if success else "✗"
            print(f"  Tick {tick}: Agent {agent_id} - {action_type} {status}")
            if message:
                print(f"    → {message[:60]}")

        conn.close()

    except Exception as e:
        print(f"Error inspecting database: {e}")


def main():
    """Run the complex simulation"""
    parser = argparse.ArgumentParser(
        description="Complex MMO Simulation with comprehensive logging"
    )
    parser.add_argument(
        "--width", type=int, default=60, help="World width (default: 60)"
    )
    parser.add_argument(
        "--height", type=int, default=60, help="World height (default: 60)"
    )
    parser.add_argument(
        "--agents", type=int, default=18, help="Number of agents (default: 18)"
    )
    parser.add_argument(
        "--npcs", type=int, default=12, help="Number of NPCs (default: 12)"
    )
    parser.add_argument(
        "--ticks", type=int, default=180, help="Max ticks (default: 180 = 3 minutes)"
    )
    parser.add_argument("--seed", type=int, default=42, help="World seed (default: 42)")
    parser.add_argument(
        "--no-visual", action="store_true", help="Run without visualization"
    )
    parser.add_argument(
        "--db-file", type=str, default="complex_simulation.db", help="Database file"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("COMPLEX MMO SIMULATION")
    print("=" * 60)
    print(f"World Size: {args.width}x{args.height}")
    print(f"Agents: {args.agents}")
    print(f"NPCs: {args.npcs}")
    print(f"Duration: {args.ticks} ticks (~{args.ticks / 60:.1f} minutes)")
    print(f"Database: {args.db_file}")
    print("=" * 60)

    # Remove existing database
    if os.path.exists(args.db_file):
        os.remove(args.db_file)
        print("Removed existing database")

    try:
        # Create configuration with minute-based logging
        config = SimulationConfig(
            world_width=args.width,
            world_height=args.height,
            world_seed=args.seed,
            max_ticks=args.ticks,
            database_path=args.db_file,
            # Log snapshots every 60 ticks (1 simulation minute)
            save_interval=60,
            analytics_interval=60,
            # Tick rate for visualization
            tick_rate=10 if not args.no_visual else 0,
            # Visualization settings
            enable_visualizer=not args.no_visual,
            visualizer_width=1400,
            visualizer_height=900,
            visualizer_tile_size=16,
            # Agent settings
            default_agent_vision_range=8,
            fog_of_war_enabled=True,
            log_actions=True,
        )

        # Create and initialize simulation
        simulation = Simulation(config)
        simulation.initialize_simulation(
            "Complex Simulation with Rich Interactions",
            f"Comprehensive test with {args.agents} agents, {args.npcs} NPCs, "
            f"gathering, crafting, trading, and combat over {args.ticks} ticks",
        )

        print(f"\nInitialized simulation ID: {simulation.simulation_id}")

        # Setup respawn system
        setup_respawn_system(simulation)
        print("Configured respawn system with 5 safe zones")

        # Create and add agents
        print(f"\nCreating {args.agents} specialized agents...")
        agents = create_specialized_agents(simulation.world, args.agents)
        for agent in agents:
            simulation.add_agent(agent)
            goals_str = (
                ", ".join([g.name for g in agent.current_goals[:2]])
                if agent.current_goals
                else "None"
            )
            class_name = (
                agent.character_class.name if agent.character_class else "Unknown"
            )
            print(f"  + {agent.name} ({class_name}) - Goals: {goals_str}")

        # Create and add NPCs
        print(f"\nCreating {args.npcs} NPCs...")
        npcs = create_diverse_npcs(simulation.world, args.npcs)
        for npc in npcs:
            simulation.add_npc(npc)
            print(
                f"  + {npc.name} ({npc.npc_type}) - HP: {npc.stats.max_health}, ATK: {npc.stats.attack_power}"
            )

            # Schedule NPCs for respawn when they die
            # The respawn system will handle this automatically in the simulation

        print(f"\n{'=' * 60}")
        print("STARTING SIMULATION")
        print("=" * 60)

        if not args.no_visual:
            print("\nVisualization Controls:")
            print("  • Left Click + Drag: Pan map")
            print("  • Mouse Wheel: Zoom")
            print("  • Click Agent: Show details")
            print("  • ESC: Deselect")
            print("  • Close window: Stop\n")

        # Run simulation
        start_time = time.time()

        try:
            if args.no_visual:
                simulation.run(num_ticks=args.ticks)
            else:
                try:
                    simulation.run_with_visualizer(num_ticks=args.ticks)
                except ImportError as e:
                    print(f"\nVisualization unavailable: {e}")
                    print("Running headless simulation...")
                    simulation.run(num_ticks=args.ticks)
        except KeyboardInterrupt:
            print("\n\nSimulation interrupted by user")

        # Print statistics
        print_simulation_info(simulation, start_time)

        # Inspect database
        inspect_database(args.db_file)

        print("\n" + "=" * 60)
        print("SIMULATION COMPLETE")
        print("=" * 60)
        print(f"\nDatabase saved to: {os.path.abspath(args.db_file)}")
        print("\nYou can inspect the database with:")
        print(f"  sqlite3 {args.db_file}")
        print("  .tables")
        print("  SELECT * FROM action_logs LIMIT 10;")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
