"""
Resource gathering micro-simulation tests.
"""

from src.ai.goal import GatherResourceGoal
from src.core.simulation import Simulation

from ..helpers import (
    assert_resource_gathered,
    cleanup_test_database,
    create_controlled_world,
    create_test_config,
    create_test_gatherer,
    force_agent_equipment,
    place_resource_node,
)


class TestResourceGathering:
    """Tests that validate resource gathering behavior"""

    def test_guaranteed_wood_gathering(self):
        """Test that agent successfully gathers wood with axe"""
        config = create_test_config(world_size=5, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Wood Gathering Test")

        sim.world = create_controlled_world(5, 5, terrain="forest")

        # Place guaranteed wood resource
        place_resource_node(sim.world, 2, 2, "wood", amount=100)

        gatherer = create_test_gatherer((2, 2), "Woodcutter")
        force_agent_equipment(gatherer, "axe")

        # Force gathering goal
        gatherer.current_goals = [
            GatherResourceGoal("wood", target_quantity=5, priority=10)
        ]

        sim.add_agent(gatherer)

        # Run simulation
        sim.run(num_ticks=80)

        # Verify wood gathering logged
        assert_resource_gathered(
            sim.db, sim.simulation_id, gatherer.id, "wood", min_amount=1
        )

        cleanup_test_database(config.database_path)

    def test_mining_validation(self):
        """Test that agent successfully mines stone with pickaxe"""
        config = create_test_config(world_size=5, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Mining Test")

        sim.world = create_controlled_world(5, 5, terrain="mountain")

        # Place stone resource
        place_resource_node(sim.world, 2, 2, "stone", amount=100)

        miner = create_test_gatherer((2, 2), "Miner")
        force_agent_equipment(miner, "pickaxe")

        # Force mining goal
        miner.current_goals = [
            GatherResourceGoal("stone", target_quantity=5, priority=10)
        ]

        sim.add_agent(miner)

        # Run simulation
        sim.run(num_ticks=80)

        # Verify stone gathering logged
        assert_resource_gathered(
            sim.db, sim.simulation_id, miner.id, "stone", min_amount=1
        )

        cleanup_test_database(config.database_path)

    def test_gathering_without_tool(self):
        """Test that gathering fails without required tool"""
        config = create_test_config(world_size=5, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("No Tool Gathering Test")

        sim.world = create_controlled_world(5, 5, terrain="forest")

        # Place wood but don't give agent an axe
        place_resource_node(sim.world, 2, 2, "wood", amount=100)

        gatherer = create_test_gatherer((2, 2), "NoToolGatherer")
        # Don't equip any tool

        gatherer.current_goals = [
            GatherResourceGoal("wood", target_quantity=5, priority=10)
        ]

        sim.add_agent(gatherer)

        # Run simulation
        sim.run(num_ticks=50)

        # Verify no successful gathering (should fail or have 0 successful gathers)
        try:
            assert_resource_gathered(
                sim.db, sim.simulation_id, gatherer.id, "wood", min_amount=1
            )
            # If this passes, the test should fail
            assert False, "Expected gathering to fail without tool, but it succeeded"
        except AssertionError as e:
            # Expected - gathering should fail
            if "Expected gathering to fail" in str(e):
                raise
            # Otherwise, this is the expected assertion error from assert_resource_gathered

        cleanup_test_database(config.database_path)
