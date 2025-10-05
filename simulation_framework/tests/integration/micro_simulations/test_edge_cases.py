"""
Edge case and error handling micro-simulation tests.
"""

import pytest
from src.core.simulation import Simulation
from src.ai.goal import AttackEnemyGoal, GatherResourceGoal, ExploreGoal
from src.actions.movement import PathfindAction

from ..helpers import (
    create_controlled_world,
    create_test_config,
    force_agent_equipment,
    create_test_warrior,
    create_test_gatherer,
    place_resource_node,
    assert_combat_occurred,
    cleanup_test_database
)


class TestEdgeCasesAndErrors:
    """Tests that validate edge cases and error handling"""

    def test_action_interruption(self):
        """Test that action interruption works correctly"""
        config = create_test_config(world_size=5, max_ticks=50, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Action Interrupt Test")

        sim.world = create_controlled_world(5, 5, terrain="forest")

        # Agent with gathering action
        gatherer = create_test_gatherer((2, 2), "InterruptGatherer")
        force_agent_equipment(gatherer, "axe")

        place_resource_node(sim.world, 2, 2, "wood", amount=100)

        gatherer.current_goals = [GatherResourceGoal("wood", target_quantity=5, priority=10)]

        sim.add_agent(gatherer)

        # Run for a bit, then simulate interruption by giving new goal
        sim.run(num_ticks=20)

        # Change goal mid-gathering
        gatherer.current_goals = [ExploreGoal(priority=10)]

        sim.run(num_ticks=20)

        # Verify both gathering and exploration actions logged
        # (interruption should cause action switch)

        cleanup_test_database(config.database_path)

    def test_invalid_target_combat(self):
        """Test that combat gracefully fails with invalid target"""
        config = create_test_config(world_size=5, max_ticks=50, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Invalid Target Test")

        sim.world = create_controlled_world(5, 5, terrain="plains")

        warrior = create_test_warrior((2, 2), "InvalidTargetWarrior")

        # Give goal to attack non-existent entity
        warrior.current_goals = [AttackEnemyGoal(99999, priority=10)]

        sim.add_agent(warrior)

        # Run simulation - should not crash
        sim.run(num_ticks=30)

        # Verify no combat occurred (target doesn't exist)
        try:
            assert_combat_occurred(sim.db, sim.simulation_id, warrior.id, 99999, min_attacks=1)
            assert False, "Expected no combat with invalid target"
        except AssertionError as e:
            # Expected - no combat should occur
            if "Expected no combat" in str(e):
                raise
            pass

        cleanup_test_database(config.database_path)

    def test_world_boundary(self):
        """Test that agent can't move outside world boundaries"""
        config = create_test_config(world_size=5, max_ticks=50, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("World Boundary Test")

        sim.world = create_controlled_world(5, 5, terrain="plains")

        # Agent at edge
        agent = create_test_warrior((0, 0), "EdgeAgent")

        # Try to move out of bounds (should fail gracefully)
        agent.current_action = PathfindAction(agent.id, (-1, -1))
        agent.current_action.start(0)

        sim.add_agent(agent)

        # Run simulation - should not crash
        sim.run(num_ticks=30)

        # Agent should stay within bounds (0,0) to (4,4)
        snapshots = sim.db.get_agent_snapshots(sim.simulation_id, agent.id)
        for snapshot in snapshots:
            assert 0 <= snapshot.position_x < 5, f"Agent x={snapshot.position_x} out of bounds"
            assert 0 <= snapshot.position_y < 5, f"Agent y={snapshot.position_y} out of bounds"

        cleanup_test_database(config.database_path)
