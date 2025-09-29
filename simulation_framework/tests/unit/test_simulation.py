import pytest
import tempfile
import os
from unittest.mock import Mock, patch

from src.core.simulation import Simulation
from src.core.config import SimulationConfig
from src.core.time_manager import TimeManager
from src.entities.agent import Agent
from src.entities.npc import NPC
from src.core.world import World
from src.ai.personality import Personality
from src.ai.character_class import CharacterClass, get_character_class


class TestTimeManager:
    """Test the time manager functionality"""

    def test_time_manager_creation(self):
        """Test time manager initialization"""
        tm = TimeManager()
        assert tm.current_tick == 0
        assert tm.ticks_per_game_hour == 60
        assert tm.ticks_per_game_day == 1440

    def test_tick_advancement(self):
        """Test tick progression"""
        tm = TimeManager()
        tm.tick()
        assert tm.current_tick == 1

        tm.tick()
        tm.tick()
        assert tm.current_tick == 3

    def test_game_time_calculation(self):
        """Test game time conversion"""
        tm = TimeManager()
        tm.current_tick = 0

        game_time = tm.get_game_time()
        assert game_time['days'] == 0
        assert game_time['hours'] == 0
        assert game_time['minutes'] == 0

        # Test 1 day + 2 hours + 30 minutes
        tm.current_tick = 1440 + 120 + 30
        game_time = tm.get_game_time()
        assert game_time['days'] == 1
        assert game_time['hours'] == 2
        assert game_time['minutes'] == 30

    def test_day_night_cycle(self):
        """Test day/night time detection"""
        tm = TimeManager()

        # Noon (12:00)
        tm.current_tick = 12 * 60
        assert tm.is_day_time()
        assert not tm.is_night_time()

        # Midnight (00:00)
        tm.current_tick = 0
        assert tm.is_night_time()
        assert not tm.is_day_time()

        # 10 AM
        tm.current_tick = 10 * 60
        assert tm.is_day_time()

    def test_time_modifiers(self):
        """Test time of day modifiers"""
        tm = TimeManager()

        # Prime day time (noon)
        tm.current_tick = 12 * 60
        assert tm.get_time_of_day_modifier() == 1.0

        # Night time
        tm.current_tick = 2 * 60  # 2 AM
        assert tm.get_time_of_day_modifier() == 0.7


class TestSimulationConfig:
    """Test simulation configuration functionality"""

    def test_config_creation(self):
        """Test configuration initialization"""
        config = SimulationConfig()
        assert config.world_width == 50
        assert config.world_height == 50
        assert config.max_ticks == 10000

    def test_config_validation(self):
        """Test configuration validation"""
        config = SimulationConfig()
        config.validate()  # Should not raise

        # Test invalid config
        config.world_width = -1
        with pytest.raises(ValueError):
            config.validate()

    def test_config_custom_params(self):
        """Test custom parameter handling"""
        config = SimulationConfig()
        config.set('custom_value', 42)
        assert config.get('custom_value') == 42
        assert config.get('nonexistent', 'default') == 'default'

    def test_config_serialization(self):
        """Test configuration serialization"""
        config = SimulationConfig(world_width=100, world_height=75)
        config.set('custom_param', 'test_value')

        # Convert to dict and back
        config_dict = config.to_dict()
        config2 = SimulationConfig.from_dict(config_dict)

        assert config2.world_width == 100
        assert config2.world_height == 75
        assert config2.get('custom_param') == 'test_value'

    def test_config_file_operations(self):
        """Test configuration file save/load"""
        config = SimulationConfig(world_width=200, max_ticks=5000)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name

        try:
            config.to_file(config_path)
            config2 = SimulationConfig.from_file(config_path)

            assert config2.world_width == 200
            assert config2.max_ticks == 5000
        finally:
            os.unlink(config_path)


