import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

from src.database.database import Database
from src.database.models import (
    SimulationRun, AgentSnapshot, WorldSnapshot, ActionLog,
    TradeLog, CombatLog, Analytics, DatabaseHelper
)
from src.database.analytics_engine import AnalyticsEngine


class TestDatabaseModels:
    def test_simulation_run_creation(self):
        sim = SimulationRun(
            name="Test Sim",
            description="Test simulation",
            world_seed=42,
            world_width=100,
            world_height=100,
            total_agents=10
        )

        assert sim.name == "Test Sim"
        assert sim.world_seed == 42
        assert sim.config == {}  # Default from __post_init__

    def test_agent_snapshot_creation(self):
        snapshot = AgentSnapshot(
            simulation_id=1,
            agent_id=5,
            tick=100,
            name="Test Agent",
            position_x=10,
            position_y=20,
            health=80,
            max_health=100,
            personality={"curiosity": 0.8},
            skills={"combat": 5}
        )

        assert snapshot.agent_id == 5
        assert snapshot.tick == 100
        assert snapshot.personality["curiosity"] == 0.8
        assert snapshot.skills["combat"] == 5

    def test_database_helper_json_conversion(self):
        # Test dict to JSON
        data = {"key": "value", "number": 42}
        json_str = DatabaseHelper.dict_to_json(data)
        assert isinstance(json_str, str)

        # Test JSON back to dict
        restored_data = DatabaseHelper.json_to_dict(json_str)
        assert restored_data == data

        # Test with None
        assert DatabaseHelper.dict_to_json(None) == "{}"
        assert DatabaseHelper.json_to_dict("") == {}
        assert DatabaseHelper.json_to_dict(None) == {}

    def test_database_helper_list_conversion(self):
        # Test list to JSON
        data = ["item1", "item2", 42]
        json_str = DatabaseHelper.list_to_json(data)
        assert isinstance(json_str, str)

        # Test JSON back to list
        restored_data = DatabaseHelper.json_to_list(json_str)
        assert restored_data == data

        # Test with None
        assert DatabaseHelper.list_to_json(None) == "[]"
        assert DatabaseHelper.json_to_list("") == []


