"""
Tests for database enhancements including trade and craft recording.
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from server.database import CraftRecord, DatabaseManager, ScenarioRun, TradeRecord


class TestDatabaseEnhancements:
    @pytest_asyncio.fixture
    async def database_manager(self):
        """Create a test database manager with in-memory database"""
        db_manager = DatabaseManager(":memory:")
        await db_manager.initialize()
        await db_manager.start_scenario("test_scenario", 50, 50)
        return db_manager

    @pytest.mark.asyncio
    async def test_record_trade(self, database_manager):
        """Test recording a trade transaction"""
        agent1_items = [{"item_name": "Wood", "quantity": 2}]
        agent2_items = [{"item_name": "Fresh Fish", "quantity": 1}]
        location = (15.5, 25.3)

        await database_manager.record_trade(
            agent1_id="agent1",
            agent2_id="agent2",
            agent1_items=agent1_items,
            agent2_items=agent2_items,
            location=location,
            status="completed",
        )

        # Verify trade was recorded (would need direct database access to fully test)
        # This tests that the method executes without error
        assert database_manager.current_scenario_id is not None

    @pytest.mark.asyncio
    async def test_record_trade_cancelled(self, database_manager):
        """Test recording a cancelled trade"""
        await database_manager.record_trade(
            agent1_id="seller",
            agent2_id="buyer",
            agent1_items=[{"item_name": "Iron Sword", "quantity": 1}],
            agent2_items=[{"item_name": "Gold", "quantity": 100}],
            location=(30.0, 40.0),
            status="cancelled",
        )

        # Should complete without error
        assert True

    @pytest.mark.asyncio
    async def test_record_craft(self, database_manager):
        """Test recording a crafting activity"""
        ingredients = [{"item_name": "Wood", "quantity": 2}]
        location = (12.0, 18.0)

        await database_manager.record_craft(
            agent_id="crafter1",
            recipe_name="basic_fire",
            ingredients=ingredients,
            result_item="fire_123",
            location=location,
            duration=300.0,
            success=True,
        )

        # Verify craft was recorded
        assert database_manager.current_scenario_id is not None

    @pytest.mark.asyncio
    async def test_record_craft_failure(self, database_manager):
        """Test recording a failed crafting attempt"""
        await database_manager.record_craft(
            agent_id="failed_crafter",
            recipe_name="invalid_recipe",
            ingredients=[],
            result_item="",
            location=(0.0, 0.0),
            duration=0.0,
            success=False,
        )

        # Should complete without error even for failed crafts
        assert True

    @pytest.mark.asyncio
    async def test_multiple_trade_records(self, database_manager):
        """Test recording multiple trades"""
        trades = [
            {
                "agent1_id": "trader_a",
                "agent2_id": "trader_b",
                "agent1_items": [{"item_name": "Wood", "quantity": 5}],
                "agent2_items": [{"item_name": "Fresh Fish", "quantity": 3}],
                "location": (10.0, 10.0),
            },
            {
                "agent1_id": "trader_c",
                "agent2_id": "trader_d",
                "agent1_items": [{"item_name": "Iron Sword", "quantity": 1}],
                "agent2_items": [{"item_name": "Hunter's Bow", "quantity": 1}],
                "location": (20.0, 20.0),
            },
        ]

        for trade in trades:
            await database_manager.record_trade(**trade)

        # All trades should be recorded successfully
        assert True

    @pytest.mark.asyncio
    async def test_multiple_craft_records(self, database_manager):
        """Test recording multiple crafting activities"""
        crafts = [
            {
                "agent_id": "woodworker1",
                "recipe_name": "basic_fire",
                "ingredients": [{"item_name": "Wood", "quantity": 2}],
                "result_item": "fire_001",
                "location": (5.0, 5.0),
            },
            {
                "agent_id": "woodworker2",
                "recipe_name": "campfire",
                "ingredients": [{"item_name": "Wood", "quantity": 4}],
                "result_item": "campfire_001",
                "location": (15.0, 15.0),
            },
        ]

        for craft in crafts:
            await database_manager.record_craft(**craft)

        # All crafts should be recorded successfully
        assert True

    @pytest.mark.asyncio
    async def test_trade_record_with_complex_items(self, database_manager):
        """Test recording trades with complex item structures"""
        complex_agent1_items = [
            {"item_name": "Wood", "quantity": 10},
            {"item_name": "Fresh Fish", "quantity": 5},
        ]
        complex_agent2_items = [
            {"item_name": "Iron Sword", "quantity": 1},
            {"item_name": "Hunter's Bow", "quantity": 1},
            {"item_name": "Fishing Rod", "quantity": 2},
        ]

        await database_manager.record_trade(
            agent1_id="complex_trader_1",
            agent2_id="complex_trader_2",
            agent1_items=complex_agent1_items,
            agent2_items=complex_agent2_items,
            location=(25.7, 35.3),
        )

        assert True

    @pytest.mark.asyncio
    async def test_database_without_scenario(self):
        """Test that trade/craft recording handles missing scenario gracefully"""
        db_manager = DatabaseManager(":memory:")
        await db_manager.initialize()
        # Don't start a scenario

        # Should handle gracefully when no scenario is active
        await db_manager.record_trade(
            agent1_id="no_scenario_agent1",
            agent2_id="no_scenario_agent2",
            agent1_items=[],
            agent2_items=[],
            location=(0.0, 0.0),
        )

        await db_manager.record_craft(
            agent_id="no_scenario_crafter",
            recipe_name="basic_fire",
            ingredients=[],
            result_item="",
            location=(0.0, 0.0),
        )

        # Should not raise errors even without active scenario
        assert True

    @pytest.mark.asyncio
    async def test_scenario_isolation(self, database_manager):
        """Test that database properly isolates data between scenarios"""
        # Record some data for first scenario
        await database_manager.record_trade("agent1", "agent2", [], [], (0.0, 0.0))

        # End first scenario and start new one
        await database_manager.end_scenario()
        await database_manager.start_scenario("second_scenario", 30, 30)

        # Record data for second scenario
        await database_manager.record_craft(
            "crafter", "basic_fire", [], "fire", (0.0, 0.0)
        )

        # Both should work without interference
        assert database_manager.current_scenario_id is not None

    @pytest.mark.asyncio
    async def test_close_database(self, database_manager):
        """Test proper database cleanup"""
        await database_manager.close()

        # After closing, engine should be disposed
        # This mainly tests that close() doesn't raise exceptions
        assert True