class TestSimulation:
    """Test the main simulation functionality"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
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
            world_width=10,
            world_height=10,
            world_seed=42,
            max_ticks=100,
            database_path=temp_db,
            save_interval=10,
            analytics_interval=5
        )

    @pytest.fixture
    def simulation(self, basic_config):
        """Create a basic simulation instance"""
        return Simulation(basic_config)

    def test_simulation_creation(self, simulation):
        """Test simulation initialization"""
        assert simulation.config.world_width == 10
        assert simulation.config.world_height == 10
        assert simulation.time_manager.current_tick == 0
        assert len(simulation.agents) == 0
        assert len(simulation.npcs) == 0

    def test_simulation_initialization(self, simulation):
        """Test simulation database initialization"""
        simulation.initialize_simulation("Test Simulation", "A test simulation")

        assert simulation.simulation_id is not None
        assert simulation.simulation_run.name == "Test Simulation"
        assert simulation.simulation_run.description == "A test simulation"

    def test_agent_management(self, simulation):
        """Test adding agents to simulation"""
        # Create test agent
        agent = Agent(
            position=(5, 5),
            name="Test Agent",
            personality=Personality.randomize(),
            character_class=get_character_class("Warrior")
        )

        simulation.add_agent(agent)
        assert len(simulation.agents) == 1
        assert agent.world is simulation.world
        assert agent.fog_of_war is simulation.fog_of_war

    def test_npc_management(self, simulation):
        """Test adding NPCs to simulation"""
        npc = NPC(
            position=(3, 3),
            name="Test NPC",
            npc_type="goblin"
        )

        simulation.add_npc(npc)
        assert len(simulation.npcs) == 1
        assert npc.world is simulation.world

    def test_simulation_statistics(self, simulation):
        """Test simulation statistics gathering"""
        # Add some entities
        agent = Agent(
            position=(1, 1),
            name="Agent1",
            personality=Personality.randomize(),
            character_class=get_character_class("Explorer")
        )
        simulation.add_agent(agent)

        npc = NPC(position=(2, 2), name="NPC1", npc_type="wolf")
        simulation.add_npc(npc)

        stats = simulation.get_statistics()
        assert stats['total_agents'] == 1
        assert stats['active_agents'] == 1
        assert stats['total_npcs'] == 1
        assert stats['active_npcs'] == 1
        assert stats['current_tick'] == 0

    def test_simulation_step(self, simulation):
        """Test single simulation step"""
        simulation.initialize_simulation("Step Test")

        # Add an agent
        agent = Agent(
            position=(1, 1),
            name="Test Agent",
            personality=Personality.randomize(),
            character_class=get_character_class("Explorer")
        )
        simulation.add_agent(agent)

        initial_tick = simulation.time_manager.current_tick
        simulation.running = True
        simulation.step()

        assert simulation.time_manager.current_tick == initial_tick + 1

    def test_simulation_run_limited(self, simulation):
        """Test running simulation for limited ticks"""
        simulation.initialize_simulation("Limited Run Test")

        # Add minimal agent
        agent = Agent(
            position=(1, 1),
            name="Test Agent",
            personality=Personality.randomize(),
            character_class=get_character_class("Explorer")
        )
        simulation.add_agent(agent)

        simulation.run(num_ticks=5)

        assert simulation.time_manager.current_tick == 5
        assert not simulation.running

    def test_simulation_pause_resume(self, simulation):
        """Test simulation pause and resume"""
        simulation.initialize_simulation("Pause Test")

        assert not simulation.paused
        simulation.pause_simulation()
        assert simulation.paused

        simulation.resume_simulation()
        assert not simulation.paused

    def test_simulation_stop(self, simulation):
        """Test simulation stop functionality"""
        simulation.initialize_simulation("Stop Test")
        simulation.running = True

        simulation.stop_simulation()
        assert not simulation.running
        assert simulation.simulation_run.end_time is not None

    @patch('src.core.simulation.time.sleep')
    def test_simulation_tick_rate(self, mock_sleep, simulation):
        """Test tick rate limiting"""
        simulation.config.tick_rate = 10.0  # 10 ticks per second
        simulation.initialize_simulation("Tick Rate Test")

        simulation.run(num_ticks=2)

        # Should have called sleep with 1/10 = 0.1 seconds, twice
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(0.1)

    def test_simulation_condition_run(self, simulation):
        """Test running simulation until condition"""
        simulation.initialize_simulation("Condition Test")

        # Add agent
        agent = Agent(
            position=(1, 1),
            name="Test Agent",
            personality=Personality.randomize(),
            character_class=get_character_class("Explorer")
        )
        simulation.add_agent(agent)

        # Run until tick 3
        def condition(sim):
            return sim.time_manager.current_tick >= 3

        simulation.run_until(condition)
        assert simulation.time_manager.current_tick >= 3

    def test_simulation_max_ticks_limit(self, simulation):
        """Test simulation respects max ticks limit"""
        simulation.config.max_ticks = 5
        simulation.initialize_simulation("Max Ticks Test")

        # Try to run for 10 ticks, but should stop at 5
        simulation.run(num_ticks=10)
        assert simulation.time_manager.current_tick == 5

    def test_simulation_snapshot_saving(self, simulation):
        """Test periodic snapshot saving"""
        simulation.config.save_interval = 2
        simulation.initialize_simulation("Snapshot Test")

        # Add agent with full data
        agent = Agent(
            position=(1, 1),
            name="Test Agent",
            personality=Personality.randomize(),
            character_class=get_character_class("Explorer")
        )
        simulation.add_agent(agent)

        # Run for a few ticks to trigger saves
        simulation.run(num_ticks=5)

        # Should have saved snapshots
        snapshots = simulation.db.get_agent_snapshots(simulation.simulation_id)
        assert len(snapshots) > 0