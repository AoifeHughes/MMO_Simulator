"""Database schema definitions and migration management"""

from typing import List


class DatabaseSchema:
    """Database schema management and SQL definitions"""

    # Current schema version
    SCHEMA_VERSION = 1

    # Table creation SQL statements
    CREATE_TABLES = [
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            world_seed INTEGER NOT NULL,
            world_width INTEGER NOT NULL,
            world_height INTEGER NOT NULL,
            start_time TEXT,
            end_time TEXT,
            current_tick INTEGER DEFAULT 0,
            total_agents INTEGER DEFAULT 0,
            config TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS agent_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            tick INTEGER NOT NULL,
            name TEXT NOT NULL,
            position_x INTEGER NOT NULL,
            position_y INTEGER NOT NULL,
            health INTEGER NOT NULL,
            max_health INTEGER NOT NULL,
            stamina INTEGER NOT NULL,
            max_stamina INTEGER NOT NULL,
            personality TEXT DEFAULT '{}',
            character_class TEXT DEFAULT '',
            skills TEXT DEFAULT '{}',
            current_goals TEXT DEFAULT '[]',
            relationships TEXT DEFAULT '{}',
            inventory_items INTEGER DEFAULT 0,
            gold INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS world_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            tick INTEGER NOT NULL,
            total_entities INTEGER DEFAULT 0,
            active_agents INTEGER DEFAULT 0,
            active_npcs INTEGER DEFAULT 0,
            resource_nodes INTEGER DEFAULT 0,
            world_events TEXT DEFAULT '[]',
            market_prices TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            tick INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            action_data TEXT DEFAULT '{}',
            success BOOLEAN DEFAULT FALSE,
            result_message TEXT DEFAULT '',
            duration INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS trade_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            tick INTEGER NOT NULL,
            initiator_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            offered_items TEXT DEFAULT '{}',
            requested_items TEXT DEFAULT '{}',
            offered_gold INTEGER DEFAULT 0,
            requested_gold INTEGER DEFAULT 0,
            completed BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS combat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            tick INTEGER NOT NULL,
            attacker_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            damage_dealt INTEGER DEFAULT 0,
            damage_type TEXT DEFAULT '',
            was_critical BOOLEAN DEFAULT FALSE,
            weapon_used TEXT DEFAULT '',
            target_died BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            simulation_id INTEGER NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            tick INTEGER NOT NULL,
            category TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (simulation_id) REFERENCES simulation_runs(id)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """,

        # Create indexes separately
        "CREATE INDEX IF NOT EXISTS idx_agent_snapshots_sim_tick ON agent_snapshots (simulation_id, tick)",
        "CREATE INDEX IF NOT EXISTS idx_agent_snapshots_agent_id ON agent_snapshots (agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_world_snapshots_sim_tick ON world_snapshots (simulation_id, tick)",
        "CREATE INDEX IF NOT EXISTS idx_action_logs_sim_tick ON action_logs (simulation_id, tick)",
        "CREATE INDEX IF NOT EXISTS idx_action_logs_agent_id ON action_logs (agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_action_logs_type ON action_logs (action_type)",
        "CREATE INDEX IF NOT EXISTS idx_trade_logs_sim_tick ON trade_logs (simulation_id, tick)",
        "CREATE INDEX IF NOT EXISTS idx_trade_logs_initiator ON trade_logs (initiator_id)",
        "CREATE INDEX IF NOT EXISTS idx_trade_logs_target ON trade_logs (target_id)",
        "CREATE INDEX IF NOT EXISTS idx_combat_logs_sim_tick ON combat_logs (simulation_id, tick)",
        "CREATE INDEX IF NOT EXISTS idx_combat_logs_attacker ON combat_logs (attacker_id)",
        "CREATE INDEX IF NOT EXISTS idx_combat_logs_target ON combat_logs (target_id)",
        "CREATE INDEX IF NOT EXISTS idx_analytics_sim_metric ON analytics (simulation_id, metric_name)",
        "CREATE INDEX IF NOT EXISTS idx_analytics_category ON analytics (category)",
        "CREATE INDEX IF NOT EXISTS idx_analytics_tick ON analytics (tick)"
    ]

    # Trigger definitions for automatic timestamp updates
    CREATE_TRIGGERS = [
        """
        CREATE TRIGGER IF NOT EXISTS update_simulation_runs_timestamp
        AFTER UPDATE ON simulation_runs
        BEGIN
            UPDATE simulation_runs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
        """
    ]

    # View definitions for common queries
    CREATE_VIEWS = [
        """
        CREATE VIEW IF NOT EXISTS agent_summary AS
        SELECT
            s.name as simulation_name,
            a.simulation_id,
            a.agent_id,
            a.name as agent_name,
            a.character_class,
            COUNT(*) as snapshot_count,
            MIN(a.tick) as first_tick,
            MAX(a.tick) as last_tick,
            AVG(a.health * 1.0 / a.max_health) as avg_health_ratio,
            AVG(a.stamina * 1.0 / a.max_stamina) as avg_stamina_ratio
        FROM agent_snapshots a
        JOIN simulation_runs s ON a.simulation_id = s.id
        GROUP BY a.simulation_id, a.agent_id, a.name, a.character_class
        """,

        """
        CREATE VIEW IF NOT EXISTS action_summary AS
        SELECT
            simulation_id,
            action_type,
            COUNT(*) as total_actions,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_actions,
            AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate,
            AVG(duration) as avg_duration
        FROM action_logs
        GROUP BY simulation_id, action_type
        """,

        """
        CREATE VIEW IF NOT EXISTS trade_summary AS
        SELECT
            simulation_id,
            COUNT(*) as total_trades,
            SUM(CASE WHEN completed THEN 1 ELSE 0 END) as completed_trades,
            AVG(CASE WHEN completed THEN 1.0 ELSE 0.0 END) as completion_rate,
            AVG(offered_gold + requested_gold) as avg_gold_volume
        FROM trade_logs
        GROUP BY simulation_id
        """,

        """
        CREATE VIEW IF NOT EXISTS combat_summary AS
        SELECT
            simulation_id,
            COUNT(*) as total_combats,
            SUM(damage_dealt) as total_damage,
            AVG(damage_dealt) as avg_damage,
            SUM(CASE WHEN was_critical THEN 1 ELSE 0 END) as critical_hits,
            SUM(CASE WHEN target_died THEN 1 ELSE 0 END) as deaths,
            AVG(CASE WHEN was_critical THEN 1.0 ELSE 0.0 END) as critical_rate
        FROM combat_logs
        GROUP BY simulation_id
        """
    ]

    @classmethod
    def get_all_creation_sql(cls) -> List[str]:
        """Get all SQL statements needed to create the complete schema"""
        return cls.CREATE_TABLES + cls.CREATE_TRIGGERS + cls.CREATE_VIEWS

    @classmethod
    def get_migration_sql(cls, from_version: int, to_version: int) -> List[str]:
        """Get SQL statements for migrating between schema versions"""
        migrations = []

        # Future migrations would be added here
        # For now, we only have version 1
        if from_version == 0 and to_version == 1:
            migrations.extend(cls.get_all_creation_sql())

        return migrations

    @classmethod
    def get_sample_data_sql(cls) -> List[str]:
        """Get SQL statements to insert sample data for testing"""
        return [
            """
            INSERT OR IGNORE INTO simulation_runs
            (id, name, description, world_seed, world_width, world_height, start_time, total_agents, config)
            VALUES
            (1, 'Test Simulation', 'Sample simulation for testing', 42, 50, 50,
             datetime('now'), 10, '{"max_ticks": 1000, "save_interval": 100}')
            """,

            """
            INSERT OR IGNORE INTO schema_version (version) VALUES (1)
            """
        ]

    @classmethod
    def get_cleanup_sql(cls) -> List[str]:
        """Get SQL statements to clean up old data"""
        return [
            # Remove old snapshots beyond a certain age
            """
            DELETE FROM agent_snapshots
            WHERE created_at < datetime('now', '-30 days')
            AND simulation_id NOT IN (
                SELECT id FROM simulation_runs
                WHERE end_time IS NULL  -- Keep data from active simulations
            )
            """,

            """
            DELETE FROM world_snapshots
            WHERE created_at < datetime('now', '-30 days')
            AND simulation_id NOT IN (
                SELECT id FROM simulation_runs
                WHERE end_time IS NULL
            )
            """,

            # Keep action logs for longer for analysis
            """
            DELETE FROM action_logs
            WHERE created_at < datetime('now', '-90 days')
            AND simulation_id NOT IN (
                SELECT id FROM simulation_runs
                WHERE end_time IS NULL
            )
            """,

            # Keep trade and combat logs for analysis
            """
            DELETE FROM trade_logs
            WHERE created_at < datetime('now', '-90 days')
            AND simulation_id NOT IN (
                SELECT id FROM simulation_runs
                WHERE end_time IS NULL
            )
            """,

            """
            DELETE FROM combat_logs
            WHERE created_at < datetime('now', '-90 days')
            AND simulation_id NOT IN (
                SELECT id FROM simulation_runs
                WHERE end_time IS NULL
            )
            """,

            # Vacuum to reclaim space
            "VACUUM"
        ]