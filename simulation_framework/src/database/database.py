from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ActionLog,
    AgentSnapshot,
    Analytics,
    CombatLog,
    DatabaseHelper,
    SimulationRun,
    TradeLog,
    WorldSnapshot,
)
from .schema import DatabaseSchema

logger = logging.getLogger(__name__)


class Database:
    """Main database interface for the simulation framework"""

    def __init__(self, db_path: str = "simulation.db"):
        self.db_path = db_path
        self.connection = None
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize database and create tables if they don't exist"""
        try:
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if db_dir:  # Only create directory if path has a directory component
                os.makedirs(db_dir, exist_ok=True)

            with self.get_connection() as conn:
                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys = ON")

                # Set WAL mode for better concurrent access
                conn.execute("PRAGMA journal_mode = WAL")

                # Check current schema version
                current_version = self._get_schema_version(conn)

                if current_version < DatabaseSchema.SCHEMA_VERSION:
                    logger.info(
                        f"Migrating database from version {current_version} to {DatabaseSchema.SCHEMA_VERSION}"
                    )
                    self._migrate_schema(
                        conn, current_version, DatabaseSchema.SCHEMA_VERSION
                    )

                logger.info(f"Database initialized at {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _get_schema_version(self, conn: sqlite3.Connection) -> int:
        """Get current schema version from database"""
        try:
            cursor = conn.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else 0
        except sqlite3.OperationalError:
            # Table doesn't exist, assume version 0
            return 0

    def _migrate_schema(
        self, conn: sqlite3.Connection, from_version: int, to_version: int
    ) -> None:
        """Migrate database schema from one version to another"""
        migration_sql = DatabaseSchema.get_migration_sql(from_version, to_version)

        for sql in migration_sql:
            if sql.strip():
                conn.execute(sql)

        # Update schema version
        conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (to_version,)
        )
        conn.commit()

    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    # Simulation Run operations
    def create_simulation_run(self, simulation: SimulationRun) -> int:
        """Create a new simulation run record"""
        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(simulation, for_insert=True)

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            cursor = conn.execute(
                f"INSERT INTO simulation_runs ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def get_simulation_run(self, simulation_id: int) -> Optional[SimulationRun]:
        """Get simulation run by ID"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM simulation_runs WHERE id = ?", (simulation_id,)
            )
            row = cursor.fetchone()
            return DatabaseHelper.row_to_dataclass(row, SimulationRun) if row else None

    def update_simulation_run(self, simulation: SimulationRun) -> bool:
        """Update simulation run record"""
        if not simulation.id:
            return False

        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(simulation)
            data.pop("id")  # Remove ID from update data

            set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
            values = list(data.values()) + [simulation.id]

            cursor = conn.execute(
                f"UPDATE simulation_runs SET {set_clause} WHERE id = ?", values
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_simulation_runs(
        self, limit: int = 100, offset: int = 0
    ) -> List[SimulationRun]:
        """List all simulation runs"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM simulation_runs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
            return [DatabaseHelper.row_to_dataclass(row, SimulationRun) for row in rows]

    # Agent Snapshot operations
    def save_agent_snapshot(self, snapshot: AgentSnapshot) -> int:
        """Save agent snapshot"""
        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(snapshot, for_insert=True)

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            cursor = conn.execute(
                f"INSERT INTO agent_snapshots ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def save_agent_snapshots_batch(self, snapshots: List[AgentSnapshot]) -> None:
        """Save multiple agent snapshots efficiently"""
        if not snapshots:
            return

        with self.get_connection() as conn:
            # Prepare data
            data_list = [
                DatabaseHelper.dataclass_to_dict(s, for_insert=True) for s in snapshots
            ]

            # All snapshots should have the same fields
            columns = list(data_list[0].keys())
            placeholders = ", ".join(["?" for _ in columns])
            columns_str = ", ".join(columns)

            # Execute batch insert
            values_list = [list(data.values()) for data in data_list]
            conn.executemany(
                f"INSERT INTO agent_snapshots ({columns_str}) VALUES ({placeholders})",
                values_list,
            )
            conn.commit()

    def get_agent_snapshots(
        self,
        simulation_id: int,
        agent_id: Optional[int] = None,
        start_tick: Optional[int] = None,
        end_tick: Optional[int] = None,
        limit: int = 1000,
    ) -> List[AgentSnapshot]:
        """Get agent snapshots with filtering"""
        with self.get_connection() as conn:
            conditions = ["simulation_id = ?"]
            params = [simulation_id]

            if agent_id is not None:
                conditions.append("agent_id = ?")
                params.append(agent_id)

            if start_tick is not None:
                conditions.append("tick >= ?")
                params.append(start_tick)

            if end_tick is not None:
                conditions.append("tick <= ?")
                params.append(end_tick)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor = conn.execute(
                f"""
                SELECT * FROM agent_snapshots
                WHERE {where_clause}
                ORDER BY tick DESC, agent_id
                LIMIT ?
                """,
                params,
            )
            rows = cursor.fetchall()
            return [DatabaseHelper.row_to_dataclass(row, AgentSnapshot) for row in rows]

    # World Snapshot operations
    def save_world_snapshot(self, snapshot: WorldSnapshot) -> int:
        """Save world snapshot"""
        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(snapshot, for_insert=True)

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            cursor = conn.execute(
                f"INSERT INTO world_snapshots ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def get_world_snapshots(
        self,
        simulation_id: int,
        start_tick: Optional[int] = None,
        end_tick: Optional[int] = None,
        limit: int = 1000,
    ) -> List[WorldSnapshot]:
        """Get world snapshots with filtering"""
        with self.get_connection() as conn:
            conditions = ["simulation_id = ?"]
            params = [simulation_id]

            if start_tick is not None:
                conditions.append("tick >= ?")
                params.append(start_tick)

            if end_tick is not None:
                conditions.append("tick <= ?")
                params.append(end_tick)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor = conn.execute(
                f"""
                SELECT * FROM world_snapshots
                WHERE {where_clause}
                ORDER BY tick DESC
                LIMIT ?
                """,
                params,
            )
            rows = cursor.fetchall()
            return [DatabaseHelper.row_to_dataclass(row, WorldSnapshot) for row in rows]

    # Action Log operations
    def log_action(self, action: ActionLog) -> int:
        """Log an action"""
        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(action, for_insert=True)

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            cursor = conn.execute(
                f"INSERT INTO action_logs ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def get_action_logs(
        self,
        simulation_id: int,
        agent_id: Optional[int] = None,
        action_type: Optional[str] = None,
        start_tick: Optional[int] = None,
        end_tick: Optional[int] = None,
        limit: int = 1000,
    ) -> List[ActionLog]:
        """Get action logs with filtering"""
        with self.get_connection() as conn:
            conditions = ["simulation_id = ?"]
            params = [simulation_id]

            if agent_id is not None:
                conditions.append("agent_id = ?")
                params.append(agent_id)

            if action_type is not None:
                conditions.append("action_type = ?")
                params.append(action_type)

            if start_tick is not None:
                conditions.append("tick >= ?")
                params.append(start_tick)

            if end_tick is not None:
                conditions.append("tick <= ?")
                params.append(end_tick)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor = conn.execute(
                f"""
                SELECT * FROM action_logs
                WHERE {where_clause}
                ORDER BY tick DESC, agent_id
                LIMIT ?
                """,
                params,
            )
            rows = cursor.fetchall()
            return [DatabaseHelper.row_to_dataclass(row, ActionLog) for row in rows]

    # Trade Log operations
    def log_trade(self, trade: TradeLog) -> int:
        """Log a trade transaction"""
        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(trade, for_insert=True)

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            cursor = conn.execute(
                f"INSERT INTO trade_logs ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return cursor.lastrowid

    # Combat Log operations
    def log_combat(self, combat: CombatLog) -> int:
        """Log a combat action"""
        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(combat, for_insert=True)

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            cursor = conn.execute(
                f"INSERT INTO combat_logs ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return cursor.lastrowid

    # Analytics operations
    def save_analytics(self, analytics: Analytics) -> int:
        """Save analytics metric"""
        with self.get_connection() as conn:
            data = DatabaseHelper.dataclass_to_dict(analytics, for_insert=True)

            placeholders = ", ".join(["?" for _ in data])
            columns = ", ".join(data.keys())

            cursor = conn.execute(
                f"INSERT INTO analytics ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def get_analytics(
        self,
        simulation_id: int,
        metric_name: Optional[str] = None,
        category: Optional[str] = None,
        start_tick: Optional[int] = None,
        end_tick: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Analytics]:
        """Get analytics data with filtering"""
        with self.get_connection() as conn:
            conditions = ["simulation_id = ?"]
            params = [simulation_id]

            if metric_name is not None:
                conditions.append("metric_name = ?")
                params.append(metric_name)

            if category is not None:
                conditions.append("category = ?")
                params.append(category)

            if start_tick is not None:
                conditions.append("tick >= ?")
                params.append(start_tick)

            if end_tick is not None:
                conditions.append("tick <= ?")
                params.append(end_tick)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor = conn.execute(
                f"""
                SELECT * FROM analytics
                WHERE {where_clause}
                ORDER BY tick DESC, metric_name
                LIMIT ?
                """,
                params,
            )
            rows = cursor.fetchall()
            return [DatabaseHelper.row_to_dataclass(row, Analytics) for row in rows]

    # Query operations using views
    def get_agent_summary(self, simulation_id: int) -> List[Dict[str, Any]]:
        """Get agent summary using database view"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM agent_summary WHERE simulation_id = ?", (simulation_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_action_summary(self, simulation_id: int) -> List[Dict[str, Any]]:
        """Get action summary using database view"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM action_summary WHERE simulation_id = ? ORDER BY total_actions DESC",
                (simulation_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_trade_summary(self, simulation_id: int) -> Optional[Dict[str, Any]]:
        """Get trade summary using database view"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM trade_summary WHERE simulation_id = ?", (simulation_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_combat_summary(self, simulation_id: int) -> Optional[Dict[str, Any]]:
        """Get combat summary using database view"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM combat_summary WHERE simulation_id = ?", (simulation_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # Utility operations
    def cleanup_old_data(self) -> None:
        """Clean up old data according to retention policies"""
        cleanup_sql = DatabaseSchema.get_cleanup_sql()

        with self.get_connection() as conn:
            for sql in cleanup_sql:
                if sql.strip():
                    conn.execute(sql)
            conn.commit()

        logger.info("Database cleanup completed")

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            stats = {}

            # Table row counts
            tables = [
                "simulation_runs",
                "agent_snapshots",
                "world_snapshots",
                "action_logs",
                "trade_logs",
                "combat_logs",
                "analytics",
            ]

            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]

            # Database size
            cursor = conn.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            cursor = conn.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            stats["database_size_bytes"] = page_count * page_size

            return stats

    def execute_custom_query(
        self, query: str, params: Tuple = ()
    ) -> List[Dict[str, Any]]:
        """Execute custom SQL query (use with caution)"""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