class TestDatabase:
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        db = Database(temp_path)
        yield db
        db.close()

        # Cleanup
        try:
            os.unlink(temp_path)
        except (OSError, FileNotFoundError):
            pass

    def test_database_initialization(self, temp_db):
        """Test database creates and initializes properly"""
        assert os.path.exists(temp_db.db_path)

        # Test connection works
        with temp_db.get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'simulation_runs', 'agent_snapshots', 'world_snapshots',
            'action_logs', 'trade_logs', 'combat_logs', 'analytics', 'schema_version'
        ]

        for table in expected_tables:
            assert table in tables

    def test_simulation_run_crud(self, temp_db):
        """Test simulation run CRUD operations"""
        # Create
        sim = SimulationRun(
            name="Test Simulation",
            description="Test desc",
            world_seed=42,
            world_width=50,
            world_height=50,
            total_agents=5,
            config={"test": True}
        )

        sim_id = temp_db.create_simulation_run(sim)
        assert sim_id is not None
        assert sim_id > 0

        # Read
        retrieved_sim = temp_db.get_simulation_run(sim_id)
        assert retrieved_sim is not None
        assert retrieved_sim.name == "Test Simulation"
        assert retrieved_sim.world_seed == 42
        assert retrieved_sim.config["test"] is True

        # Update
        retrieved_sim.current_tick = 100
        retrieved_sim.end_time = datetime.now()
        update_success = temp_db.update_simulation_run(retrieved_sim)
        assert update_success

        # Verify update
        updated_sim = temp_db.get_simulation_run(sim_id)
        assert updated_sim.current_tick == 100
        assert updated_sim.end_time is not None

        # List
        sim_list = temp_db.list_simulation_runs()
        assert len(sim_list) >= 1
        assert any(s.id == sim_id for s in sim_list)

    def test_agent_snapshot_operations(self, temp_db):
        """Test agent snapshot operations"""
        # First create a simulation
        sim = SimulationRun(name="Test", world_seed=1, world_width=10, world_height=10)
        sim_id = temp_db.create_simulation_run(sim)

        # Create agent snapshots
        snapshots = []
        for i in range(3):
            snapshot = AgentSnapshot(
                simulation_id=sim_id,
                agent_id=1,
                tick=i * 10,
                name="Test Agent",
                position_x=i,
                position_y=i,
                health=100 - i * 10,
                max_health=100,
                personality={"curiosity": 0.5 + i * 0.1},
                skills={"combat": i}
            )
            snapshots.append(snapshot)

        # Test single save
        snapshot_id = temp_db.save_agent_snapshot(snapshots[0])
        assert snapshot_id > 0

        # Test batch save
        temp_db.save_agent_snapshots_batch(snapshots[1:])

        # Test retrieval
        all_snapshots = temp_db.get_agent_snapshots(sim_id)
        assert len(all_snapshots) == 3

        # Test filtered retrieval
        agent_snapshots = temp_db.get_agent_snapshots(sim_id, agent_id=1)
        assert len(agent_snapshots) == 3

        tick_filtered = temp_db.get_agent_snapshots(sim_id, start_tick=5, end_tick=15)
        assert len(tick_filtered) == 1  # Only tick 10 falls in range 5-15

    def test_world_snapshot_operations(self, temp_db):
        """Test world snapshot operations"""
        # Create simulation
        sim = SimulationRun(name="Test", world_seed=1, world_width=10, world_height=10)
        sim_id = temp_db.create_simulation_run(sim)

        # Create world snapshot
        snapshot = WorldSnapshot(
            simulation_id=sim_id,
            tick=50,
            total_entities=10,
            active_agents=5,
            world_events=["event1", "event2"],
            market_prices={"Wood": 2.5, "Stone": 1.5}
        )

        snapshot_id = temp_db.save_world_snapshot(snapshot)
        assert snapshot_id > 0

        # Retrieve
        snapshots = temp_db.get_world_snapshots(sim_id)
        assert len(snapshots) == 1
        assert snapshots[0].market_prices["Wood"] == 2.5
        assert len(snapshots[0].world_events) == 2

    def test_action_log_operations(self, temp_db):
        """Test action logging"""
        # Create simulation
        sim = SimulationRun(name="Test", world_seed=1, world_width=10, world_height=10)
        sim_id = temp_db.create_simulation_run(sim)

        # Log action
        action = ActionLog(
            simulation_id=sim_id,
            tick=25,
            agent_id=1,
            action_type="move",
            action_data={"from": (0, 0), "to": (1, 1)},
            success=True,
            result_message="Moved successfully"
        )

        action_id = temp_db.log_action(action)
        assert action_id > 0

        # Retrieve actions
        actions = temp_db.get_action_logs(sim_id)
        assert len(actions) == 1
        assert actions[0].action_type == "move"
        assert actions[0].action_data["from"] == [0, 0]  # Tuples become lists in JSON

        # Filtered retrieval
        move_actions = temp_db.get_action_logs(sim_id, action_type="move")
        assert len(move_actions) == 1

        no_actions = temp_db.get_action_logs(sim_id, action_type="combat")
        assert len(no_actions) == 0

    def test_analytics_operations(self, temp_db):
        """Test analytics operations"""
        # Create simulation
        sim = SimulationRun(name="Test", world_seed=1, world_width=10, world_height=10)
        sim_id = temp_db.create_simulation_run(sim)

        # Save analytics
        analytics = Analytics(
            simulation_id=sim_id,
            metric_name="agent_health",
            metric_value=0.85,
            tick=100,
            category="agents",
            metadata={"agent_count": 10}
        )

        analytics_id = temp_db.save_analytics(analytics)
        assert analytics_id > 0

        # Retrieve analytics
        all_analytics = temp_db.get_analytics(sim_id)
        assert len(all_analytics) == 1
        assert all_analytics[0].metric_name == "agent_health"
        assert all_analytics[0].metric_value == 0.85

        # Filtered retrieval
        health_analytics = temp_db.get_analytics(sim_id, metric_name="agent_health")
        assert len(health_analytics) == 1

        category_analytics = temp_db.get_analytics(sim_id, category="agents")
        assert len(category_analytics) == 1

    def test_database_views(self, temp_db):
        """Test database view functionality"""
        # Create simulation with some data
        sim = SimulationRun(name="Test", world_seed=1, world_width=10, world_height=10)
        sim_id = temp_db.create_simulation_run(sim)

        # Add agent snapshots
        for i in range(5):
            snapshot = AgentSnapshot(
                simulation_id=sim_id,
                agent_id=i + 1,
                tick=10,
                name=f"Agent {i}",
                position_x=i,
                position_y=i,
                health=100,
                max_health=100
            )
            temp_db.save_agent_snapshot(snapshot)

        # Add action logs
        for i in range(3):
            action = ActionLog(
                simulation_id=sim_id,
                tick=10,
                agent_id=1,
                action_type="move",
                success=True
            )
            temp_db.log_action(action)

        # Test views
        agent_summary = temp_db.get_agent_summary(sim_id)
        assert len(agent_summary) == 5

        action_summary = temp_db.get_action_summary(sim_id)
        assert len(action_summary) >= 1
        assert action_summary[0]["action_type"] == "move"

    def test_database_stats(self, temp_db):
        """Test database statistics"""
        stats = temp_db.get_database_stats()

        assert "simulation_runs_count" in stats
        assert "agent_snapshots_count" in stats
        assert "database_size_bytes" in stats
        assert isinstance(stats["database_size_bytes"], int)


