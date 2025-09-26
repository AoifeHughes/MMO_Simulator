"""
SQLite database system for storing MMO simulator scenario data.

This module provides persistent storage for agent statistics, inventories,
and exploration data with periodic snapshots and scenario isolation.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey, Boolean, text
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.sqlite import JSON

from server.agent_state import AgentRegistry, ServerAgentState

logger = logging.getLogger(__name__)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True)
    scenario_name = Column(String(100), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    world_width = Column(Integer, nullable=False)
    world_height = Column(Integer, nullable=False)
    total_agents = Column(Integer, default=0)

    # Relationships
    snapshots = relationship("AgentSnapshot", back_populates="scenario_run")


class AgentSnapshot(Base):
    __tablename__ = "agent_snapshots"

    id = Column(Integer, primary_key=True)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=False)
    agent_id = Column(String(50), nullable=False)
    agent_type = Column(String(50), nullable=False)
    snapshot_time = Column(DateTime, nullable=False)

    # Agent state
    position_x = Column(Float, nullable=False)
    position_y = Column(Float, nullable=False)
    rotation = Column(Float, default=0.0)
    health = Column(Float, nullable=False)
    max_health = Column(Float, nullable=False)
    is_alive = Column(Boolean, nullable=False)

    # Statistics
    damage_dealt = Column(Float, default=0.0)
    damage_taken = Column(Float, default=0.0)
    kills = Column(Float, default=0.0)
    deaths = Column(Float, default=0.0)
    exploration_percent = Column(Float, default=0.0)
    distance_traveled = Column(Float, default=0.0)
    explored_tiles_count = Column(Integer, default=0)

    # Experience and other data
    experience = Column(Float, default=0.0)

    # Relationships
    scenario_run = relationship("ScenarioRun", back_populates="snapshots")
    inventory_items = relationship("InventorySnapshot", back_populates="agent_snapshot")
    equipment_items = relationship("EquipmentSnapshot", back_populates="agent_snapshot")


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id = Column(Integer, primary_key=True)
    agent_snapshot_id = Column(Integer, ForeignKey("agent_snapshots.id"), nullable=False)
    slot_index = Column(Integer, nullable=False)
    item_name = Column(String(100))
    item_type = Column(String(50))
    quantity = Column(Integer, default=0)
    item_data = Column(JSON)  # Store full item data as JSON

    # Relationships
    agent_snapshot = relationship("AgentSnapshot", back_populates="inventory_items")


class EquipmentSnapshot(Base):
    __tablename__ = "equipment_snapshots"

    id = Column(Integer, primary_key=True)
    agent_snapshot_id = Column(Integer, ForeignKey("agent_snapshots.id"), nullable=False)
    equipment_slot = Column(String(50), nullable=False)
    item_name = Column(String(100))
    item_type = Column(String(50))
    item_data = Column(JSON)  # Store full item data as JSON

    # Relationships
    agent_snapshot = relationship("AgentSnapshot", back_populates="equipment_items")


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=False)
    trade_time = Column(DateTime, nullable=False)

    # Trade participants
    agent1_id = Column(String(50), nullable=False)
    agent2_id = Column(String(50), nullable=False)

    # Trade details
    agent1_items_given = Column(JSON)  # [{"item_name": str, "quantity": int}, ...]
    agent2_items_given = Column(JSON)  # [{"item_name": str, "quantity": int}, ...]
    trade_status = Column(String(20), default="completed")  # completed, cancelled

    # Trade location
    trade_location_x = Column(Float)
    trade_location_y = Column(Float)

    # Relationships
    scenario_run = relationship("ScenarioRun")


class CraftRecord(Base):
    __tablename__ = "crafts"

    id = Column(Integer, primary_key=True)
    scenario_run_id = Column(Integer, ForeignKey("scenario_runs.id"), nullable=False)
    craft_time = Column(DateTime, nullable=False)

    # Crafter
    agent_id = Column(String(50), nullable=False)

    # Craft details
    recipe_name = Column(String(100), nullable=False)
    ingredients_used = Column(JSON)  # [{"item_name": str, "quantity": int}, ...]
    result_item = Column(String(100))  # Name of created object/item

    # Craft location
    craft_location_x = Column(Float, nullable=False)
    craft_location_y = Column(Float, nullable=False)

    # Result details
    craft_duration = Column(Float)  # How long the crafted object lasts
    craft_success = Column(Boolean, default=True)

    # Relationships
    scenario_run = relationship("ScenarioRun")


class DatabaseManager:
    """Manages SQLite database operations for scenario data storage"""

    def __init__(self, database_path: str = "scenario_data.db"):
        self.database_path = database_path
        self.engine = None
        self.session_factory = None
        self.current_scenario_id: Optional[int] = None

    async def initialize(self):
        """Initialize database connection and create tables"""
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.database_path}",
            echo=False
        )

        # Create all tables
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        logger.info(f"Database initialized: {self.database_path}")

    async def start_scenario(self, scenario_name: str, world_width: int, world_height: int) -> int:
        """Start a new scenario run and clear previous data"""
        if not self.session_factory:
            await self.initialize()

        async with self.session_factory() as session:
            # Clear all existing data (reset database)
            await session.execute(text("DELETE FROM equipment_snapshots"))
            await session.execute(text("DELETE FROM inventory_snapshots"))
            await session.execute(text("DELETE FROM agent_snapshots"))
            await session.execute(text("DELETE FROM scenario_runs"))
            await session.commit()

            # Create new scenario run
            scenario_run = ScenarioRun(
                scenario_name=scenario_name,
                start_time=datetime.now(),
                world_width=world_width,
                world_height=world_height
            )

            session.add(scenario_run)
            await session.commit()
            await session.refresh(scenario_run)

            self.current_scenario_id = scenario_run.id
            logger.info(f"Started scenario '{scenario_name}' with ID {self.current_scenario_id}")
            return scenario_run.id

    async def end_scenario(self):
        """End the current scenario run"""
        if not self.current_scenario_id or not self.session_factory:
            return

        async with self.session_factory() as session:
            scenario_run = await session.get(ScenarioRun, self.current_scenario_id)
            if scenario_run:
                scenario_run.end_time = datetime.now()
                await session.commit()
                logger.info(f"Ended scenario ID {self.current_scenario_id}")

        self.current_scenario_id = None

    async def save_snapshot(self, agent_registry: AgentRegistry):
        """Save a complete snapshot of all agents to the database"""
        if not self.current_scenario_id or not self.session_factory:
            return

        snapshot_time = datetime.now()

        async with self.session_factory() as session:
            # Update scenario agent count
            scenario_run = await session.get(ScenarioRun, self.current_scenario_id)
            if scenario_run:
                scenario_run.total_agents = len(agent_registry.agents)

            # Save agent snapshots
            for agent_id, agent_state in agent_registry.agents.items():
                await self._save_agent_snapshot(session, agent_id, agent_state, snapshot_time)

            await session.commit()

        logger.debug(f"Saved snapshot for {len(agent_registry.agents)} agents")

    async def record_trade(self, agent1_id: str, agent2_id: str, agent1_items: List[Dict], agent2_items: List[Dict],
                          location: Tuple[float, float], status: str = "completed"):
        """Record a trade transaction"""
        if not self.current_scenario_id or not self.session_factory:
            return

        async with self.session_factory() as session:
            trade_record = TradeRecord(
                scenario_run_id=self.current_scenario_id,
                trade_time=datetime.now(),
                agent1_id=agent1_id,
                agent2_id=agent2_id,
                agent1_items_given=agent1_items,
                agent2_items_given=agent2_items,
                trade_status=status,
                trade_location_x=location[0],
                trade_location_y=location[1]
            )

            session.add(trade_record)
            await session.commit()
            logger.debug(f"Recorded trade between {agent1_id} and {agent2_id}")

    async def record_craft(self, agent_id: str, recipe_name: str, ingredients: List[Dict],
                          result_item: str, location: Tuple[float, float],
                          duration: float = 300.0, success: bool = True):
        """Record a crafting activity"""
        if not self.current_scenario_id or not self.session_factory:
            return

        async with self.session_factory() as session:
            craft_record = CraftRecord(
                scenario_run_id=self.current_scenario_id,
                craft_time=datetime.now(),
                agent_id=agent_id,
                recipe_name=recipe_name,
                ingredients_used=ingredients,
                result_item=result_item,
                craft_location_x=location[0],
                craft_location_y=location[1],
                craft_duration=duration,
                craft_success=success
            )

            session.add(craft_record)
            await session.commit()
            logger.debug(f"Recorded craft by {agent_id}: {recipe_name} -> {result_item}")

    async def _save_agent_snapshot(self, session, agent_id: str, agent_state: ServerAgentState, snapshot_time: datetime):
        """Save a single agent snapshot with inventory and equipment"""
        # Create agent snapshot
        agent_snapshot = AgentSnapshot(
            scenario_run_id=self.current_scenario_id,
            agent_id=agent_id,
            agent_type=agent_state.agent_type,
            snapshot_time=snapshot_time,
            position_x=agent_state.position[0],
            position_y=agent_state.position[1],
            rotation=agent_state.rotation,
            health=agent_state.health,
            max_health=agent_state.max_health,
            is_alive=agent_state.is_alive,
            damage_dealt=agent_state.stats.get("damage_dealt", 0.0),
            damage_taken=agent_state.stats.get("damage_taken", 0.0),
            kills=agent_state.stats.get("kills", 0.0),
            deaths=agent_state.stats.get("deaths", 0.0),
            exploration_percent=agent_state.stats.get("exploration_percent", 0.0),
            distance_traveled=agent_state.stats.get("distance_traveled", 0.0),
            explored_tiles_count=len(agent_state.explored_tiles),
            experience=agent_state.experience
        )

        session.add(agent_snapshot)
        await session.flush()  # Get the ID

        # Save inventory
        for slot_idx, slot in enumerate(agent_state.inventory.slots):
            if not slot.is_empty():
                inventory_item = InventorySnapshot(
                    agent_snapshot_id=agent_snapshot.id,
                    slot_index=slot_idx,
                    item_name=slot.item.name,
                    item_type=slot.item.item_type.value,
                    quantity=slot.quantity,
                    item_data=slot.item.to_dict()
                )
                session.add(inventory_item)

        # Save equipped items
        for slot, item in agent_state.inventory.equipped_items.items():
            if item:
                equipment_item = EquipmentSnapshot(
                    agent_snapshot_id=agent_snapshot.id,
                    equipment_slot=slot.value,
                    item_name=item.name,
                    item_type=item.item_type.value,
                    item_data=item.to_dict()
                )
                session.add(equipment_item)

    async def get_scenario_summary(self, scenario_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get summary statistics for a scenario"""
        if not self.session_factory:
            return None

        target_id = scenario_id or self.current_scenario_id
        if not target_id:
            return None

        async with self.session_factory() as session:
            scenario_run = await session.get(ScenarioRun, target_id)
            if not scenario_run:
                return None

            # Get latest snapshots for each agent
            query = text("""
            SELECT
                agent_type,
                COUNT(DISTINCT agent_id) as agent_count,
                AVG(exploration_percent) as avg_exploration,
                MAX(exploration_percent) as max_exploration,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(damage_dealt) as total_damage_dealt,
                AVG(distance_traveled) as avg_distance
            FROM agent_snapshots
            WHERE scenario_run_id = :scenario_id
            AND snapshot_time = (
                SELECT MAX(snapshot_time)
                FROM agent_snapshots as a2
                WHERE a2.agent_id = agent_snapshots.agent_id
                AND a2.scenario_run_id = :scenario_id
            )
            GROUP BY agent_type
            """)

            cursor = await session.execute(query, {"scenario_id": target_id})
            results = cursor.fetchall()

            agent_stats = {}
            for row in results:
                agent_stats[row.agent_type] = {
                    "count": row.agent_count,
                    "avg_exploration": round(row.avg_exploration, 2),
                    "max_exploration": round(row.max_exploration, 2),
                    "total_kills": row.total_kills,
                    "total_deaths": row.total_deaths,
                    "total_damage_dealt": round(row.total_damage_dealt, 2),
                    "avg_distance": round(row.avg_distance, 2)
                }

            return {
                "scenario_name": scenario_run.scenario_name,
                "start_time": scenario_run.start_time.isoformat(),
                "end_time": scenario_run.end_time.isoformat() if scenario_run.end_time else None,
                "world_size": f"{scenario_run.world_width}x{scenario_run.world_height}",
                "total_agents": scenario_run.total_agents,
                "agent_stats": agent_stats
            }

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")


class PeriodicDataCollector:
    """Handles periodic data collection from the server"""

    def __init__(self, database_manager: DatabaseManager, agent_registry: AgentRegistry):
        self.database_manager = database_manager
        self.agent_registry = agent_registry
        self.collection_task: Optional[asyncio.Task] = None
        self.running = False
        self.collection_interval = 60  # 60 seconds

    async def start(self):
        """Start periodic data collection"""
        if self.running:
            return

        self.running = True
        self.collection_task = asyncio.create_task(self._collection_loop())
        logger.info("Started periodic data collection (60s interval)")

    async def stop(self):
        """Stop periodic data collection and save final snapshot"""
        self.running = False

        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass

        # Save final snapshot
        await self.database_manager.save_snapshot(self.agent_registry)
        logger.info("Stopped periodic data collection and saved final snapshot")

    async def _collection_loop(self):
        """Main collection loop that runs every 60 seconds"""
        try:
            while self.running:
                await asyncio.sleep(self.collection_interval)

                if self.running:  # Check again after sleep
                    await self.database_manager.save_snapshot(self.agent_registry)

        except asyncio.CancelledError:
            logger.debug("Data collection loop cancelled")
        except Exception as e:
            logger.error(f"Error in data collection loop: {e}")