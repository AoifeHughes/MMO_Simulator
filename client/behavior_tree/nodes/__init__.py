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
from .fishing_action import (
    FishAtWater,
    HasFishingRod,
    MoveToFishingSpot,
    WaterNearby,
    WaterDiscoveredButNotNearby,
)
from .weapon_selection import (
    AttackWithBestWeapon,
    HasWeaponForRange,
    IsInWeaponRange,
    SelectBestWeapon,
)
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
from .dynamic_condition import (
    DynamicEnemyInRange,
    DynamicEnemyInChaseRange,
    HasServerGameData,
)
from .decorator import (
    CooldownDecorator,
    InterruptibleDecorator,
    InverterDecorator,
    ProbabilityDecorator,
    RepeatDecorator,
    TimerDecorator,
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
