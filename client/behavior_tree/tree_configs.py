"""
Pre-configured behavior trees for different agent types.
These configurations replicate existing agent behaviors while
adding stability mechanisms to prevent stuttering.
"""

import math
from typing import Optional

from .nodes import *
from .tree import BehaviorTree


def create_npc_tree(
    home_x: float, home_y: float, wander_radius: float = 15.0
) -> BehaviorTree:
    """
    Create behavior tree for NPC agents.
    Behavior: Idle -> Wander -> React to players
    """

    # Create the tree structure
    root = PrioritySelector(
        "NPCRoot",
        [
            # React to nearby players (wave)
            Sequence(
                "PlayerReaction",
                [
                    NearOtherAgent(["player"], 5.0),
                    CooldownDecorator(
                        "WaveCooldown",
                        Idle(1.0),  # Simple reaction - just pause briefly
                        cooldown_duration=3.0,
                    ),
                ],
            ),
            # Wander behavior with stability
            CooldownDecorator(
                "WanderCooldown",
                TimerDecorator(
                    "WanderTimer",
                    Wander(home_x, home_y, wander_radius),
                    minimum_duration=2.0,
                ),
                cooldown_duration=1.0,
            ),
            # Default idle behavior
            TimerDecorator("IdleTimer", Idle(2.0), minimum_duration=1.0),
        ],
    )

    return BehaviorTree(root, "NPCTree")


def create_explorer_tree(
    home_x: float,
    home_y: float,
    exploration_radius: float = 30.0,
    mode: str = "frontier",
) -> BehaviorTree:
    """
    Create behavior tree for Explorer agents.
    Behavior: Avoid others -> Explore -> Return to base
    """

    root = PrioritySelector(
        "ExplorerRoot",
        [
            # Main exploration behavior
            CooldownDecorator(
                "ExploreCooldown",
                TimerDecorator(
                    "ExploreTimer",
                    Explore(exploration_radius, mode),
                    minimum_duration=3.0,
                ),
                cooldown_duration=2.0,
            ),
            # Recovery behavior when stuck
            Sequence(
                "UnstuckBehavior",
                [
                    IsStuck(1.0, 2.0),
                    CooldownDecorator(
                        "UnstuckCooldown",
                        Wander(home_x, home_y, 10.0),
                        cooldown_duration=3.0,
                    ),
                ],
            ),
            # Default idle
            Idle(1.0),
        ],
    )

    return BehaviorTree(root, "ExplorerTree")


def create_player_tree(
    spawn_x: float, spawn_y: float, patrol_radius: float = 8.0
) -> BehaviorTree:
    """
    Create behavior tree for Player agents.
    Behavior: Emergency -> Combat -> Patrol -> Idle
    """

    # Create patrol points around spawn
    patrol_points = []
    for i in range(4):
        angle = (2 * math.pi / 4) * i
        px = spawn_x + math.cos(angle) * patrol_radius
        py = spawn_y + math.sin(angle) * patrol_radius
        patrol_points.append((px, py))

    root = PrioritySelector(
        "PlayerRoot",
        [
            # Emergency: Low health -> Flee
            Sequence(
                "Emergency",
                [
                    HealthBelowThreshold(20.0),
                    CooldownDecorator(
                        "EmergencyFlee",
                        TimerDecorator(
                            "FleeTimer",
                            Wander(spawn_x, spawn_y, 15.0),  # Move around spawn area
                            minimum_duration=6.0,  # Increased for tactical consistency
                        ),
                        cooldown_duration=2.0,  # Reduced to allow re-evaluation
                    ),
                ],
            ),
            # Combat: Enemy nearby -> Chase and attack
            Sequence(
                "Combat",
                [
                    EnemyInRange(20.0, ["enemy"]),
                    CooldownDecorator(
                        "CombatCooldown",
                        PrioritySelector(
                            "CombatActions",
                            [
                                # Attack if close enough (matches server sword_slash range)
                                Sequence(
                                    "AttackSequence",
                                    [
                                        EnemyInRange(2.5, ["enemy"]),
                                        TimerDecorator(
                                            "AttackTimer",
                                            AttackNearestEnemy(
                                                attack_name="sword_slash",
                                                damage=15.0,  # Legacy fallback
                                                attack_range=2.5,  # Match server definition
                                                enemy_types=["enemy"],
                                            ),
                                            minimum_duration=1.0,
                                        ),
                                    ],
                                ),
                                # Otherwise chase (more responsive timing)
                                TimerDecorator(
                                    "ChaseTimer",
                                    ChaseNearestEnemy(
                                        enemy_types=["enemy"], chase_range=20.0
                                    ),
                                    minimum_duration=0.2,
                                ),
                            ],
                        ),
                        cooldown_duration=0.5,
                    ),
                ],
            ),
            # Patrol behavior
            CooldownDecorator(
                "PatrolCooldown",
                Patrol(patrol_points),
                cooldown_duration=1.0,
            ),
            # Default idle
            Idle(2.0),
        ],
    )

    return BehaviorTree(root, "PlayerTree")


