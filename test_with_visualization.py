#!/usr/bin/env python3
"""
Enhanced test with visualization system
Creates visual and data outputs for analysis
"""

import time
import random
import logging
import threading
from typing import List

from test_simple import SimpleTest, SimpleTestAgent, HazardZone, HealingStation
from src.visualization.visualizer import Visualizer
from src.world.world import Vector2

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VisualizedTest(SimpleTest):
    """Enhanced test with visualization capabilities"""

    def __init__(self):
        super().__init__()

        # Initialize visualizer
        self.visualizer = Visualizer(
            output_dir="output",
            capture_interval=2.0  # Capture every 2 seconds
        )

        # Extended test duration for better visualization
        self.test_duration = 60.0  # Run for 60 seconds

    def setup(self):
        """Setup test world with visualization-friendly parameters"""
        logger.info("Setting up visualized test world...")

        # Create hazard zones in a pattern
        hazard_positions = [
            Vector2(200, 200),   # Top-left
            Vector2(800, 200),   # Top-right
            Vector2(500, 400),   # Center
            Vector2(200, 700),   # Bottom-left
            Vector2(800, 700),   # Bottom-right
            Vector2(350, 600),   # Additional hazards
            Vector2(650, 300),
        ]

        for i, pos in enumerate(hazard_positions):
            hazard = HazardZone(
                f"Hazard_Zone_{i}",
                pos,
                radius=60,  # Slightly larger for visibility
                damage_per_second=8
            )
            self.hazards.append(hazard)
            self.game.world.add_object(hazard)

        # Create healing stations at strategic locations
        healing_positions = [
            Vector2(50, 50),     # Corner safe zones
            Vector2(950, 50),
            Vector2(50, 950),
            Vector2(950, 950),
            Vector2(500, 100),   # Edge centers
            Vector2(100, 500),
            Vector2(900, 500),
            Vector2(500, 900),
        ]

        for i, pos in enumerate(healing_positions):
            station = HealingStation(
                f"Healing_Station_{i}",
                pos,
                heal_radius=40,
                heal_per_second=15
            )
            self.healing_stations.append(station)
            self.game.world.add_object(station)

        # Create test agents with varied personalities
        agent_count = 15  # More agents for interesting visualization

        # Define agent archetypes for variety
        archetypes = [
            {"name": "Explorer", "exploration": 0.9, "risk_taking": 0.8},
            {"name": "Cautious", "exploration": 0.2, "risk_taking": 0.1},
            {"name": "Balanced", "exploration": 0.5, "risk_taking": 0.5},
            {"name": "Aggressive", "exploration": 0.7, "risk_taking": 0.9},
            {"name": "Social", "exploration": 0.4, "risk_taking": 0.3},
        ]

        for i in range(agent_count):
            # Choose archetype
            archetype = archetypes[i % len(archetypes)]

            # Random starting position in safe area
            pos = Vector2(
                random.uniform(400, 600),
                random.uniform(400, 600)
            )

            agent = SimpleTestAgent(f"{archetype['name']}_{i:02d}", pos)
            agent.stats.max_health = 100
            agent.stats.health = random.randint(70, 100)  # Some start injured
            agent.speed = random.uniform(40, 70)  # Varied speeds

            # Apply archetype traits
            agent.personality.exploration = archetype.get('exploration', 0.5)
            agent.personality.risk_taking = archetype.get('risk_taking', 0.5)

            self.agents.append(agent)
            self.game.world.add_agent(agent)

        logger.info(f"Created {agent_count} agents, {len(self.hazards)} hazards, "
                   f"and {len(self.healing_stations)} healing stations")

    def run(self):
        """Run the visualized test"""
        self.start_time = time.time()

        # Start game engine in background
        game_thread = threading.Thread(target=self.game.start)
        game_thread.daemon = True
        game_thread.start()

        logger.info(f"Starting visualized test for {self.test_duration} seconds...")
        logger.info(f"Output will be saved to: {self.visualizer.session_dir}")

        try:
            last_update = time.time()
            last_print = time.time()
            last_capture = time.time()

            while time.time() - self.start_time < self.test_duration:
                current_time = time.time()
                delta_time = current_time - last_update
                last_update = current_time

                # Update agents (same as before)
                for agent in self.agents:
                    if agent.stats.health > 0:
                        agent.update_behavior(self.game.world, self.hazards,
                                            self.healing_stations, delta_time)

                        # Check hazards
                        for hazard in self.hazards:
                            if hazard.check_and_damage(agent, current_time):
                                self.stats['hazard_hits'] += 1
                                self.stats['total_damage_taken'] += hazard.damage_per_second

                        # Check healing stations
                        for station in self.healing_stations:
                            if station.check_and_heal(agent, current_time):
                                self.stats['healing_visits'] += 1
                                self.stats['total_healing_done'] += station.heal_per_second

                        # Check for death
                        if agent.stats.health <= 0:
                            self.stats['agent_deaths'] += 1
                            logger.warning(f"{agent.name} has died!")

                # Capture visualization snapshot
                if current_time - last_capture >= self.visualizer.capture_interval:
                    self.visualizer.capture_snapshot(
                        self.game, self.agents, self.hazards, self.healing_stations
                    )
                    last_capture = current_time

                # Print status every 10 seconds
                if current_time - last_print >= 10.0:
                    self.print_enhanced_status()
                    last_print = current_time

                time.sleep(0.05)

        except KeyboardInterrupt:
            logger.info("Test interrupted by user")

        finally:
            self.game.stop()
            self.finalize_visualization()

    def print_enhanced_status(self):
        """Print enhanced status with visualization info"""
        elapsed = time.time() - self.start_time
        print(f"\n--- Visualized Test Status at {elapsed:.1f}s ---")

        # Agent status
        alive_agents = [a for a in self.agents if a.stats.health > 0]
        if alive_agents:
            avg_health = sum(a.stats.health for a in alive_agents) / len(alive_agents)
            print(f"Agents: {len(alive_agents)}/{len(self.agents)} alive")
            print(f"Average Health: {avg_health:.1f}")

            # Action distribution
            action_counts = {}
            for agent in alive_agents:
                action = agent.current_action.value
                action_counts[action] = action_counts.get(action, 0) + 1

            print(f"Current Actions:")
            for action, count in sorted(action_counts.items()):
                print(f"  {action}: {count}")

        print(f"Hazard Hits: {self.stats['hazard_hits']}")
        print(f"Healing Visits: {self.stats['healing_visits']}")

        # Visualization stats
        viz_stats = self.visualizer.get_stats()
        print(f"Snapshots Captured: {viz_stats['snapshots_captured']}")

    def finalize_visualization(self):
        """Finalize and export all visualization data"""
        logger.info("Finalizing visualization...")

        # Export all data
        self.visualizer.export_all_data()

        # Create final analysis
        self.create_final_analysis()

        logger.info("Visualization complete!")
        logger.info(f"Check output directory: {self.visualizer.session_dir}")

    def create_final_analysis(self):
        """Create additional analysis files"""
        output_dir = self.visualizer.session_dir

        # Agent behavior analysis
        behavior_file = os.path.join(output_dir, "agent_behavior_analysis.txt")
        with open(behavior_file, 'w') as f:
            f.write("AGENT BEHAVIOR ANALYSIS\n")
            f.write("=" * 30 + "\n\n")

            for agent in self.agents:
                f.write(f"Agent: {agent.name}\n")
                f.write(f"  Personality:\n")
                f.write(f"    Exploration: {agent.personality.exploration:.2f}\n")
                f.write(f"    Risk Taking: {agent.personality.risk_taking:.2f}\n")
                f.write(f"  Final Health: {agent.stats.health:.1f}/{agent.stats.max_health}\n")
                f.write(f"  Final Position: ({agent.position.x:.1f}, {agent.position.y:.1f})\n")

                if agent.stats_log:
                    actions = [log['action'] for log in agent.stats_log]
                    action_counts = {}
                    for action in actions:
                        action_counts[action] = action_counts.get(action, 0) + 1

                    f.write(f"  Behavior Summary:\n")
                    for action, count in sorted(action_counts.items()):
                        percentage = (count / len(actions)) * 100
                        f.write(f"    {action}: {percentage:.1f}%\n")

                f.write("\n")

        # World interaction heatmap data
        heatmap_file = os.path.join(output_dir, "interaction_heatmap_data.csv")
        with open(heatmap_file, 'w') as f:
            f.write("x,y,hazard_interactions,healing_interactions\n")

            # Create a grid and count interactions
            grid_size = 50
            for x in range(0, 1000, grid_size):
                for y in range(0, 1000, grid_size):
                    hazard_count = 0
                    healing_count = 0

                    # Count nearby interactions
                    for agent in self.agents:
                        for log in agent.stats_log:
                            pos_x, pos_y = log['position']
                            if (x <= pos_x < x + grid_size and
                                y <= pos_y < y + grid_size):

                                if log['action'] == 'avoid_hazard':
                                    hazard_count += 1
                                elif log['action'] == 'seek_healing':
                                    healing_count += 1

                    f.write(f"{x + grid_size//2},{y + grid_size//2},{hazard_count},{healing_count}\n")


def main():
    """Main entry point for visualized test"""
    print("""
    ╔══════════════════════════════════════════╗
    ║     MMO ENGINE VISUALIZED TEST           ║
    ║                                          ║
    ║  Testing with graphics and data export   ║
    ╚══════════════════════════════════════════╝
    """)

    # Check if pygame is available
    try:
        import pygame
        logger.info("Graphics rendering available")
    except ImportError:
        logger.warning("Pygame not available - graphics will be disabled")
        logger.info("Install pygame with: pip install pygame")

    test = VisualizedTest()
    test.setup()
    test.run()


if __name__ == "__main__":
    import os
    main()