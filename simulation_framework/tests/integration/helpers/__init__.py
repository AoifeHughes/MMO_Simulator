"""Test helper utilities for micro-simulation testing"""

from .simulation_test_helper import (
    create_controlled_world,
    create_test_config,
    force_agent_equipment,
    place_resource_node,
    cleanup_test_database,
    create_wall_obstacle
)
from .forced_behavior import (
    ForcedBehaviorAgent,
    ControlledNPC,
    StaticNPC,
    create_test_warrior,
    create_test_archer,
    create_test_gatherer,
    create_weak_goblin,
    create_strong_enemy
)
from .database_assertions import (
    assert_combat_occurred,
    assert_entity_died,
    assert_entity_health_changed,
    assert_resource_gathered,
    assert_movement_occurred,
    assert_action_logged,
    assert_stamina_decreased,
    assert_inventory_changed,
    get_combat_logs,
    get_action_logs
)

__all__ = [
    'create_controlled_world',
    'create_test_config',
    'force_agent_equipment',
    'place_resource_node',
    'cleanup_test_database',
    'create_wall_obstacle',
    'ForcedBehaviorAgent',
    'ControlledNPC',
    'StaticNPC',
    'create_test_warrior',
    'create_test_archer',
    'create_test_gatherer',
    'create_weak_goblin',
    'create_strong_enemy',
    'assert_combat_occurred',
    'assert_entity_died',
    'assert_entity_health_changed',
    'assert_resource_gathered',
    'assert_movement_occurred',
    'assert_action_logged',
    'assert_stamina_decreased',
    'assert_inventory_changed',
    'get_combat_logs',
    'get_action_logs'
]
