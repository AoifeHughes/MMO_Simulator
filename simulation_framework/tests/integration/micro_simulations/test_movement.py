"""
Movement and pathfinding micro-simulation tests.
"""

from src.ai.goal import ExploreGoal
from src.core.simulation import Simulation

from ..helpers import (
    assert_movement_occurred,
    assert_stamina_decreased,
    cleanup_test_database,
    create_controlled_world,
    create_test_config,
    create_test_warrior,
)


class TestMovementAndPathfinding:
    """Tests that validate movement and pathfinding behavior"""

    def test_direct_movement(self):
        """Test that agent moves directly to target position"""
        config = create_test_config(world_size=10, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Direct Movement Test")

        sim.world = create_controlled_world(10, 10, terrain="plains")

        agent = create_test_warrior((0, 0), "MovingAgent")

        # Give exploration goal to trigger movement
        agent.current_goals = [ExploreGoal(priority=10)]

        sim.add_agent(agent)

        # Run simulation
        sim.run(num_ticks=50)

        # Verify movement occurred (exploration causes wandering)
        assert_movement_occurred(sim.db, sim.simulation_id, agent.id)

        cleanup_test_database(config.database_path)

    def test_obstacle_navigation(self):
        """Test that agent navigates around obstacles"""
        config = create_test_config(world_size=10, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Obstacle Navigation Test")

        sim.world = create_controlled_world(10, 10, terrain="plains")

        # Create wall obstacle
        for y in range(10):
            if y != 5:  # Leave gap at y=5
                tile = sim.world.get_tile(5, y)
                tile.properties.passable = False

        agent = create_test_warrior((2, 5), "NavigatingAgent")

        # Give exploration goal to trigger movement
        agent.current_goals = [ExploreGoal(priority=10)]

        sim.add_agent(agent)

        # Run simulation
        sim.run(num_ticks=80)

        # Verify agent moved (exploration should cause wandering/pathfinding)
        assert_movement_occurred(sim.db, sim.simulation_id, agent.id)

        cleanup_test_database(config.database_path)

    def test_movement_stamina_cost(self):
        """Test that movement consumes stamina correctly"""
        config = create_test_config(world_size=10, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Movement Stamina Test")

        sim.world = create_controlled_world(10, 10, terrain="plains")

        agent = create_test_warrior((0, 0), "StaminaTestAgent")
        agent.stats.stamina = 100

        # Give exploration goal to trigger wandering
        agent.current_goals = [ExploreGoal(priority=10)]

        sim.add_agent(agent)

        # Run simulation
        sim.run(num_ticks=50)

        # Verify stamina decreased
        assert_stamina_decreased(sim.db, sim.simulation_id, agent.id)

        cleanup_test_database(config.database_path)
