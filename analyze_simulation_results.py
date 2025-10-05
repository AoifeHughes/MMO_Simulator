#!/usr/bin/env python3
"""
Comprehensive database analysis script to check for expected simulation behaviors.

This script will:
1. Connect to the simulation database
2. Define a comprehensive list of expected behaviors
3. Query the database to verify each behavior occurred
4. Report on missing behaviors and potential bugs
"""

import sqlite3
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class BehaviorCheck:
    """Represents a specific behavior to check for"""
    name: str
    description: str
    sql_query: str
    expected_minimum: int = 1  # Minimum number of occurrences expected
    found_count: int = 0
    sample_data: List[Any] = None

    def __post_init__(self):
        if self.sample_data is None:
            self.sample_data = []


class SimulationAnalyzer:
    """Analyzer for simulation database results"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.behaviors = []
        self.simulation_info = {}

    def get_simulation_info(self) -> Dict:
        """Get basic information about the simulation run"""
        cursor = self.conn.cursor()

        # Get the latest simulation run
        cursor.execute("""
            SELECT * FROM simulation_runs
            ORDER BY id DESC
            LIMIT 1
        """)

        sim_run = cursor.fetchone()
        if not sim_run:
            return {"error": "No simulation runs found"}

        return {
            "simulation_id": sim_run["id"],
            "name": sim_run["name"],
            "description": sim_run["description"],
            "world_size": f"{sim_run['world_width']}x{sim_run['world_height']}",
            "world_seed": sim_run["world_seed"],
            "start_time": sim_run["start_time"],
            "end_time": sim_run["end_time"],
            "total_ticks": sim_run["current_tick"],
            "total_agents": sim_run["total_agents"]
        }

    def define_expected_behaviors(self) -> List[BehaviorCheck]:
        """Define all the behaviors we expect to see in the simulation"""

        return [
            # === BASIC SIMULATION MECHANICS ===
            BehaviorCheck(
                name="Simulation Initialization",
                description="Simulation run was properly initialized and recorded",
                sql_query="SELECT COUNT(*) as count FROM simulation_runs WHERE id = (SELECT MAX(id) FROM simulation_runs)",
                expected_minimum=1
            ),

            BehaviorCheck(
                name="Agent Snapshots Recorded",
                description="Agent snapshots were saved periodically",
                sql_query="SELECT COUNT(*) as count FROM agent_snapshots",
                expected_minimum=50  # Should have many snapshots over 5 minutes
            ),

            BehaviorCheck(
                name="World Snapshots Recorded",
                description="World state snapshots were saved periodically",
                sql_query="SELECT COUNT(*) as count FROM world_snapshots",
                expected_minimum=10  # Should have world snapshots
            ),

            # === AGENT BEHAVIORS ===
            BehaviorCheck(
                name="Agent Movement Actions",
                description="Agents performed movement actions",
                sql_query="SELECT COUNT(*) as count FROM action_logs WHERE action_type LIKE '%Move%'",
                expected_minimum=100  # Should see many movement actions
            ),

            BehaviorCheck(
                name="Agent Exploration Actions",
                description="Agents performed exploration/wandering actions",
                sql_query="SELECT COUNT(*) as count FROM action_logs WHERE action_type LIKE '%Wander%' OR action_type LIKE '%Explore%'",
                expected_minimum=10
            ),

            BehaviorCheck(
                name="Agent Pathfinding Actions",
                description="Agents used pathfinding to reach destinations",
                sql_query="SELECT COUNT(*) as count FROM action_logs WHERE action_type LIKE '%Pathfind%'",
                expected_minimum=5
            ),

            # === RESOURCE GATHERING ===
            BehaviorCheck(
                name="Gathering Actions Attempted",
                description="Agents attempted to gather resources",
                sql_query="SELECT COUNT(*) as count FROM action_logs WHERE action_type LIKE '%Gather%' OR action_type LIKE '%Mine%' OR action_type LIKE '%Woodcut%' OR action_type LIKE '%Fish%' OR action_type LIKE '%Forage%'",
                expected_minimum=5
            ),

            BehaviorCheck(
                name="Successful Gathering Actions",
                description="Some gathering actions were successful",
                sql_query="SELECT COUNT(*) as count FROM action_logs WHERE (action_type LIKE '%Gather%' OR action_type LIKE '%Mine%' OR action_type LIKE '%Woodcut%') AND success = 1",
                expected_minimum=1
            ),

            # === COMBAT BEHAVIORS ===
            BehaviorCheck(
                name="Combat Actions Initiated",
                description="Combat actions were initiated between entities",
                sql_query="SELECT COUNT(*) as count FROM action_logs WHERE action_type LIKE '%Attack%' OR action_type LIKE '%Combat%'",
                expected_minimum=1
            ),

            BehaviorCheck(
                name="Combat Hits Landed",
                description="Combat attacks successfully hit targets",
                sql_query="SELECT COUNT(*) as count FROM action_logs WHERE action_type LIKE '%Attack%' AND success = 1",
                expected_minimum=1
            ),

            BehaviorCheck(
                name="Combat Damage Dealt",
                description="Combat resulted in damage being dealt",
                sql_query="SELECT COUNT(*) as count FROM combat_logs WHERE damage_dealt > 0",
                expected_minimum=1
            ),

            # === HEALTH AND STAMINA MANAGEMENT ===
            BehaviorCheck(
                name="Health Changes Recorded",
                description="Agents experienced health changes (damage/healing)",
                sql_query="""
                    SELECT COUNT(*) as count FROM agent_snapshots a1
                    JOIN agent_snapshots a2 ON a1.agent_id = a2.agent_id
                    WHERE a1.tick < a2.tick AND a1.health != a2.health
                """,
                expected_minimum=1
            ),

            BehaviorCheck(
                name="Stamina Usage Recorded",
                description="Agents used stamina for actions",
                sql_query="""
                    SELECT COUNT(*) as count FROM agent_snapshots a1
                    JOIN agent_snapshots a2 ON a1.agent_id = a2.agent_id
                    WHERE a1.tick < a2.tick AND a1.stamina < a2.stamina
                """,
                expected_minimum=10  # Should see stamina being used
            ),

            # === AI DECISION MAKING ===
            BehaviorCheck(
                name="Goal-Based Actions",
                description="Agents had active goals recorded in snapshots",
                sql_query="SELECT COUNT(*) as count FROM agent_snapshots WHERE current_goals != '[]' AND current_goals != ''",
                expected_minimum=50
            ),

            BehaviorCheck(
                name="Personality-Based Behavior",
                description="Agents had personality data recorded",
                sql_query="SELECT COUNT(*) as count FROM agent_snapshots WHERE personality != '{}' AND personality != ''",
                expected_minimum=50
            ),

            BehaviorCheck(
                name="Character Class Diversity",
                description="Multiple character classes were present",
                sql_query="SELECT COUNT(DISTINCT character_class) as count FROM agent_snapshots WHERE character_class != ''",
                expected_minimum=2
            ),

            # === WORLD DYNAMICS ===
            BehaviorCheck(
                name="Position Changes",
                description="Agents moved around the world (position changes)",
                sql_query="""
                    SELECT COUNT(*) as count FROM agent_snapshots a1
                    JOIN agent_snapshots a2 ON a1.agent_id = a2.agent_id
                    WHERE a1.tick < a2.tick AND (a1.position_x != a2.position_x OR a1.position_y != a2.position_y)
                """,
                expected_minimum=100  # Should see lots of movement
            ),

            BehaviorCheck(
                name="World State Evolution",
                description="World state changed over time",
                sql_query="""
                    SELECT COUNT(*) as count FROM world_snapshots w1
                    JOIN world_snapshots w2 ON w1.simulation_id = w2.simulation_id
                    WHERE w1.tick < w2.tick AND w1.tick != w2.tick
                """,
                expected_minimum=5
            ),

            # === SYSTEM INTERACTIONS ===
            BehaviorCheck(
                name="Action Success and Failure",
                description="Actions had both successful and failed outcomes",
                sql_query="SELECT COUNT(DISTINCT success) as count FROM action_logs",
                expected_minimum=2  # Should have both true and false
            ),

            BehaviorCheck(
                name="Action Duration Variety",
                description="Actions had different durations",
                sql_query="SELECT COUNT(DISTINCT duration) as count FROM action_logs WHERE duration > 0",
                expected_minimum=2
            ),

            BehaviorCheck(
                name="Diverse Action Types",
                description="Multiple types of actions were performed",
                sql_query="SELECT COUNT(DISTINCT action_type) as count FROM action_logs",
                expected_minimum=5
            ),

            # === ANALYTICS AND METRICS ===
            BehaviorCheck(
                name="Analytics Data Generated",
                description="Analytics metrics were calculated and stored",
                sql_query="SELECT COUNT(*) as count FROM analytics",
                expected_minimum=1
            ),

            BehaviorCheck(
                name="Multiple Metric Categories",
                description="Different categories of metrics were recorded",
                sql_query="SELECT COUNT(DISTINCT category) as count FROM analytics WHERE category != ''",
                expected_minimum=1
            ),

            # === TIME PROGRESSION ===
            BehaviorCheck(
                name="Temporal Progression",
                description="Simulation progressed through multiple time ticks",
                sql_query="SELECT MAX(tick) - MIN(tick) as count FROM agent_snapshots",
                expected_minimum=1000  # Should have run for many ticks
            ),

            BehaviorCheck(
                name="Consistent Time Recording",
                description="Time progression was consistent across tables",
                sql_query="""
                    SELECT COUNT(*) as count FROM (
                        SELECT DISTINCT tick FROM agent_snapshots
                        UNION
                        SELECT DISTINCT tick FROM action_logs
                        UNION
                        SELECT DISTINCT tick FROM world_snapshots
                    )
                """,
                expected_minimum=100
            ),

            # === DATA INTEGRITY ===
            BehaviorCheck(
                name="Agent Data Consistency",
                description="Agent data was consistently recorded",
                sql_query="SELECT COUNT(DISTINCT agent_id) as count FROM agent_snapshots",
                expected_minimum=20  # Should see most of our 30 agents
            ),

            BehaviorCheck(
                name="Simulation ID Consistency",
                description="All records properly reference the simulation",
                sql_query="""
                    SELECT COUNT(*) as count FROM (
                        SELECT simulation_id FROM agent_snapshots WHERE simulation_id IS NOT NULL
                        UNION ALL
                        SELECT simulation_id FROM action_logs WHERE simulation_id IS NOT NULL
                        UNION ALL
                        SELECT simulation_id FROM world_snapshots WHERE simulation_id IS NOT NULL
                        UNION ALL
                        SELECT simulation_id FROM analytics WHERE simulation_id IS NOT NULL
                    )
                """,
                expected_minimum=500
            )
        ]

    def run_behavior_checks(self) -> List[BehaviorCheck]:
        """Run all behavior checks against the database"""

        self.behaviors = self.define_expected_behaviors()

        for behavior in self.behaviors:
            try:
                cursor = self.conn.cursor()
                cursor.execute(behavior.sql_query)
                result = cursor.fetchone()

                # Extract count from result
                if result and 'count' in result.keys():
                    behavior.found_count = result['count'] or 0
                else:
                    behavior.found_count = 0

                # Get sample data for successful checks
                if behavior.found_count > 0:
                    sample_query = behavior.sql_query.replace("COUNT(*) as count", "*")
                    sample_query += " LIMIT 3"

                    try:
                        cursor.execute(sample_query)
                        behavior.sample_data = [dict(row) for row in cursor.fetchall()]
                    except:
                        # Some queries might not work with SELECT *, that's OK
                        behavior.sample_data = []

            except Exception as e:
                print(f"Error checking behavior '{behavior.name}': {e}")
                behavior.found_count = -1  # Indicate error

        return self.behaviors

    def generate_report(self) -> Dict:
        """Generate a comprehensive analysis report"""

        # Get simulation info
        self.simulation_info = self.get_simulation_info()

        # Run all checks
        behaviors = self.run_behavior_checks()

        # Categorize results
        passed = [b for b in behaviors if b.found_count >= b.expected_minimum]
        failed = [b for b in behaviors if 0 <= b.found_count < b.expected_minimum]
        errors = [b for b in behaviors if b.found_count < 0]

        return {
            "simulation_info": self.simulation_info,
            "summary": {
                "total_checks": len(behaviors),
                "passed": len(passed),
                "failed": len(failed),
                "errors": len(errors),
                "success_rate": f"{len(passed) / len(behaviors) * 100:.1f}%"
            },
            "passed_behaviors": passed,
            "failed_behaviors": failed,
            "error_behaviors": errors
        }

    def print_detailed_report(self):
        """Print a detailed analysis report"""

        report = self.generate_report()

        print("=" * 70)
        print("COMPREHENSIVE SIMULATION ANALYSIS REPORT")
        print("=" * 70)

        # Simulation info
        info = report["simulation_info"]
        print(f"\nSimulation Info:")
        print(f"  ID: {info.get('simulation_id')}")
        print(f"  Name: {info.get('name')}")
        print(f"  World: {info.get('world_size')} (seed: {info.get('world_seed')})")
        print(f"  Duration: {info.get('total_ticks')} ticks")
        print(f"  Agents: {info.get('total_agents')}")
        print(f"  Time: {info.get('start_time')} to {info.get('end_time')}")

        # Summary
        summary = report["summary"]
        print(f"\nSummary:")
        print(f"  Total Behavior Checks: {summary['total_checks']}")
        print(f"  ✅ Passed: {summary['passed']}")
        print(f"  ❌ Failed: {summary['failed']}")
        print(f"  ⚠️  Errors: {summary['errors']}")
        print(f"  Success Rate: {summary['success_rate']}")

        # Passed behaviors
        if report["passed_behaviors"]:
            print(f"\n✅ PASSED BEHAVIORS ({len(report['passed_behaviors'])}):")
            print("-" * 50)
            for behavior in report["passed_behaviors"]:
                print(f"  ✓ {behavior.name}")
                print(f"    Found: {behavior.found_count} (expected: {behavior.expected_minimum}+)")
                print(f"    Description: {behavior.description}")
                if behavior.sample_data:
                    print(f"    Sample: {len(behavior.sample_data)} records")
                print()

        # Failed behaviors
        if report["failed_behaviors"]:
            print(f"\n❌ FAILED BEHAVIORS ({len(report['failed_behaviors'])}):")
            print("-" * 50)
            for behavior in report["failed_behaviors"]:
                print(f"  ✗ {behavior.name}")
                print(f"    Found: {behavior.found_count} (expected: {behavior.expected_minimum}+)")
                print(f"    Description: {behavior.description}")
                print(f"    Query: {behavior.sql_query}")
                print()

        # Error behaviors
        if report["error_behaviors"]:
            print(f"\n⚠️  ERROR BEHAVIORS ({len(report['error_behaviors'])}):")
            print("-" * 50)
            for behavior in report["error_behaviors"]:
                print(f"  ! {behavior.name}")
                print(f"    Error during query execution")
                print(f"    Description: {behavior.description}")
                print(f"    Query: {behavior.sql_query}")
                print()

        # Recommendations
        print("\n" + "=" * 70)
        print("RECOMMENDATIONS")
        print("=" * 70)

        if report["failed_behaviors"]:
            print("\nAreas needing investigation:")
            for behavior in report["failed_behaviors"]:
                if "Combat" in behavior.name:
                    print(f"  • Combat System: {behavior.name} - Check combat mechanics and NPC aggro")
                elif "Gathering" in behavior.name:
                    print(f"  • Resource System: {behavior.name} - Check resource availability and gathering logic")
                elif "Analytics" in behavior.name:
                    print(f"  • Analytics System: {behavior.name} - Check analytics calculation timing")
                else:
                    print(f"  • {behavior.name} - Investigate underlying system")

        if not report["failed_behaviors"] and not report["error_behaviors"]:
            print("\n🎉 All behavior checks passed! The simulation is working as expected.")

        print(f"\nDatabase location: {self.db_path}")
        print("Analysis complete.")


def main():
    """Run the comprehensive simulation analysis"""

    db_path = "/Users/aoife/git/MMO_Simulator/simulation_data.db"

    print("Starting comprehensive simulation analysis...")
    print(f"Database: {db_path}")

    try:
        analyzer = SimulationAnalyzer(db_path)
        analyzer.print_detailed_report()

    except FileNotFoundError:
        print(f"Error: Database file not found at {db_path}")
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()