"""
Test suite for SQLite database functionality in MMO simulator scenarios.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from typing import List

import pytest
import pytest_asyncio

from server.agent_state import AgentRegistry, ServerAgentState
from server.database import (
    AgentSnapshot,
    DatabaseManager,
    PeriodicDataCollector,
    ScenarioRun,
)
from shared.inventory import Inventory
from shared.items import create_item


@pytest_asyncio.fixture
async def temp_database():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    db_manager = DatabaseManager(db_path)
    await db_manager.initialize()

    try:
        yield db_manager
    finally:
        await db_manager.close()
        os.unlink(db_path)


@pytest.fixture
def agent_registry():
    """Create an agent registry with test data"""
    registry = AgentRegistry()
    registry.set_world_dimensions(100, 100)

    # Create test agent with inventory and stats
    agent_id = "test_agent_1"
    agent_state = registry.register_agent(agent_id, "explorer", 25.0, 25.0)

    # Add some exploration data
    agent_state.add_explored_tile(24, 24)
    agent_state.add_explored_tile(25, 25)
    agent_state.add_explored_tile(26, 26)

    # Add some statistics
    agent_state.stats["damage_dealt"] = 50.0
    agent_state.stats["kills"] = 2.0
    agent_state.stats["deaths"] = 1.0
    agent_state.stats["distance_traveled"] = 100.5
    agent_state.stats["exploration_percent"] = 15.0  # Add exploration percentage

    # Add inventory items
    sword = create_item("iron_sword")
    if sword:
        agent_state.inventory.add_item(sword, 1)
        agent_state.inventory.equip_item(sword.item_id)

    # Add a second agent for combat scenarios
    combat_agent_id = "combat_agent_1"
    combat_agent = registry.register_agent(combat_agent_id, "player", 75.0, 75.0)
    combat_agent.stats["damage_dealt"] = 100.0
    combat_agent.stats["kills"] = 5.0

    return registry


class TestDatabaseManager:
    """Test the DatabaseManager class"""

    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_database):
        """Test database initialization creates tables"""
        db_manager = temp_database

        # Should be able to create tables without error
        assert db_manager.engine is not None
        assert db_manager.session_factory is not None

    @pytest.mark.asyncio
    async def test_scenario_lifecycle(self, temp_database):
        """Test starting and ending scenarios"""
        db_manager = temp_database

        # Start scenario
        scenario_id = await db_manager.start_scenario("test_scenario", 100, 100)
        assert scenario_id > 0
        assert db_manager.current_scenario_id == scenario_id

        # End scenario
        await db_manager.end_scenario()
        assert db_manager.current_scenario_id is None

    @pytest.mark.asyncio
    async def test_database_reset_on_scenario_start(self, temp_database):
        """Test that starting a scenario clears existing data"""
        db_manager = temp_database

        # Start first scenario and add some data
        scenario_id_1 = await db_manager.start_scenario("scenario_1", 50, 50)

        # Create dummy agent registry and save snapshot
        registry = AgentRegistry()
        registry.register_agent("agent_1", "explorer", 10.0, 10.0)
        await db_manager.save_snapshot(registry)

        # Start second scenario - should clear data
        scenario_id_2 = await db_manager.start_scenario("scenario_2", 100, 100)

        # Should have scenario ID (might be same as first due to table reset)
        assert scenario_id_2 >= 1
        assert db_manager.current_scenario_id == scenario_id_2

        # Previous data should be cleared (verified by database being empty)
        summary = await db_manager.get_scenario_summary()
        assert summary["scenario_name"] == "scenario_2"

    @pytest.mark.asyncio
    async def test_save_agent_snapshot(self, temp_database, agent_registry):
        """Test saving agent snapshots with inventory and stats"""
        db_manager = temp_database

        # Start scenario
        await db_manager.start_scenario("fishing_exploration", 100, 100)

        # Save snapshot
        await db_manager.save_snapshot(agent_registry)

        # Verify data was saved
        summary = await db_manager.get_scenario_summary()
        assert summary is not None
        assert summary["scenario_name"] == "fishing_exploration"
        assert summary["total_agents"] == 2  # explorer + player

        # Check agent-specific stats
        agent_stats = summary["agent_stats"]
        assert "explorer" in agent_stats
        assert "player" in agent_stats

        explorer_stats = agent_stats["explorer"]
        assert explorer_stats["count"] == 1
        assert explorer_stats["total_kills"] == 2.0
        assert explorer_stats["total_damage_dealt"] == 50.0
        assert explorer_stats["avg_exploration"] > 0  # Should have some exploration

    @pytest.mark.asyncio
    async def test_inventory_and_equipment_storage(self, temp_database, agent_registry):
        """Test that inventory and equipment are properly stored"""
        db_manager = temp_database

        await db_manager.start_scenario("test_inventory", 100, 100)
        await db_manager.save_snapshot(agent_registry)

        # Use raw SQL to verify inventory was stored
        async with db_manager.session_factory() as session:
            # Check inventory items
            from sqlalchemy import text

            inventory_query = text("SELECT * FROM inventory_snapshots")
            cursor = await session.execute(inventory_query)
            inventory_results = cursor.fetchall()
            assert len(inventory_results) > 0, "Should have inventory items saved"

            # Check equipped items
            equipment_query = text("SELECT * FROM equipment_snapshots")
            cursor = await session.execute(equipment_query)
            equipment_results = cursor.fetchall()
            assert len(equipment_results) > 0, "Should have equipped items saved"

    @pytest.mark.asyncio
    async def test_exploration_tracking(self, temp_database, agent_registry):
        """Test exploration percentage calculation and storage"""
        db_manager = temp_database

        await db_manager.start_scenario("exploration_test", 100, 100)

        # Agent should have some explored tiles
        test_agent = agent_registry.get_agent("test_agent_1")
        assert test_agent is not None
        assert len(test_agent.explored_tiles) == 3

        # Calculate exploration percentage
        exploration_percent = test_agent.get_exploration_percentage(100, 100)
        assert exploration_percent == 0.03  # 3 tiles out of 10000 = 0.03%

        await db_manager.save_snapshot(agent_registry)

        # Check that exploration data is saved
        summary = await db_manager.get_scenario_summary()
        explorer_stats = summary["agent_stats"]["explorer"]
        assert explorer_stats["avg_exploration"] > 0


class TestPeriodicDataCollector:
    """Test the PeriodicDataCollector class"""

    @pytest.mark.asyncio
    async def test_collector_lifecycle(self, temp_database, agent_registry):
        """Test starting and stopping data collection"""
        db_manager = temp_database
        await db_manager.start_scenario("collector_test", 100, 100)

        collector = PeriodicDataCollector(db_manager, agent_registry)

        # Start collection
        await collector.start()
        assert collector.running is True
        assert collector.collection_task is not None

        # Stop collection
        await collector.stop()
        assert collector.running is False

    @pytest.mark.asyncio
    async def test_collection_interval_override(self, temp_database, agent_registry):
        """Test that collection interval can be set for faster testing"""
        db_manager = temp_database
        await db_manager.start_scenario("interval_test", 100, 100)

        collector = PeriodicDataCollector(db_manager, agent_registry)
        collector.collection_interval = 0.1  # 100ms for fast testing

        # Start collection and let it run briefly
        await collector.start()
        await asyncio.sleep(0.3)  # Let it collect a few times
        await collector.stop()

        # Should have saved multiple snapshots
        summary = await db_manager.get_scenario_summary()
        assert summary is not None


class TestScenarioSpecificData:
    """Test data collection for specific scenarios"""

    @pytest.mark.asyncio
    async def test_fishing_exploration_data(self, temp_database):
        """Test data structure for fishing exploration scenarios"""
        db_manager = temp_database

        registry = AgentRegistry()
        registry.set_world_dimensions(100, 100)

        # Create fishing explorer
        explorer_id = "fisher_1"
        explorer = registry.register_agent(explorer_id, "explorer", 50.0, 50.0)

        # Add fishing rod
        fishing_rod = create_item("fishing_rod")
        if fishing_rod:
            explorer.inventory.add_item(fishing_rod, 1)

        # Simulate exploration (finding water)
        for x in range(45, 55):
            for y in range(45, 55):
                explorer.add_explored_tile(x, y)  # 100 tiles explored

        # Calculate exploration percentage: 100 tiles / 10000 total * 100 = 1%
        total_tiles = 100 * 100  # 10000
        explored_tiles = len(explorer.explored_tiles)  # 100
        exploration_percent = (explored_tiles / total_tiles) * 100
        explorer.stats["exploration_percent"] = exploration_percent

        await db_manager.start_scenario("fishing_exploration", 100, 100)
        await db_manager.save_snapshot(registry)

        summary = await db_manager.get_scenario_summary()
        explorer_stats = summary["agent_stats"]["explorer"]

        assert explorer_stats["count"] == 1
        assert explorer_stats["avg_exploration"] == 1.0  # 100 tiles / 10000 * 100 = 1%

    @pytest.mark.asyncio
    async def test_combat_scenario_data(self, temp_database):
        """Test data structure for combat scenarios"""
        db_manager = temp_database

        registry = AgentRegistry()
        registry.set_world_dimensions(100, 100)

        # Create combat agents
        player1 = registry.register_agent("player_1", "player", 40.0, 45.0)
        player2 = registry.register_agent("player_2", "player", 42.0, 52.0)
        enemy1 = registry.register_agent("enemy_1", "enemy", 52.0, 47.0)
        enemy2 = registry.register_agent("enemy_2", "enemy", 54.0, 45.0)

        # Simulate combat
        player1.stats["kills"] = 2.0
        player1.stats["damage_dealt"] = 150.0
        player1.stats["deaths"] = 1.0

        enemy1.stats["kills"] = 1.0
        enemy1.stats["damage_dealt"] = 75.0
        enemy1.stats["deaths"] = 1.0

        await db_manager.start_scenario("basic_combat", 100, 100)
        await db_manager.save_snapshot(registry)

        summary = await db_manager.get_scenario_summary()

        # Check player stats
        player_stats = summary["agent_stats"]["player"]
        assert player_stats["count"] == 2
        assert player_stats["total_kills"] == 2.0
        assert player_stats["total_damage_dealt"] == 150.0

        # Check enemy stats
        enemy_stats = summary["agent_stats"]["enemy"]
        assert enemy_stats["count"] == 2
        assert enemy_stats["total_kills"] == 1.0
        assert enemy_stats["total_damage_dealt"] == 75.0


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_save_snapshot_without_scenario(self, temp_database, agent_registry):
        """Test that save_snapshot handles missing scenario gracefully"""
        db_manager = temp_database

        # Try to save without starting scenario
        await db_manager.save_snapshot(agent_registry)  # Should not crash

        # No data should be saved
        summary = await db_manager.get_scenario_summary()
        assert summary is None

    @pytest.mark.asyncio
    async def test_empty_agent_registry(self, temp_database):
        """Test saving snapshot with no agents"""
        db_manager = temp_database
        empty_registry = AgentRegistry()

        await db_manager.start_scenario("empty_test", 100, 100)
        await db_manager.save_snapshot(empty_registry)

        summary = await db_manager.get_scenario_summary()
        assert summary["total_agents"] == 0
        assert summary["agent_stats"] == {}

    @pytest.mark.asyncio
    async def test_agent_without_inventory(self, temp_database):
        """Test agents with empty inventories"""
        db_manager = temp_database

        registry = AgentRegistry()
        registry.set_world_dimensions(100, 100)

        # Create agent but don't add starting items
        agent_id = "empty_agent"
        agent_state = ServerAgentState(agent_id=agent_id, agent_type="npc")
        agent_state.inventory = Inventory()  # Empty inventory
        registry.agents[agent_id] = agent_state

        await db_manager.start_scenario("empty_inventory_test", 100, 100)
        await db_manager.save_snapshot(registry)

        # Should save without errors
        summary = await db_manager.get_scenario_summary()
        assert summary["total_agents"] == 1


@pytest.mark.asyncio
async def test_integration_with_server():
    """Integration test simulating actual server usage"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        # Create database manager
        db_manager = DatabaseManager(db_path)

        # Create agent registry
        registry = AgentRegistry()
        registry.set_world_dimensions(100, 100)

        # Add agents
        explorer = registry.register_agent("explorer_1", "explorer", 25.0, 25.0)
        player = registry.register_agent("player_1", "player", 75.0, 75.0)

        # Simulate scenario lifecycle
        await db_manager.initialize()
        scenario_id = await db_manager.start_scenario("fishing_exploration", 100, 100)

        # Create collector and start
        collector = PeriodicDataCollector(db_manager, registry)
        collector.collection_interval = 0.1  # Fast for testing
        await collector.start()

        # Simulate some game activity
        await asyncio.sleep(0.3)

        # Add exploration data
        registry.process_agent_vision_update(
            "explorer_1", [(24, 24), (25, 25), (26, 26)]
        )

        # Let collector save data
        await asyncio.sleep(0.2)

        # Stop and cleanup
        await collector.stop()
        await db_manager.end_scenario()

        # Verify final state
        summary = await db_manager.get_scenario_summary(scenario_id)
        assert summary is not None
        assert summary["total_agents"] == 2

        await db_manager.close()

    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    # Run a simple test
    async def run_simple_test():
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name

        db_manager = DatabaseManager(db_path)
        await db_manager.initialize()

        registry = AgentRegistry()
        registry.set_world_dimensions(100, 100)
        registry.register_agent("test_1", "explorer", 50.0, 50.0)

        await db_manager.start_scenario("test", 100, 100)
        await db_manager.save_snapshot(registry)

        summary = await db_manager.get_scenario_summary()
        print("Summary:", summary)

        await db_manager.close()
        os.unlink(db_path)

    asyncio.run(run_simple_test())
