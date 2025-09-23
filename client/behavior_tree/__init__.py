"""
Behavior Tree System for MMO Simulator Agents

This module provides a comprehensive behavior tree system for creating
stable, responsive AI agents that don't suffer from stuttering or
rapid action switching.

Key Features:
- Built-in stability mechanisms (cooldowns, timers)
- Hierarchical priority system
- Easy to extend and configure
- Performance monitoring and debugging tools
- Unified decision-making framework

Usage:
    from client.behavior_tree import BehaviorTree, BehaviorTreeBuilder
    from client.behavior_tree.nodes import *

    # Create a simple behavior tree
    tree = BehaviorTreeBuilder() \
        .priority_selector("MainSelector") \
        .condition(EnemyInRange(10.0)) \
        .action(Attack("enemy_id")) \
        .action(Patrol(waypoints)) \
        .build("ExampleTree")

    # Use in agent update loop
    status = tree.update(agent, delta_time)
"""

from .tree import BehaviorTree, BehaviorTreeBuilder
from .nodes import *

__version__ = "1.0.0"

__all__ = [
    'BehaviorTree',
    'BehaviorTreeBuilder',
    # Re-export all node types from nodes module
    'BehaviorNode', 'CompositeNode', 'DecoratorNode', 'ConditionNode', 'ActionNode', 'NodeStatus',
    'PrioritySelector', 'Sequence', 'Parallel',
    'CooldownDecorator', 'TimerDecorator', 'RepeatDecorator',
    'InverterDecorator', 'ProbabilityDecorator', 'InterruptibleDecorator',
    'HealthBelowThreshold', 'HealthAboveThreshold', 'EnemyInRange', 'DistanceToTarget',
    'TargetVisible', 'PathExists', 'TimeSinceLastAction', 'IsAgentType', 'HasTarget',
    'IsStuck', 'IsIdle', 'NearOtherAgent', 'CustomCondition',
    'MoveToTarget', 'MoveToEntity', 'Patrol', 'Wander', 'Attack', 'Idle', 'Flee', 'Explore',
]