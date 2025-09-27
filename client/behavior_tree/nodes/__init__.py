"""
Behavior tree node implementations
"""

from .action import (
    Attack,
    Explore,
    Flee,
    Idle,
    MoveToEntity,
    MoveToTarget,
    Patrol,
    Wander,
)
from .base import (
    ActionNode,
    BehaviorNode,
    CompositeNode,
    ConditionNode,
    DecoratorNode,
    NodeStatus,
)
from .combat_action import AttackNearestEnemy, ChaseNearestEnemy
from .composite import Parallel, PrioritySelector, Sequence
from .condition import (
    CustomCondition,
    DistanceToTarget,
    EnemyInRange,
    HasTarget,
    HealthAboveThreshold,
    HealthBelowThreshold,
    IsAgentType,
    IsIdle,
    IsStuck,
    NearOtherAgent,
    PathExists,
    TargetVisible,
    TimeSinceLastAction,
)
from .decorator import (
    CooldownDecorator,
    InterruptibleDecorator,
    InverterDecorator,
    ProbabilityDecorator,
    RepeatDecorator,
    TimerDecorator,
)
from .dynamic_condition import (
    DynamicEnemyInChaseRange,
    DynamicEnemyInRange,
    HasServerGameData,
)
from .fishing_action import (
    FishAtWater,
    HasFishingRod,
    MoveToFishingSpot,
    WaterDiscoveredButNotNearby,
    WaterNearby,
)
from .personality_condition import (
    PersonalityActivityMotivation,
    PersonalityArchetypeMatch,
    PersonalityCompatibility,
    PersonalityCondition,
    PersonalityPriorityCondition,
    high_combat_drive,
    high_exploration_drive,
    high_social_desire,
    low_risk_tolerance,
    motivated_to_explore,
    motivated_to_fish,
    prefers_combat_over_exploration,
)
from .weapon_selection import (
    AttackWithBestWeapon,
    HasWeaponForRange,
    IsInWeaponRange,
    SelectBestWeapon,
)

__all__ = [
    # Base classes
    "BehaviorNode",
    "CompositeNode",
    "DecoratorNode",
    "ConditionNode",
    "ActionNode",
    "NodeStatus",
    # Composite nodes
    "PrioritySelector",
    "Sequence",
    "Parallel",
    # Decorator nodes
    "CooldownDecorator",
    "TimerDecorator",
    "RepeatDecorator",
    "InverterDecorator",
    "ProbabilityDecorator",
    "InterruptibleDecorator",
    # Condition nodes
    "HealthBelowThreshold",
    "HealthAboveThreshold",
    "EnemyInRange",
    "DistanceToTarget",
    "TargetVisible",
    "PathExists",
    "TimeSinceLastAction",
    "IsAgentType",
    "HasTarget",
    "IsStuck",
    "IsIdle",
    "NearOtherAgent",
    "CustomCondition",
    # Personality condition nodes
    "PersonalityCondition",
    "PersonalityPriorityCondition",
    "PersonalityActivityMotivation",
    "PersonalityCompatibility",
    "PersonalityArchetypeMatch",
    "high_combat_drive",
    "high_exploration_drive",
    "low_risk_tolerance",
    "high_social_desire",
    "prefers_combat_over_exploration",
    "motivated_to_fish",
    "motivated_to_explore",
    # Dynamic condition nodes (use server data)
    "DynamicEnemyInRange",
    "DynamicEnemyInChaseRange",
    "HasServerGameData",
    # Action nodes
    "MoveToTarget",
    "MoveToEntity",
    "Patrol",
    "Wander",
    "Attack",
    "Idle",
    "Flee",
    "Explore",
    "AttackNearestEnemy",
    "ChaseNearestEnemy",
    # Fishing nodes
    "FishAtWater",
    "HasFishingRod",
    "MoveToFishingSpot",
    "WaterNearby",
    "WaterDiscoveredButNotNearby",
    # Weapon selection nodes
    "AttackWithBestWeapon",
    "HasWeaponForRange",
    "IsInWeaponRange",
    "SelectBestWeapon",
]