class TestAnalyticsEngine:
    @pytest.fixture
    def analytics_setup(self):
        """Setup analytics engine with test data"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name

        db = Database(temp_path)
        analytics = AnalyticsEngine(db)

        # Create test simulation
        sim = SimulationRun(name="Analytics Test", world_seed=1, world_width=10, world_height=10)
        sim_id = db.create_simulation_run(sim)

        yield analytics, db, sim_id

        db.close()
        try:
            os.unlink(temp_path)
        except (OSError, FileNotFoundError):
            pass

    def test_analytics_engine_initialization(self, analytics_setup):
        """Test analytics engine initializes correctly"""
        analytics, db, sim_id = analytics_setup
        assert analytics.db == db

    def test_metric_calculation(self, analytics_setup):
        """Test basic metric calculations"""
        analytics, db, sim_id = analytics_setup

        # Add some test data
        for i in range(5):
            snapshot = AgentSnapshot(
                simulation_id=sim_id,
                agent_id=i + 1,
                tick=100,
                name=f"Agent {i}",
                health=80 + i * 4,  # 80, 84, 88, 92, 96
                max_health=100,
                stamina=60 + i * 5,  # 60, 65, 70, 75, 80
                max_stamina=100,
                inventory_items=i * 2,  # 0, 2, 4, 6, 8
                gold=i * 10  # 0, 10, 20, 30, 40
            )
            db.save_agent_snapshot(snapshot)

        # Calculate metrics
        analytics._calculate_agent_performance_metrics(sim_id, 100)

        # Check saved metrics
        health_metric = db.get_analytics(sim_id, metric_name="average_agent_health")
        assert len(health_metric) == 1
        assert health_metric[0].metric_value == 0.88  # (80+84+88+92+96)/500 = 440/500 = 0.88

        stamina_metric = db.get_analytics(sim_id, metric_name="average_agent_stamina")
        assert len(stamina_metric) == 1
        assert stamina_metric[0].metric_value == 0.7  # (60+65+70+75+80)/500 = 350/500 = 0.7

    def test_trend_analysis(self, analytics_setup):
        """Test trend analysis functionality"""
        analytics, db, sim_id = analytics_setup

        # Create trend data (increasing values)
        for i in range(10):
            metric = Analytics(
                simulation_id=sim_id,
                metric_name="test_metric",
                metric_value=float(i * 10),  # 0, 10, 20, ..., 90
                tick=i * 10,
                category="test"
            )
            db.save_analytics(metric)

        # Analyze trend
        trend_data = analytics.get_trend_analysis(sim_id, "test_metric")

        assert trend_data["trend"] == "increasing"
        assert trend_data["slope"] > 0
        assert trend_data["data_points"] == 10
        assert trend_data["min_value"] == 0.0
        assert trend_data["max_value"] == 90.0

    def test_correlation_analysis(self, analytics_setup):
        """Test correlation analysis"""
        analytics, db, sim_id = analytics_setup

        # Create correlated data
        for i in range(10):
            # Perfectly correlated metrics
            metric1 = Analytics(
                simulation_id=sim_id,
                metric_name="metric_a",
                metric_value=float(i),
                tick=i,
                category="test"
            )
            metric2 = Analytics(
                simulation_id=sim_id,
                metric_name="metric_b",
                metric_value=float(i * 2),  # Perfectly correlated
                tick=i,
                category="test"
            )
            db.save_analytics(metric1)
            db.save_analytics(metric2)

        # Analyze correlation
        correlation_data = analytics.get_correlation_analysis(sim_id, "metric_a", "metric_b")

        assert correlation_data["correlation"] == pytest.approx(1.0, rel=1e-3)
        assert correlation_data["strength"] == "very_strong"
        assert correlation_data["common_points"] == 10

    def test_simulation_report_generation(self, analytics_setup):
        """Test comprehensive simulation report"""
        analytics, db, sim_id = analytics_setup

        # Add some test metrics
        analytics._save_metric(sim_id, 100, "average_agent_health", 0.85, "agents")
        analytics._save_metric(sim_id, 100, "exploration_rate", 0.3, "exploration")

        # Generate report
        report = analytics.generate_simulation_report(sim_id)

        assert "simulation" in report
        assert "key_metrics" in report
        assert "trends" in report
        assert report["simulation"]["id"] == sim_id

        # Check that some metrics are included
        assert "average_agent_health" in report["key_metrics"]
        assert report["key_metrics"]["average_agent_health"] == 0.85

    def test_gini_coefficient_calculation(self, analytics_setup):
        """Test Gini coefficient calculation for inequality"""
        analytics, db, sim_id = analytics_setup

        # Test with equal distribution (Gini = 0)
        equal_values = [10.0] * 5
        gini_equal = analytics._calculate_gini_coefficient(equal_values)
        assert gini_equal == pytest.approx(0.0, abs=0.01)

        # Test with unequal distribution
        unequal_values = [1.0, 2.0, 3.0, 4.0, 90.0]  # Very unequal
        gini_unequal = analytics._calculate_gini_coefficient(unequal_values)
        assert gini_unequal > 0.5  # Should indicate high inequality

    def test_clustering_calculation(self, analytics_setup):
        """Test agent clustering calculation"""
        analytics, db, sim_id = analytics_setup

        # Test clustered positions
        clustered_positions = [(5, 5), (5, 6), (6, 5), (6, 6)]
        clustering_metric = analytics._calculate_clustering(clustered_positions)
        assert clustering_metric > 0.8  # Should be highly clustered

        # Test spread out positions
        spread_positions = [(0, 0), (50, 50), (100, 0), (0, 100)]
        spread_metric = analytics._calculate_clustering(spread_positions)
        assert spread_metric < 0.5  # Should be less clustered

    def test_economic_metrics_calculation(self, analytics_setup):
        """Test economic metrics calculation"""
        analytics, db, sim_id = analytics_setup

        # Add world snapshot with market data
        world_snapshot = WorldSnapshot(
            simulation_id=sim_id,
            tick=100,
            market_prices={"Wood": 5.0, "Stone": 3.0, "Iron": 10.0}
        )
        db.save_world_snapshot(world_snapshot)

        # Calculate economic metrics
        analytics._calculate_economic_metrics(sim_id, 100)

        # Check that economic metrics were saved
        price_metrics = db.get_analytics(sim_id, category="economy")
        assert len(price_metrics) > 0

        # Find average price metric
        avg_price_metric = None
        for metric in price_metrics:
            if metric.metric_name == "average_market_price":
                avg_price_metric = metric
                break

        assert avg_price_metric is not None
        assert avg_price_metric.metric_value == pytest.approx(6.0, rel=1e-3)  # (5+3+10)/3 = 6