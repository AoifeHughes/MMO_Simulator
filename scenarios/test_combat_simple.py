"""
Simple Combat Test Scenario

A minimal test scenario to verify combat mechanics work correctly.
- Small 20x20 map
- Two agents spawn 3 units apart (within attack range)
- Simple behavior: detect enemy -> attack -> verify damage
"""

import logging
from typing import Any, Dict, List

from client.behavior_tree.nodes.combat_action import AttackNearestEnemy
from client.behavior_tree.nodes.base import NodeStatus
from client.behavior_tree.nodes.composite import PrioritySelector as Selector, Sequence
from client.behavior_tree.nodes.condition import EnemyInRange, HealthAboveThreshold
from client.behavior_tree.nodes.decorator import CooldownDecorator, TimerDecorator
from client.behavior_tree.nodes.dynamic_condition import DynamicEnemyInRange
from client.behavior_tree.tree import BehaviorTree
from scenarios.base_scenario import BaseScenario

logger = logging.getLogger(__name__)


class TestCombatSimpleScenario(BaseScenario):
    def __init__(self):
        from world.terrain_generator import TerrainType
        super().__init__(
            name="Test Combat Simple",
            description="Minimal combat test with agents spawning in attack range",
            terrain_type=TerrainType.GRASSLAND,  # Simple flat terrain
        )
        self.world_size = (20, 20)

    async def setup(self, server):
        """Setup the test scenario"""
        logger.info("Setting up simple combat test scenario")

        agent_configs = []

        # Spawn player at (10, 10)
        player_id = server.world.spawn_agent(
            agent_type="player",
            x=10,
            y=10,
            rotation=0
        )

        # Register the player agent so it can be found by clients
        player_agent = server.world.get_agent(player_id)
        if player_agent:
            server.agent_registry.register_agent(
                player_id, "player", player_agent.x, player_agent.y
            )
            server.ai_system.register_agent(
                player_id, "player", player_agent.x, player_agent.y
            )

        agent_configs.append({
            "id": player_id,
            "type": "player",
            "behavior": "simple_attack"
        })

        # Spawn enemy at (10, 13) - exactly 3 units away
        enemy_id = server.world.spawn_agent(
            agent_type="enemy",
            x=10,
            y=13,
            rotation=180
        )

        # Register the enemy agent so it can be found by clients
        enemy_agent = server.world.get_agent(enemy_id)
        if enemy_agent:
            server.agent_registry.register_agent(
                enemy_id, "enemy", enemy_agent.x, enemy_agent.y
            )
            server.ai_system.register_agent(
                enemy_id, "enemy", enemy_agent.x, enemy_agent.y
            )

        agent_configs.append({
            "id": enemy_id,
            "type": "enemy",
            "behavior": "simple_attack"
        })

        logger.info(f"Simple combat test scenario setup complete:")
        logger.info(f"  Player at (10, 10)")
        logger.info(f"  Enemy at (10, 13) - 3 units apart")
        logger.info(f"  Both have attack range of 1.5-3.5 units")
        logger.info(f"  Expected behavior: Immediate combat engagement")

        # Log initial health
        player = server.world.get_agent(player_id)
        enemy = server.world.get_agent(enemy_id)
        if player and enemy:
            logger.info(f"  Player health: {player.health}/{player.max_health}")
            logger.info(f"  Enemy health: {enemy.health}/{enemy.max_health}")

        return agent_configs

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Implementation of abstract method - agents already spawned in setup"""
        return []

    def get_custom_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float) -> BehaviorTree:
        """Create simple combat test behavior tree"""

        # Determine enemy types based on agent type
        if agent_type == "player":
            enemy_types = ["enemy"]
            attack_name = "punch"  # Players use punch
        elif agent_type == "enemy":
            enemy_types = ["player"]
            attack_name = "claw"  # Enemies use claw
        else:
            return None

        # Ultra-simple combat tree
        root = Sequence(
            "SimpleCombatRoot",
            [
                # Only fight if healthy
                HealthAboveThreshold(20.0),

                # Combat sequence
                Selector(
                    "CombatSelector",
                    [
                        # Try dynamic attack first (uses server data)
                        Sequence(
                            "DynamicAttack",
                            [
                                DynamicEnemyInRange(attack_name, enemy_types),
                                CooldownDecorator(
                                    "AttackCooldown",
                                    TimerDecorator(
                                        "AttackTimer",
                                        AttackNearestEnemy(
                                            attack_name=attack_name,
                                            damage=10.0,
                                            attack_range=3.5,
                                            enemy_types=enemy_types
                                        ),
                                        minimum_duration=1.0
                                    ),
                                    cooldown_duration=1.5
                                )
                            ]
                        ),

                        # Fallback to basic attack
                        Sequence(
                            "BasicAttack",
                            [
                                EnemyInRange(3.5, enemy_types),
                                CooldownDecorator(
                                    "BasicAttackCooldown",
                                    TimerDecorator(
                                        "BasicAttackTimer",
                                        AttackNearestEnemy(
                                            attack_name=attack_name,
                                            damage=10.0,
                                            attack_range=3.5,
                                            enemy_types=enemy_types
                                        ),
                                        minimum_duration=1.0
                                    ),
                                    cooldown_duration=1.5
                                )
                            ]
                        )
                    ]
                )
            ]
        )

        tree = BehaviorTree(root, f"SimpleCombatTree_{agent_type}")
        logger.info(f"Created simple combat test tree for {agent_type} at ({agent_x}, {agent_y})")
        return tree