def create_enemy_tree(
    spawn_x: float, spawn_y: float, patrol_radius: float = 10.0
) -> BehaviorTree:
    """
    Create behavior tree for Enemy agents.
    Behavior: Hunt players -> Combat -> Patrol -> Idle
    """

    # Create patrol points around spawn
    patrol_points = []
    for i in range(3):
        angle = (2 * math.pi / 3) * i
        px = spawn_x + math.cos(angle) * patrol_radius
        py = spawn_y + math.sin(angle) * patrol_radius
        patrol_points.append((px, py))

    root = PrioritySelector(
        "EnemyRoot",
        [
            # Hunt and combat - highest priority
            Sequence(
                "HuntCombat",
                [
                    EnemyInRange(15.0, ["player"]),
                    CooldownDecorator(
                        "HuntCooldown",
                        PrioritySelector(
                            "HuntActions",
                            [
                                # Attack if in range (matches server claw range)
                                Sequence(
                                    "AttackSequence",
                                    [
                                        EnemyInRange(1.8, ["player"]),
                                        TimerDecorator(
                                            "AttackTimer",
                                            AttackNearestEnemy(
                                                attack_name="claw",
                                                damage=12.0,  # Legacy fallback
                                                attack_range=1.8,  # Match server definition
                                                enemy_types=["player"],
                                            ),
                                            minimum_duration=0.8,
                                        ),
                                    ],
                                ),
                                # Chase if farther away (more responsive timing)
                                TimerDecorator(
                                    "ChaseTimer",
                                    ChaseNearestEnemy(
                                        enemy_types=["player"], chase_range=15.0
                                    ),
                                    minimum_duration=0.2,
                                ),
                            ],
                        ),
                        cooldown_duration=0.5,
                    ),
                ],
            ),
            # Patrol when no targets
            CooldownDecorator(
                "PatrolCooldown",
                Patrol(patrol_points),
                cooldown_duration=1.0,
            ),
            # Default idle
            Idle(1.5),
        ],
    )

    return BehaviorTree(root, "EnemyTree")


class TreeFactory:
    """Factory class for creating behavior trees for different agent types"""

    @staticmethod
    def create_tree_for_agent_type(
        agent_type: str, agent_x: float, agent_y: float, **kwargs
    ) -> Optional[BehaviorTree]:
        """
        Create a behavior tree appropriate for the given agent type.

        Args:
            agent_type: Type of agent ("npc", "explorer", "player", "enemy")
            agent_x: Agent's spawn X position
            agent_y: Agent's spawn Y position
            **kwargs: Additional parameters for specific agent types

        Returns:
            BehaviorTree instance or None if agent type not recognized
        """

        if agent_type == "npc":
            wander_radius = kwargs.get("wander_radius", 15.0)
            return create_npc_tree(agent_x, agent_y, wander_radius)

        elif agent_type == "explorer":
            exploration_radius = kwargs.get("exploration_radius", 30.0)
            mode = kwargs.get("exploration_mode", "frontier")
            return create_explorer_tree(agent_x, agent_y, exploration_radius, mode)

        elif agent_type == "player":
            patrol_radius = kwargs.get("patrol_radius", 8.0)
            return create_player_tree(agent_x, agent_y, patrol_radius)

        elif agent_type == "enemy":
            patrol_radius = kwargs.get("patrol_radius", 10.0)
            return create_enemy_tree(agent_x, agent_y, patrol_radius)

        else:
            return None

    @staticmethod
    def create_custom_tree(tree_config: dict) -> Optional[BehaviorTree]:
        """
        Create a behavior tree from a configuration dictionary.
        Allows for runtime customization of behavior trees.

        Args:
            tree_config: Dictionary describing the tree structure

        Returns:
            BehaviorTree instance or None if config is invalid
        """
        # This would be implemented later for advanced customization
        # For now, return None to indicate not implemented
        return None
