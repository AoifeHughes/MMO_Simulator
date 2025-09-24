import logging
import math
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario
from world.terrain_generator import TerrainType
from client.behavior_tree.nodes import *
from client.behavior_tree.tree import BehaviorTree
from shared.items import create_item

logger = logging.getLogger(__name__)


class DualWeaponCombatScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Dual Weapon Combat",
            description="Warriors with sword and bow vs enemies, switching weapons based on range",
            terrain_type=TerrainType.GRASSLAND,  # Open terrain for clear combat
            seed=150,  # Consistent arena layout
        )
        self.num_warriors = 2
        self.num_enemies = 4

    async def setup(self, server):
        """Setup dual weapon combat scenario"""
        self.server = server
        logger.info("Setting up dual weapon combat scenario")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn warriors and enemies"""
        agent_configs = []

        # Spawn warriors on one side (they get dual weapons)
        warrior_positions = [(40, 45), (42, 52)]
        for i in range(self.num_warriors):
            x, y = warrior_positions[i]
            rotation = 0.0  # Facing east toward enemies

            agent_config = {
                "type": "player",
                "position": (x, y),
                "name": f"Warrior_{i+1}",
            }
            agent_configs.append(agent_config)

            # Spawn warrior on server
            agent_id = self.server.world.spawn_agent("player", x, y, rotation)

            # Register agent and customize inventory
            agent_state = self.server.agent_registry.register_agent(agent_id, "player", x, y)

            # Give warrior both sword and bow (they start with sword, add bow)
            # First, ensure they have sword (they should get this from add_starting_items)
            sword = create_item("iron_sword")
            if sword:
                agent_state.inventory.add_item(sword, 1)
                agent_state.inventory.equip_item(sword.item_id)

            bow = create_item("hunters_bow")
            if bow:
                agent_state.inventory.add_item(bow, 1)

            logger.info(f"Spawned warrior {agent_id} at ({x}, {y}) with sword and bow")
            logger.info(f"Warrior weapons: {[item.name for item in agent_state.inventory.get_weapons()]}")
            logger.info(f"Warrior equipped: {[item.name for slot, item in agent_state.inventory.equipped_items.items() if item is not None]}")

        # Spawn enemies on the other side
        enemy_positions = [
            (52, 47),
            (54, 45),
            (50, 50),
            (56, 52),
        ]
        for i in range(self.num_enemies):
            x, y = enemy_positions[i]
            rotation = 180.0  # Facing west toward warriors

            agent_config = {
                "type": "enemy",
                "position": (x, y),
                "name": f"Enemy_{i+1}",
            }
            agent_configs.append(agent_config)

            # Spawn enemy on server
            agent_id = self.server.world.spawn_agent("enemy", x, y, rotation)
            agent_state = self.server.agent_registry.register_agent(agent_id, "enemy", x, y)

            logger.info(f"Spawned enemy {agent_id} at ({x}, {y})")

        # Override warrior behavior trees
        self._create_dual_weapon_trees()

        logger.info("Dual weapon combat scenario setup:")
        logger.info(f"  Warriors: {self.num_warriors} agents with sword + bow")
        logger.info(f"  Enemies: {self.num_enemies} agents with claws")
        logger.info(f"  Distance: ~8-16 units between sides")
        logger.info("  Expected behavior: Warriors switch between bow (long range) and sword (close range)")

        return agent_configs

    def _create_dual_weapon_trees(self):
        """Create behavior trees for dual weapon warriors"""
        # This would be applied when agents connect
        # For now, we store the tree configuration
        self.warrior_behavior_tree_config = {
            "type": "dual_weapon_warrior",
            "weapons": ["sword", "bow"],
            "tactics": "range_based_switching"
        }

    def _create_dual_weapon_warrior_tree(
        self, spawn_x: float, spawn_y: float, patrol_radius: float = 8.0
    ) -> BehaviorTree:
        """
        Create behavior tree for dual-weapon warrior.
        Behavior: Emergency -> Weapon Selection -> Combat -> Patrol -> Idle
        """

        # Create patrol points around spawn
        patrol_points = []
        for i in range(4):
            angle = (2 * math.pi / 4) * i
            px = spawn_x + math.cos(angle) * patrol_radius
            py = spawn_y + math.sin(angle) * patrol_radius
            patrol_points.append((px, py))

        root = PrioritySelector(
            "DualWeaponWarriorRoot",
            [
                # Priority 1: Emergency - Low health -> Flee
                Sequence(
                    "Emergency",
                    [
                        HealthBelowThreshold(20.0),
                        CooldownDecorator(
                            "EmergencyFlee",
                            TimerDecorator(
                                "FleeTimer",
                                Wander(spawn_x, spawn_y, 15.0),
                                minimum_duration=6.0,
                            ),
                            cooldown_duration=2.0,
                        ),
                    ],
                ),

                # Priority 2: Combat with weapon switching
                Sequence(
                    "CombatWithWeaponSwitching",
                    [
                        DynamicEnemyInChaseRange(20.0, ["enemy"]),
                        CooldownDecorator(
                            "CombatCooldown",
                            PrioritySelector(
                                "WeaponBasedCombat",
                                [
                                    # Long range: Use bow (3-15 units)
                                    Sequence(
                                        "BowCombat",
                                        [
                                            # Check if enemy is in bow range and we have clear shot
                                            Sequence(
                                                "BowRangeCheck",
                                                [
                                                    DynamicEnemyInRange("bow_shot", ["enemy"]),
                                                    # TODO: Add line-of-sight check
                                                ]
                                            ),
                                            # Attack with bow
                                            TimerDecorator(
                                                "BowAttackTimer",
                                                AttackWithBestWeapon(enemy_types=["enemy"]),
                                                minimum_duration=1.0,
                                            ),
                                        ],
                                    ),

                                    # Close range: Use sword (0.5-2.5 units)
                                    Sequence(
                                        "SwordCombat",
                                        [
                                            DynamicEnemyInRange("sword_slash", ["enemy"]),
                                            TimerDecorator(
                                                "SwordAttackTimer",
                                                AttackWithBestWeapon(enemy_types=["enemy"]),
                                                minimum_duration=1.0,
                                            ),
                                        ],
                                    ),

                                    # Move to optimal range
                                    PrioritySelector(
                                        "RangeManagement",
                                        [
                                            # If enemy too close for bow, back up
                                            Sequence(
                                                "BackUpForBow",
                                                [
                                                    # Custom condition: enemy closer than 3 units
                                                    CustomCondition(
                                                        lambda agent: self._enemy_too_close_for_bow(agent),
                                                        "EnemyTooCloseForBow"
                                                    ),
                                                    TimerDecorator(
                                                        "BackUpTimer",
                                                        Wander(spawn_x, spawn_y, 12.0),  # Tactical withdrawal
                                                        minimum_duration=1.0,
                                                    ),
                                                ],
                                            ),

                                            # If enemy too far for sword, close distance
                                            Sequence(
                                                "CloseForSword",
                                                [
                                                    # Custom condition: enemy farther than 2.5 but closer than 15
                                                    CustomCondition(
                                                        lambda agent: self._enemy_in_chase_range_but_far_for_sword(agent),
                                                        "EnemyInChaseRangeButFarForSword"
                                                    ),
                                                    TimerDecorator(
                                                        "ChaseTimer",
                                                        ChaseNearestEnemy(
                                                            enemy_types=["enemy"], chase_range=20.0
                                                        ),
                                                        minimum_duration=0.5,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            cooldown_duration=0.3,  # Faster combat decisions
                        ),
                    ],
                ),

                # Priority 3: Patrol when no targets
                CooldownDecorator(
                    "PatrolCooldown",
                    Patrol(patrol_points),
                    cooldown_duration=1.0,
                ),

                # Priority 4: Default idle
                Idle(2.0),
            ],
        )

        return BehaviorTree(root, "DualWeaponWarriorTree")

    def _enemy_too_close_for_bow(self, agent) -> bool:
        """Check if nearest enemy is too close for bow use (< 3 units)"""
        if not hasattr(agent, 'visible_entities'):
            return False

        nearest_enemy_distance = float('inf')
        for entity in agent.visible_entities:
            if entity.get("agent_type") == "enemy":
                distance = ((entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2) ** 0.5
                nearest_enemy_distance = min(nearest_enemy_distance, distance)

        return nearest_enemy_distance < 3.0

    def _enemy_in_chase_range_but_far_for_sword(self, agent) -> bool:
        """Check if enemy is in chase range but too far for sword (> 2.5 but < 15)"""
        if not hasattr(agent, 'visible_entities'):
            return False

        for entity in agent.visible_entities:
            if entity.get("agent_type") == "enemy":
                distance = ((entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2) ** 0.5
                if 2.5 < distance <= 15.0:
                    return True

        return False

    def get_custom_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float) -> BehaviorTree:
        """Return custom behavior tree for this scenario"""
        if agent_type == "player":  # Warriors
            return self._create_dual_weapon_warrior_tree(agent_x, agent_y)
        return None