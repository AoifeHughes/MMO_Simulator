#!/usr/bin/env python3
"""
Database inspection tool for MMO Simulator databases.

Usage:
    python inspect_database.py simulation_data.db
"""

import os
import sqlite3
import sys
from datetime import datetime


def format_timestamp(timestamp):
    """Format timestamp for readable display"""
    if timestamp:
        try:
            return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(timestamp)
    return "N/A"


def inspect_database(db_path):
    """Inspect and display database contents"""
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return

    print(f"=== Inspecting Database: {db_path} ===")
    print(f"File size: {os.path.getsize(db_path) / 1024:.1f} KB")
    print()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Show all tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = cursor.fetchall()
        print(f"📊 Tables ({len(tables)}): {', '.join([table[0] for table in tables])}")
        print()

        # Simulation runs
        print("🎯 SIMULATION RUNS")
        print("-" * 50)
        cursor.execute("""
            SELECT id, name, description, world_width, world_height,
                   current_tick, total_agents, start_time, end_time
            FROM simulation_runs ORDER BY id DESC
        """)
        runs = cursor.fetchall()

        if runs:
            for run in runs:
                (
                    run_id,
                    name,
                    description,
                    width,
                    height,
                    tick,
                    agents,
                    start_time,
                    end_time,
                ) = run
                print(f"Run ID: {run_id}")
                print(f"Name: {name}")
                print(f"Description: {description}")
                print(f"World: {width}x{height}")
                print(f"Final Tick: {tick}")
                print(f"Total Agents: {agents}")
                print(f"Started: {start_time}")
                print(f"Ended: {end_time if end_time else 'Running'}")
                print()
        else:
            print("No simulation runs found.")
        print()

        # Action logs summary
        print("🎬 ACTION LOGS")
        print("-" * 50)
        cursor.execute("SELECT COUNT(*) FROM action_logs")
        total_actions = cursor.fetchone()[0]
        print(f"Total actions: {total_actions}")

        if total_actions > 0:
            # Action types breakdown
            cursor.execute("""
                SELECT action_type, COUNT(*) as count,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
                FROM action_logs
                GROUP BY action_type
                ORDER BY count DESC
            """)
            action_types = cursor.fetchall()

            print("\\nAction breakdown:")
            for action_type, count, successful in action_types:
                success_rate = (successful / count * 100) if count > 0 else 0
                print(
                    f"  {action_type}: {count} total, {successful} successful ({success_rate:.1f}%)"
                )

            # Recent actions
            print("\\nRecent actions:")
            cursor.execute("""
                SELECT tick, agent_id, action_type, success, result_message
                FROM action_logs
                ORDER BY tick DESC
                LIMIT 10
            """)
            recent_actions = cursor.fetchall()

            for tick, agent_id, action_type, success, message in recent_actions:
                status = "✅" if success else "❌"
                msg_preview = message[:50]
                print(
                    f"  Tick {tick:3d}: Agent {agent_id} - "
                    f"{action_type:15s} {status} {msg_preview}"
                )
        print()

        # Agent snapshots
        print("👥 AGENT SNAPSHOTS")
        print("-" * 50)
        cursor.execute("SELECT COUNT(*) FROM agent_snapshots")
        total_snapshots = cursor.fetchone()[0]
        print(f"Total snapshots: {total_snapshots}")

        if total_snapshots > 0:
            # Latest snapshot for each agent
            cursor.execute("""
                SELECT agent_id, name, MAX(tick) as last_tick,
                       health, max_health, position_x, position_y
                FROM agent_snapshots
                GROUP BY agent_id
                ORDER BY agent_id
            """)
            latest_agents = cursor.fetchall()

            print("\\nFinal agent states:")
            for agent_id, name, tick, health, max_health, x, y in latest_agents:
                health_pct = (health / max_health * 100) if max_health > 0 else 0
                status = "💚" if health > 0 else "💀"
                print(
                    f"  Agent {agent_id:2d} ({name:15s}): {status} "
                    f"{health:3d}/{max_health:3d} HP ({health_pct:5.1f}%) "
                    f"at ({x:2d},{y:2d}) [Tick {tick}]"
                )
        print()

        # World snapshots
        print("🌍 WORLD SNAPSHOTS")
        print("-" * 50)
        cursor.execute("SELECT COUNT(*) FROM world_snapshots")
        world_snapshots = cursor.fetchone()[0]
        print(f"World snapshots: {world_snapshots}")

        if world_snapshots > 0:
            cursor.execute("""
                SELECT tick, active_agents, active_npcs
                FROM world_snapshots
                ORDER BY tick DESC
                LIMIT 1
            """)
            latest_world = cursor.fetchone()
            if latest_world:
                tick, active_agents, active_npcs = latest_world
                print(
                    f"Latest (Tick {tick}): {active_agents} agents, "
                    f"{active_npcs} NPCs active"
                )
        print()

        # Combat logs
        print("⚔️ COMBAT LOGS")
        print("-" * 50)
        cursor.execute("SELECT COUNT(*) FROM combat_logs")
        combat_count = cursor.fetchone()[0]
        print(f"Combat events: {combat_count}")

        if combat_count > 0:
            cursor.execute("""
                SELECT tick, attacker_id, defender_id, damage_dealt, combat_result
                FROM combat_logs
                ORDER BY tick DESC
                LIMIT 5
            """)
            recent_combat = cursor.fetchall()

            print("\\nRecent combat:")
            for tick, attacker, defender, damage, result in recent_combat:
                print(
                    f"  Tick {tick:3d}: Agent {attacker} vs Agent {defender} - {damage} damage, {result}"
                )
        print()

        # Trade logs
        print("💰 TRADE LOGS")
        print("-" * 50)
        cursor.execute("SELECT COUNT(*) FROM trade_logs")
        trade_count = cursor.fetchone()[0]
        print(f"Trade events: {trade_count}")

        if trade_count > 0:
            cursor.execute("""
                SELECT tick, buyer_id, seller_id, item_name, quantity, price
                FROM trade_logs
                ORDER BY tick DESC
                LIMIT 5
            """)
            recent_trades = cursor.fetchall()

            print("\\nRecent trades:")
            for tick, buyer, seller, item, qty, price in recent_trades:
                print(
                    f"  Tick {tick:3d}: Agent {buyer} bought {qty}x {item} "
                    f"from Agent {seller} for {price}"
                )
        print()

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python inspect_database.py <database_file>")
        print("Example: python inspect_database.py simulation_data.db")
        sys.exit(1)

    db_path = sys.argv[1]
    inspect_database(db_path)


if __name__ == "__main__":
    main()
