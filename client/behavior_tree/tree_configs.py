"""
Pre-configured behavior trees for different agent types.
These configurations replicate existing agent behaviors while
adding stability mechanisms to prevent stuttering.
"""

import math
from typing import Optional

from shared.action_constants import DISTANCES

from .nodes import *
from .nodes.fishing_action_simple import (
    FishingAction,
    FishingRodRequirement,
    WaterNearbyCondition,
)
from .nodes.wood_harvesting_action import *
from .nodes.wood_harvesting_action_simple import (
    WoodHarvestingAction,
    WoodNearbyCondition,
)
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
    Behavior: Avoid others -> Explore -> Return to base (or Fish if mode is "fishing")
    """

    if mode == "fishing":
        # Special fishing explorer behavior
        root = PrioritySelector(
            "FishingExplorerRoot",
            [
                # Priority 1: Fish at water if we're already close enough and have fishing rod
                Sequence(
                    "FishingBehavior",
                    [
                        FishingRodRequirement(),  # OOP-based fishing rod check
                        WaterNearbyCondition(
                            DISTANCES.FISHING_RANGE
                        ),  # Server-authoritative water detection
                        CooldownDecorator(
                            "FishingCooldown",
                            FishingAction(
                                DISTANCES.FISHING_RANGE
                            ),  # OOP-based fishing action with server queries
                            cooldown_duration=2.0,
                        ),
                    ],
                ),
                # Priority 2: Move to water if we know where it is but aren't close enough
                Sequence(
                    "MoveToWaterBehavior",
                    [
                        FishingRodRequirement(),  # OOP-based fishing rod check
                        WaterDiscoveredButNotNearby(
                            DISTANCES.FISHING_RANGE
                        ),  # Water is known but not fishing-close
                        CooldownDecorator(
                            "MoveToWaterCooldown",
                            TimerDecorator(
                                "MoveToWaterTimer",
                                MoveToFishingSpot(DISTANCES.FISHING_RANGE),
                                minimum_duration=2.0,
                            ),
                            cooldown_duration=1.0,
                        ),
                    ],
                ),
                # Priority 3: Explore to find water if none discovered yet
                CooldownDecorator(
                    "ExplorationCooldown",
                    TimerDecorator(
                        "ExploreTimer",
                        Explore(
                            exploration_radius, "frontier"
                        ),  # Use frontier mode for water discovery
                        minimum_duration=3.0,
                    ),
                    cooldown_duration=1.0,
                ),
                # Priority 4: Wander if stuck or need to move
                Sequence(
                    "UnstuckBehavior",
                    [
                        IsStuck(1.0, 2.0),
                        CooldownDecorator(
                            "UnstuckCooldown",
                            Wander(home_x, home_y, 15.0),
                            cooldown_duration=3.0,
                        ),
                    ],
                ),
                # Priority 5: Default idle
                Idle(1.0),
            ],
        )

        return BehaviorTree(root, "FishingExplorerTree")

    elif mode == "wood_harvesting":
        # Special wood harvesting explorer behavior
        root = PrioritySelector(
            "WoodHarvestingExplorerRoot",
            [
                # Priority 1: Harvest wood if we're already close enough
                Sequence(
                    "WoodHarvestingBehavior",
                    [
                        WoodNearbyCondition(
                            DISTANCES.WOOD_HARVESTING_RANGE
                        ),  # Server-authoritative wood detection
                        CooldownDecorator(
                            "HarvestingCooldown",
                            WoodHarvestingAction(
                                DISTANCES.WOOD_HARVESTING_RANGE
                            ),  # OOP-based wood harvesting with server queries
                            cooldown_duration=2.0,
                        ),
                    ],
                ),
                # Priority 2: Move to wood if we know where it is but aren't close enough
                Sequence(
                    "MoveToWoodBehavior",
                    [
                        WoodDiscoveredButNotNearby(
                            DISTANCES.WOOD_HARVESTING_RANGE
                        ),  # Wood is known but not harvesting-close
                        CooldownDecorator(
                            "MoveToWoodCooldown",
                            TimerDecorator(
                                "MoveToWoodTimer",
                                MoveToWoodHarvestingSpot(
                                    DISTANCES.WOOD_HARVESTING_RANGE
                                ),
                                minimum_duration=2.0,
                            ),
                            cooldown_duration=1.0,
                        ),
                    ],
                ),
                # Priority 3: Explore to find wood if none discovered yet
                CooldownDecorator(
                    "ExplorationCooldown",
                    TimerDecorator(
                        "ExploreTimer",
                        Explore(
                            exploration_radius, "frontier"
                        ),  # Use frontier mode for wood discovery
                        minimum_duration=3.0,
                    ),
                    cooldown_duration=1.0,
                ),
                # Priority 4: Wander if stuck or need to move
                Sequence(
                    "UnstuckBehavior",
                    [
                        IsStuck(1.0, 2.0),
                        CooldownDecorator(
                            "UnstuckCooldown",
                            Wander(home_x, home_y, 15.0),
                            cooldown_duration=3.0,
                        ),
                    ],
                ),
                # Priority 5: Default idle
                Idle(1.0),
            ],
        )

        return BehaviorTree(root, "WoodHarvestingExplorerTree")

    else:
        # Default exploration behavior
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
    Create behavior tree for Player agents with improved priority structure.
    Behavior: Emergency -> Combat Engagement -> Patrol -> Idle

    Key improvements:
    - Longer commitment durations to reduce flipping
    - Cleaner priority hierarchy
    - Better intention management
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
            # Priority 1: Emergency - Low health (highest priority)
            Sequence(
                "EmergencyResponse",
                [
                    HealthBelowThreshold(20.0),
                    # Use longer timer for commitment to emergency behavior
                    TimerDecorator(
                        "EmergencyCommitment",
                        CooldownDecorator(
                            "EmergencyFlee",
                            Wander(spawn_x, spawn_y, 15.0),
                            cooldown_duration=1.0,  # Reduced internal cooldown
                        ),
                        minimum_duration=8.0,  # Longer commitment to fleeing
                    ),
                ],
            ),
            # Priority 2: Combat Engagement (only if healthy)
            Sequence(
                "CombatEngagement",
                [
                    # Must be healthy enough to fight
                    HealthAboveThreshold(25.0),  # Hysteresis with emergency
                    DynamicEnemyInChaseRange(20.0, ["enemy"]),
                    # Combat state machine with commitment
                    TimerDecorator(
                        "CombatCommitment",
                        PrioritySelector(
                            "CombatStateMachine",
                            [
                                # State 1: Attack if in range
                                Sequence(
                                    "AttackState",
                                    [
                                        DynamicEnemyInRange("sword_slash", ["enemy"]),
                                        CooldownDecorator(
                                            "AttackExecution",
                                            AttackNearestEnemy(
                                                attack_name="sword_slash",
                                                damage=15.0,
                                                attack_range=2.5,
                                                enemy_types=["enemy"],
                                            ),
                                            cooldown_duration=1.2,  # Attack cooldown
                                        ),
                                    ],
                                ),
                                # State 2: Chase to get in range
                                CooldownDecorator(
                                    "ChaseExecution",
                                    ChaseNearestEnemy(
                                        enemy_types=["enemy"], chase_range=20.0
                                    ),
                                    cooldown_duration=0.3,  # Faster chase updates
                                ),
                            ],
                        ),
                        minimum_duration=3.0,  # Commit to combat for 3 seconds minimum
                    ),
                ],
            ),
            # Priority 3: Patrol (peaceful behavior)
            CooldownDecorator(
                "PatrolBehavior",
                TimerDecorator(
                    "PatrolCommitment",
                    Patrol(patrol_points),
                    minimum_duration=4.0,  # Commit to patrol route
                ),
                cooldown_duration=2.0,
            ),
            # Priority 4: Idle (lowest priority fallback)
            TimerDecorator(
                "IdleCommitment",
                Idle(3.0),  # Longer idle periods
                minimum_duration=2.0,
            ),
        ],
    )

    return BehaviorTree(root, "ImprovedPlayerTree")


def create_enemy_tree(
    spawn_x: float, spawn_y: float, patrol_radius: float = 10.0
) -> BehaviorTree:
    """
    Create behavior tree for Enemy agents with improved aggression and commitment.
    Behavior: Hunt players -> Combat -> Patrol -> Idle

    Key improvements:
    - More aggressive hunting behavior
    - Better commitment to combat once engaged
    - Longer pursuit range for enemies
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
            # Priority 1: Aggressive hunting and combat
            Sequence(
                "AggressiveHunt",
                [
                    DynamicEnemyInChaseRange(18.0, ["player"]),  # Longer pursuit range
                    # Combat commitment - stick with it once engaged
                    TimerDecorator(
                        "CombatCommitment",
                        PrioritySelector(
                            "CombatStateMachine",
                            [
                                # State 1: Claw attack if in range
                                Sequence(
                                    "ClawAttackState",
                                    [
                                        DynamicEnemyInRange("claw", ["player"]),
                                        CooldownDecorator(
                                            "ClawAttackExecution",
                                            AttackNearestEnemy(
                                                attack_name="claw",
                                                damage=12.0,
                                                attack_range=1.8,
                                                enemy_types=["player"],
                                            ),
                                            cooldown_duration=0.9,  # Slightly faster attacks
                                        ),
                                    ],
                                ),
                                # State 2: Aggressive pursuit
                                ChaseNearestEnemy(
                                    enemy_types=["player"],
                                    chase_range=18.0,  # Extended chase range
                                ),
                            ],
                        ),
                        minimum_duration=4.0,  # Longer combat commitment than players
                    ),
                ],
            ),
            # Priority 2: Patrol when no players detected
            CooldownDecorator(
                "HuntPatrol",
                TimerDecorator(
                    "PatrolCommitment",
                    Patrol(patrol_points),
                    minimum_duration=3.0,  # Shorter patrol commitment (ready to hunt)
                ),
                cooldown_duration=1.5,
            ),
            # Priority 3: Alert idle (scanning for targets)
            TimerDecorator(
                "AlertIdle",
                Idle(2.0),  # Shorter idle periods
                minimum_duration=1.0,
            ),
        ],
    )

    return BehaviorTree(root, "ImprovedEnemyTree")


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
