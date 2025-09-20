#!/usr/bin/env python3
"""
MMO Simulation Engine
Main entry point demonstrating the game systems
"""

import time
import random
import logging
import sys
from typing import List
import threading

from src.engine.game import Game, GameConfig
from src.agents.agent import Agent
from src.agents.npc import NPC, NPCRole
from src.agents.enemy import Enemy, EnemyType
from src.world.world import Vector2
from src.world.objects import (
    GameObject, Container, ResourceNode, Portal,
    Item, Weapon, Armor, ItemRarity, ItemType,
    Terrain, TerrainType
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MMOSimulation:
    """Main simulation class that sets up and runs the MMO world"""

    def __init__(self):
        self.game = Game(GameConfig(
            target_fps=60,
            agent_update_interval=0.5,
            request_resolution_interval=0.1
        ))
        self.running = False

    def setup_world(self):
        """Populate the world with entities"""
        logger.info("Setting up MMO world...")

        # Add terrain features
        self._create_terrain()

        # Add NPCs
        self._create_npcs()

        # Add enemies
        self._create_enemies()

        # Add agents with diverse personalities
        self._create_agents(50)  # Create 50 intelligent agents

        # Add world objects
        self._create_world_objects()

        logger.info("World setup complete!")

    def _create_terrain(self):
        """Create terrain features"""
        terrains = [
            Terrain(TerrainType.FOREST, Vector2(2000, 1500), Vector2(800, 800)),
            Terrain(TerrainType.MOUNTAIN, Vector2(3500, 2000), Vector2(1000, 1000)),
            Terrain(TerrainType.SWAMP, Vector2(1500, 3000), Vector2(600, 600)),
        ]

        for terrain in terrains:
            self.game.world.terrain[terrain.id] = terrain

    def _create_npcs(self):
        """Create NPCs in the world"""
        npcs = [
            NPC("Marcus the Merchant", NPCRole.MERCHANT, Vector2(1100, 1100)),
            NPC("Elder Sage", NPCRole.QUEST_GIVER, Vector2(1200, 1000)),
            NPC("Captain Rex", NPCRole.TRAINER, Vector2(1000, 1200)),
            NPC("Guard Tom", NPCRole.GUARD, Vector2(900, 1000)),
            NPC("Guard Sarah", NPCRole.GUARD, Vector2(1100, 900)),
            NPC("Wanderer Jim", NPCRole.WANDERER, Vector2(1300, 1300)),
            NPC("Blacksmith Joe", NPCRole.BLACKSMITH, Vector2(1050, 1150)),
        ]

        for npc in npcs:
            self.game.world.add_npc(npc)

    def _create_enemies(self):
        """Create enemies in different areas"""
        # Starting area - weak enemies
        for i in range(10):
            pos = Vector2(
                random.uniform(800, 1300),
                random.uniform(800, 1300)
            )
            enemy = Enemy(f"Goblin_{i}", EnemyType.NORMAL, level=random.randint(1, 5), position=pos)
            self.game.world.add_enemy(enemy)

        # Forest area - medium enemies
        for i in range(8):
            pos = Vector2(
                random.uniform(2000, 2800),
                random.uniform(1500, 2300)
            )
            enemy = Enemy(f"Wolf_{i}", EnemyType.NORMAL, level=random.randint(10, 20), position=pos)
            self.game.world.add_enemy(enemy)

        # Add some elite enemies
        elite_positions = [
            Vector2(2400, 1900),
            Vector2(3600, 2100),
        ]
        for i, pos in enumerate(elite_positions):
            enemy = Enemy(f"Elite_Guardian_{i}", EnemyType.ELITE, level=25, position=pos)
            self.game.world.add_enemy(enemy)

        # Add a boss
        boss = Enemy("Dragon Lord", EnemyType.BOSS, level=50, position=Vector2(4000, 2500))
        self.game.world.add_enemy(boss)

    def _create_agents(self, count: int):
        """Create intelligent agents with varied personalities"""
        agent_classes = ["Warrior", "Mage", "Ranger", "Rogue", "Cleric"]

        for i in range(count):
            agent = Agent(f"Agent_{i:03d}")

            # Randomize personality
            agent.personality.randomize()

            # Assign class
            agent.character_class = random.choice(agent_classes)

            # Set level (some variation in starting levels)
            agent.level = random.randint(1, 10)

            # Random starting position in safe zone
            agent.position = Vector2(
                random.uniform(900, 1200),
                random.uniform(900, 1200)
            )

            # Give starting equipment
            if random.random() > 0.5:
                weapon = Weapon(
                    f"Starter {agent.character_class} Weapon",
                    "sword" if agent.character_class == "Warrior" else "staff",
                    damage=10 + agent.level,
                    rarity=ItemRarity.COMMON
                )
                agent.inventory.append(weapon)
                agent.equipment['weapon'] = weapon

            # Add some initial knowledge
            initial_knowledge = [
                {
                    'type': 'area_info',
                    'content': 'Starting zone is safe for low levels',
                    'confidence': 1.0
                },
                {
                    'type': 'enemy_weakness',
                    'content': 'Goblins are weak to fire',
                    'confidence': 0.7
                }
            ]
            agent.memory.knowledge_base.extend(initial_knowledge)

            self.game.world.add_agent(agent)

        logger.info(f"Created {count} agents with diverse personalities")

    def _create_world_objects(self):
        """Create interactive objects in the world"""
        # Resource nodes
        resource_positions = [
            (Vector2(1400, 1100), "ore"),
            (Vector2(1500, 1200), "wood"),
            (Vector2(2100, 1600), "herb"),
            (Vector2(2200, 1700), "ore"),
        ]

        for pos, resource_type in resource_positions:
            node = ResourceNode(f"{resource_type}_node", pos, resource_type)
            self.game.world.add_object(node)

        # Containers with loot
        chest = Container("Treasure Chest", Vector2(1250, 1250))
        chest.locked = True
        chest.lock_difficulty = 15

        # Add items to chest
        chest.add_item(Weapon("Magic Sword", "sword", 25, ItemRarity.RARE))
        chest.add_item(Item("Health Potion", ItemType.CONSUMABLE, ItemRarity.COMMON))

        self.game.world.add_object(chest)

        # Portals
        portal = Portal(
            "Forest Portal",
            Vector2(1500, 1000),
            "dark_forest",
            Vector2(2000, 1500)
        )
        self.game.world.add_object(portal)

    def run(self):
        """Run the simulation"""
        self.running = True

        # Start game in a separate thread
        game_thread = threading.Thread(target=self.game.start)
        game_thread.daemon = True
        game_thread.start()

        logger.info("MMO Simulation started! Press Ctrl+C to stop.")

        # Main monitoring loop
        try:
            last_stats_time = time.time()
            while self.running:
                current_time = time.time()

                # Print statistics every 5 seconds
                if current_time - last_stats_time >= 5.0:
                    self._print_statistics()
                    last_stats_time = current_time

                time.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("Stopping simulation...")
            self.stop()

    def _print_statistics(self):
        """Print current game statistics"""
        stats = self.game.get_stats()
        world_stats = stats.get('world_stats', {})

        print("\n" + "="*50)
        print("MMO SIMULATION STATISTICS")
        print("="*50)
        print(f"Game Tick: {stats['current_tick']}")
        print(f"Target FPS: {stats['target_fps']}")
        print(f"Running: {stats['running']}, Paused: {stats['paused']}")
        print("-"*50)
        print(f"Agents: {world_stats.get('total_agents', 0)}")
        print(f"NPCs: {world_stats.get('total_npcs', 0)}")
        print(f"Enemies: {world_stats.get('total_enemies', 0)}")
        print(f"Objects: {world_stats.get('total_objects', 0)}")
        print(f"Pending Requests: {stats.get('pending_requests', 0)}")

        # Sample agent status
        if self.game.world.agents:
            sample_agent = list(self.game.world.agents.values())[0]
            agent_info = sample_agent.get_info()
            print("-"*50)
            print("Sample Agent Status:")
            print(f"  Name: {agent_info['name']}")
            print(f"  Level: {agent_info['level']}")
            print(f"  State: {agent_info['state']}")
            print(f"  Health: {agent_info['health']}")
            print(f"  Position: {agent_info['position']}")

        # Request manager statistics
        if self.game.request_manager:
            req_stats = self.game.request_manager.get_statistics()
            print("-"*50)
            print("Request Processing:")
            print(f"  Total Processed: {req_stats['total_processed']}")
            print(f"  Pending: {req_stats['pending']}")
            print(f"  Failed: {req_stats['failed']}")

            if req_stats['by_type']:
                print("  By Type:")
                for req_type, count in req_stats['by_type'].items():
                    print(f"    {req_type.value}: {count}")

        print("="*50)

    def stop(self):
        """Stop the simulation"""
        self.running = False
        self.game.stop()
        logger.info("Simulation stopped.")


def main():
    """Main entry point"""
    print("""
    ╔══════════════════════════════════════════╗
    ║     MMO SIMULATION ENGINE v1.0           ║
    ║                                          ║
    ║  Intelligent Agent-Based MMO World       ║
    ║  With Emergent Behaviors                 ║
    ╚══════════════════════════════════════════╝
    """)

    simulation = MMOSimulation()
    simulation.setup_world()
    simulation.run()


if __name__ == "__main__":
    main()