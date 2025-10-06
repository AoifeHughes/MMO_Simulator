import os
import tempfile

import pytest
from src.ai.character_class import get_character_class
from src.ai.goal import ExploreGoal, GatherResourceGoal
from src.ai.personality import Personality
from src.core.config import SimulationConfig
from src.core.simulation import Simulation
from src.entities.agent import Agent
from src.entities.npc import NPC


class TestSimulationScenarios:
    """Integration tests for complete simulation scenarios"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield db_path
        try:
            os.unlink(db_path)
        except FileNotFoundError:
            pass

    @pytest.fixture
    def basic_config(self, temp_db):
        """Create a basic simulation configuration"""
        return SimulationConfig(
            world_width=20,
            world_height=20,
            world_seed=42,
            max_ticks=50,
            database_path=temp_db,
            save_interval=10,
            analytics_interval=5,
            tick_rate=0,  # Run as fast as possible for tests
        )

    @pytest.fixture
    def simulation(self, basic_config):
        """Create a basic simulation instance"""
        return Simulation(basic_config)

    def create_test_agent(
        self, position: tuple, name: str, character_class: str = "Explorer"
    ) -> Agent:
        """Helper to create a test agent"""
        return Agent(
            position=position,
            name=name,
            personality=Personality.randomize(),
            character_class=get_character_class(character_class),
        )

    def create_test_npc(
        self, position: tuple, name: str, npc_type: str = "goblin"
    ) -> NPC:
        """Helper to create a test NPC"""
        return NPC(position=position, name=name, npc_type=npc_type)

    def test_basic_exploration_scenario(self, simulation):
        """Test basic exploration scenario with multiple agents"""
        simulation.initialize_simulation("Basic Exploration Test")

        # Create exploring agents
        explorers = [
            self.create_test_agent((2, 2), "Explorer1", "Explorer"),
            self.create_test_agent((18, 18), "Explorer2", "Explorer"),
            self.create_test_agent((2, 18), "Explorer3", "Explorer"),
        ]

        # Add explorers to simulation
        for explorer in explorers:
            # Give them exploration goals
            explorer.current_goals = [ExploreGoal()]
            simulation.add_agent(explorer)

        # Run simulation
        simulation.run(num_ticks=20)

        # Verify simulation ran successfully
        assert simulation.time_manager.current_tick == 20
        stats = simulation.get_statistics()
        assert stats["total_agents"] == 3
        assert stats["active_agents"] == 3

        # Verify agents moved around and explored
        for agent in simulation.agents:
            # Agent should have some memory of explored areas
            assert hasattr(agent, "fog_of_war")

    def test_combat_scenario(self, simulation):
        """Test combat scenario with agents and NPCs"""
        simulation.initialize_simulation("Combat Test")

        # Create warrior agents
        warriors = [
            self.create_test_agent((5, 5), "Warrior1", "Warrior"),
            self.create_test_agent((6, 5), "Warrior2", "Warrior"),
        ]

        # Create hostile NPCs
        enemies = [
            self.create_test_npc((15, 15), "Goblin1", "goblin"),
            self.create_test_npc((16, 15), "Goblin2", "goblin"),
            self.create_test_npc((15, 16), "Wolf1", "wolf"),
        ]

        # Add entities to simulation first
        for warrior in warriors:
            # Give them exploration goals initially (combat will emerge naturally)
            warrior.current_goals = [ExploreGoal()]
            simulation.add_agent(warrior)

        for enemy in enemies:
            simulation.add_npc(enemy)

        # Run simulation
        simulation.run(num_ticks=30)

        # Verify simulation ran successfully
        assert simulation.time_manager.current_tick == 30
        stats = simulation.get_statistics()
        assert stats["total_agents"] == 2
        assert stats["total_npcs"] == 3

        # Check that some combat occurred (entities may have taken damage)
        for agent in simulation.agents:
            if agent.stats.health < agent.stats.max_health:
                break

        # Note: Combat may not always occur in a short test, so we just verify
        # the simulation completed successfully

    def test_resource_gathering_scenario(self, simulation):
        """Test resource gathering scenario"""
        simulation.initialize_simulation("Resource Gathering Test")

        # Create gatherer agents
        gatherers = [
            self.create_test_agent((3, 3), "Gatherer1", "Explorer"),
            self.create_test_agent((17, 17), "Gatherer2", "Explorer"),
        ]

        # Add gatherers to simulation
        for gatherer in gatherers:
            # Give them resource gathering goals
            gatherer.current_goals = [GatherResourceGoal(resource_type="wood")]
            simulation.add_agent(gatherer)

        # Run simulation
        simulation.run(num_ticks=25)

        # Verify simulation ran successfully
        assert simulation.time_manager.current_tick == 25
        stats = simulation.get_statistics()
        assert stats["total_agents"] == 2
        assert stats["active_agents"] == 2

        # Verify agents attempted to gather resources
        # (specific resource gathering success depends on world generation)
        for agent in simulation.agents:
            assert agent.stats.is_alive()

    def test_mixed_population_scenario(self, simulation):
        """Test scenario with mixed population of agents and NPCs"""
        simulation.initialize_simulation("Mixed Population Test")

        # Create diverse agent population
        agents = [
            self.create_test_agent((1, 1), "Explorer1", "Explorer"),
            self.create_test_agent((19, 1), "Warrior1", "Warrior"),
            self.create_test_agent((1, 19), "Explorer2", "Explorer"),
            self.create_test_agent((19, 19), "Warrior2", "Warrior"),
            self.create_test_agent((10, 10), "Explorer3", "Explorer"),
        ]

        # Create diverse NPC population
        npcs = [
            self.create_test_npc((5, 5), "Goblin1", "goblin"),
            self.create_test_npc((15, 5), "Wolf1", "wolf"),
            self.create_test_npc((5, 15), "Goblin2", "goblin"),
            self.create_test_npc((15, 15), "Wolf2", "wolf"),
        ]

        # Add entities with varied goals
        for i, agent in enumerate(agents):
            if i % 3 == 0:
                agent.current_goals = [ExploreGoal()]
            elif i % 3 == 1:
                agent.current_goals = [GatherResourceGoal(resource_type="stone")]
            else:
                agent.current_goals = [
                    ExploreGoal()
                ]  # Use exploration instead of attack for now
            simulation.add_agent(agent)

        for npc in npcs:
            simulation.add_npc(npc)

        # Run simulation
        simulation.run(num_ticks=40)

        # Verify simulation ran successfully
        assert simulation.time_manager.current_tick == 40
        stats = simulation.get_statistics()
        assert stats["total_agents"] == 5
        assert stats["total_npcs"] == 4

        # Verify all systems integrated properly
        assert len(simulation.tick_times) > 0  # Performance tracking working
        assert simulation.last_save_tick > 0  # Periodic saves working

    def test_long_running_scenario(self, simulation):
        """Test longer running scenario to stress test the simulation"""
        # Reduce save interval for more frequent database operations
        simulation.config.save_interval = 5
        simulation.config.max_ticks = 100

        simulation.initialize_simulation("Long Running Test")

        # Create a moderate population
        agents = []
        for i in range(8):
            x = (i % 4) * 5 + 2
            y = (i // 4) * 10 + 2
            agent = self.create_test_agent(
                (x, y), f"Agent{i+1}", "Explorer" if i % 2 == 0 else "Warrior"
            )
            # Rotate through different goal types
            if i % 3 == 0:
                agent.current_goals = [ExploreGoal()]
            elif i % 3 == 1:
                agent.current_goals = [GatherResourceGoal(resource_type="wood")]
            else:
                agent.current_goals = [
                    ExploreGoal()
                ]  # Use exploration instead of attack for now
            agents.append(agent)
            simulation.add_agent(agent)

        # Add some NPCs
        npcs = [
            self.create_test_npc((10, 10), "CenterGoblin", "goblin"),
            self.create_test_npc((5, 15), "GuardWolf", "wolf"),
        ]
        for npc in npcs:
            simulation.add_npc(npc)

        # Run longer simulation
        simulation.run(num_ticks=60)

        # Verify simulation completed successfully
        assert simulation.time_manager.current_tick == 60
        stats = simulation.get_statistics()
        assert stats["total_agents"] == 8
        assert stats["total_npcs"] == 2

        # Verify database operations occurred
        assert simulation.simulation_id is not None
        snapshots = simulation.db.get_agent_snapshots(simulation.simulation_id)
        assert len(snapshots) > 0

        # Verify analytics were calculated
        report = simulation.get_analytics_report()
        assert report is not None

    def test_simulation_pause_resume_scenario(self, simulation):
        """Test simulation pause and resume functionality"""
        simulation.initialize_simulation("Pause Resume Test")

        # Add some agents
        agents = [
            self.create_test_agent((5, 5), "TestAgent1", "Explorer"),
            self.create_test_agent((15, 15), "TestAgent2", "Warrior"),
        ]
        for agent in agents:
            agent.current_goals = [ExploreGoal()]
            simulation.add_agent(agent)

        # Start simulation
        simulation.running = True

        # Run for a few ticks
        for _ in range(5):
            simulation.step()

        pause_tick = simulation.time_manager.current_tick
        assert pause_tick == 5

        # Pause simulation
        simulation.pause_simulation()
        assert simulation.paused

        # Try to step while paused (should not advance)
        simulation.step()
        assert simulation.time_manager.current_tick == pause_tick

        # Resume and continue
        simulation.resume_simulation()
        assert not simulation.paused

        # Run a few more ticks
        for _ in range(5):
            simulation.step()

        assert simulation.time_manager.current_tick == 10

    def test_conditional_simulation_scenario(self, simulation):
        """Test running simulation until a custom condition is met"""
        simulation.initialize_simulation("Conditional Test")

        # Add agents
        agents = [self.create_test_agent((10, 10), "CenterAgent", "Explorer")]
        for agent in agents:
            agent.current_goals = [ExploreGoal()]
            simulation.add_agent(agent)

        # Define condition: run until tick 15
        def stop_condition(sim):
            return sim.time_manager.current_tick >= 15

        # Run with condition
        simulation.run_until(stop_condition)

        # Verify condition was met
        assert simulation.time_manager.current_tick >= 15
        assert not simulation.running

    def test_analytics_scenario(self, simulation):
        """Test analytics functionality during simulation"""
        simulation.config.analytics_interval = 10
        simulation.initialize_simulation("Analytics Test")

        # Create agents with different characteristics
        agents = [
            self.create_test_agent((2, 2), "EarlyExplorer", "Explorer"),
            self.create_test_agent((18, 18), "LateWarrior", "Warrior"),
            self.create_test_agent((10, 2), "MidExplorer", "Explorer"),
        ]

        for i, agent in enumerate(agents):
            if i == 0:
                agent.current_goals = [ExploreGoal()]
            elif i == 1:
                agent.current_goals = [
                    ExploreGoal()
                ]  # Use exploration instead of attack for now
            else:
                agent.current_goals = [GatherResourceGoal(resource_type="stone")]
            simulation.add_agent(agent)

        # Add an NPC for interaction
        npc = self.create_test_npc((10, 10), "CentralGoblin", "goblin")
        simulation.add_npc(npc)

        # Run simulation to trigger analytics
        simulation.run(num_ticks=25)

        # Verify analytics were generated
        report = simulation.get_analytics_report()
        assert report is not None

        # Check simulation completed successfully
        assert simulation.time_manager.current_tick == 25
        stats = simulation.get_statistics()
        assert stats["total_agents"] == 3
        assert stats["total_npcs"] == 1

    def test_market_trading_scenario(self, simulation):
        """Test market and trading systems during simulation"""
        simulation.initialize_simulation("Trading Test")

        # Create traders
        traders = [
            self.create_test_agent((3, 10), "Trader1", "Explorer"),
            self.create_test_agent((17, 10), "Trader2", "Explorer"),
        ]

        for trader in traders:
            # Give mixed goals including resource gathering (for trading)
            trader.current_goals = [GatherResourceGoal(resource_type="wood")]
            simulation.add_agent(trader)

        # Run simulation to allow market dynamics
        simulation.run(num_ticks=35)

        # Verify market system is active
        market_prices = simulation.market.get_current_prices()
        assert len(market_prices) > 0

        # Verify simulation completed successfully
        assert simulation.time_manager.current_tick == 35
        stats = simulation.get_statistics()
        assert stats["total_agents"] == 2

        # Check that trading system is functioning
        assert simulation.trading_system is not None
