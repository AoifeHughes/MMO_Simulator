"""Test helper utilities for micro-simulation testing"""

from .database_assertions import (
    assert_action_logged,
    assert_combat_occurred,
    assert_entity_died,
    assert_entity_health_changed,
    assert_inventory_changed,
    assert_movement_occurred,
    assert_resource_gathered,
    assert_stamina_decreased,
    get_action_logs,
    get_combat_logs,
)
from .forced_behavior import (
    ControlledNPC,
    ForcedBehaviorAgent,
    StaticNPC,
    create_strong_enemy,
    create_test_archer,
    create_test_gatherer,
    create_test_warrior,
    create_weak_goblin,
)
from .simulation_test_helper import (
    cleanup_test_database,
    create_controlled_world,
    create_test_config,
    create_wall_obstacle,
    force_agent_equipment,
    place_resource_node,
)

__all__ = [
    "create_controlled_world",
    "create_test_config",
    "force_agent_equipment",
    "place_resource_node",
    "cleanup_test_database",
    "create_wall_obstacle",
    "ForcedBehaviorAgent",
    "ControlledNPC",
    "StaticNPC",
    "create_test_warrior",
    "create_test_archer",
    "create_test_gatherer",
    "create_weak_goblin",
    "create_strong_enemy",
    "assert_combat_occurred",
    "assert_entity_died",
    "assert_entity_health_changed",
    "assert_resource_gathered",
    "assert_movement_occurred",
    "assert_action_logged",
    "assert_stamina_decreased",
    "assert_inventory_changed",
    "get_combat_logs",
    "get_action_logs",
]
