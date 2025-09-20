"""
Visualization module for MMO simulation
Creates graphical and text-based outputs for analysis
"""

import os
import time
import json
import csv
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    logging.warning("Pygame not available - graphics disabled")

from src.world.world import Vector2
from src.agents.agent import Agent

logger = logging.getLogger(__name__)


@dataclass
class WorldSnapshot:
    """Captures a snapshot of the world state at a specific time"""
    timestamp: float
    tick: int
    agents: List[Dict[str, Any]]
    hazards: List[Dict[str, Any]]
    healing_stations: List[Dict[str, Any]]
    world_stats: Dict[str, Any]


class DataExporter:
    """Handles exporting data to various formats"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export_snapshots_csv(self, snapshots: List[WorldSnapshot], filename: str = "simulation_data.csv"):
        """Export snapshot data to CSV"""
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Header
            writer.writerow([
                'timestamp', 'tick', 'agent_id', 'agent_name', 'health', 'max_health',
                'pos_x', 'pos_y', 'action', 'velocity_x', 'velocity_y'
            ])

            # Data rows
            for snapshot in snapshots:
                for agent_data in snapshot.agents:
                    writer.writerow([
                        snapshot.timestamp,
                        snapshot.tick,
                        agent_data.get('id', ''),
                        agent_data.get('name', ''),
                        agent_data.get('health', 0),
                        agent_data.get('max_health', 100),
                        agent_data.get('pos_x', 0),
                        agent_data.get('pos_y', 0),
                        agent_data.get('action', ''),
                        agent_data.get('velocity_x', 0),
                        agent_data.get('velocity_y', 0)
                    ])

        logger.info(f"Exported CSV data to {filepath}")

    def export_snapshots_json(self, snapshots: List[WorldSnapshot], filename: str = "simulation_data.json"):
        """Export snapshot data to JSON"""
        filepath = os.path.join(self.output_dir, filename)

        # Convert snapshots to serializable format
        data = []
        for snapshot in snapshots:
            data.append(asdict(snapshot))

        with open(filepath, 'w') as jsonfile:
            json.dump(data, jsonfile, indent=2)

        logger.info(f"Exported JSON data to {filepath}")

    def export_summary_report(self, snapshots: List[WorldSnapshot], filename: str = "summary_report.txt"):
        """Export a human-readable summary report"""
        filepath = os.path.join(self.output_dir, filename)

        if not snapshots:
            return

        with open(filepath, 'w') as f:
            f.write("MMO SIMULATION ANALYSIS REPORT\n")
            f.write("=" * 50 + "\n\n")

            # Basic info
            start_time = snapshots[0].timestamp
            end_time = snapshots[-1].timestamp
            duration = end_time - start_time

            f.write(f"Simulation Duration: {duration:.2f} seconds\n")
            f.write(f"Total Snapshots: {len(snapshots)}\n")
            f.write(f"Start Time: {datetime.fromtimestamp(start_time)}\n")
            f.write(f"End Time: {datetime.fromtimestamp(end_time)}\n\n")

            # Agent analysis
            if snapshots[0].agents:
                f.write("AGENT ANALYSIS\n")
                f.write("-" * 30 + "\n")

                agent_ids = set()
                for snapshot in snapshots:
                    for agent in snapshot.agents:
                        agent_ids.add(agent['id'])

                f.write(f"Total Unique Agents: {len(agent_ids)}\n\n")

                # Per-agent summary
                for agent_id in sorted(agent_ids):
                    agent_snapshots = []
                    for snapshot in snapshots:
                        for agent in snapshot.agents:
                            if agent['id'] == agent_id:
                                agent_snapshots.append(agent)
                                break

                    if agent_snapshots:
                        first = agent_snapshots[0]
                        last = agent_snapshots[-1]

                        f.write(f"Agent: {first['name']}\n")
                        f.write(f"  Initial Health: {first['health']:.1f}/{first['max_health']}\n")
                        f.write(f"  Final Health: {last['health']:.1f}/{last['max_health']}\n")

                        # Health statistics
                        health_values = [a['health'] for a in agent_snapshots]
                        min_health = min(health_values)
                        max_health = max(health_values)
                        avg_health = sum(health_values) / len(health_values)

                        f.write(f"  Health Range: {min_health:.1f} - {max_health:.1f}\n")
                        f.write(f"  Average Health: {avg_health:.1f}\n")

                        # Movement statistics
                        positions = [(a['pos_x'], a['pos_y']) for a in agent_snapshots]
                        if len(positions) > 1:
                            total_distance = 0
                            for i in range(1, len(positions)):
                                dx = positions[i][0] - positions[i-1][0]
                                dy = positions[i][1] - positions[i-1][1]
                                total_distance += (dx*dx + dy*dy)**0.5

                            f.write(f"  Total Distance Traveled: {total_distance:.1f}\n")

                        # Action distribution
                        actions = [a.get('action', 'unknown') for a in agent_snapshots]
                        action_counts = {}
                        for action in actions:
                            action_counts[action] = action_counts.get(action, 0) + 1

                        f.write(f"  Action Distribution:\n")
                        for action, count in sorted(action_counts.items()):
                            percentage = (count / len(actions)) * 100
                            f.write(f"    {action}: {count} ({percentage:.1f}%)\n")

                        f.write("\n")

            # World statistics over time
            f.write("WORLD STATISTICS OVER TIME\n")
            f.write("-" * 30 + "\n")

            if len(snapshots) > 1:
                # Calculate average health over time
                avg_healths = []
                for snapshot in snapshots:
                    if snapshot.agents:
                        avg_health = sum(a['health'] for a in snapshot.agents) / len(snapshot.agents)
                        avg_healths.append(avg_health)

                if avg_healths:
                    f.write(f"Average Agent Health:\n")
                    f.write(f"  Initial: {avg_healths[0]:.1f}\n")
                    f.write(f"  Final: {avg_healths[-1]:.1f}\n")
                    f.write(f"  Minimum: {min(avg_healths):.1f}\n")
                    f.write(f"  Maximum: {max(avg_healths):.1f}\n")

        logger.info(f"Exported summary report to {filepath}")


class GraphicsRenderer:
    """Renders world state as images using pygame"""

    def __init__(self, width: int = 1000, height: int = 1000):
        self.width = width
        self.height = height
        self.screen = None
        self.initialized = False

        if PYGAME_AVAILABLE:
            self._initialize_pygame()

    def _initialize_pygame(self):
        """Initialize pygame for rendering"""
        try:
            pygame.init()
            self.screen = pygame.Surface((self.width, self.height))
            self.initialized = True
            logger.info("Graphics renderer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize pygame: {e}")
            self.initialized = False

    def render_world_state(self, snapshot: WorldSnapshot, world_bounds: Tuple[float, float, float, float]) -> Optional[pygame.Surface]:
        """Render a world snapshot to a pygame surface"""
        if not self.initialized:
            return None

        world_x_min, world_y_min, world_x_max, world_y_max = world_bounds
        world_width = world_x_max - world_x_min
        world_height = world_y_max - world_y_min

        # Clear screen
        self.screen.fill((50, 50, 50))  # Dark gray background

        # Helper function to convert world coordinates to screen coordinates
        def world_to_screen(world_x: float, world_y: float) -> Tuple[int, int]:
            screen_x = int((world_x - world_x_min) / world_width * self.width)
            screen_y = int((world_y - world_y_min) / world_height * self.height)
            return screen_x, screen_y

        # Draw hazards (red circles)
        for hazard in snapshot.hazards:
            pos = world_to_screen(hazard['pos_x'], hazard['pos_y'])
            radius = int(hazard['radius'] / world_width * self.width)
            pygame.draw.circle(self.screen, (255, 100, 100), pos, radius)
            pygame.draw.circle(self.screen, (255, 0, 0), pos, radius, 2)

        # Draw healing stations (green circles)
        for station in snapshot.healing_stations:
            pos = world_to_screen(station['pos_x'], station['pos_y'])
            radius = int(station['radius'] / world_width * self.width)
            pygame.draw.circle(self.screen, (100, 255, 100), pos, radius)
            pygame.draw.circle(self.screen, (0, 255, 0), pos, radius, 2)

        # Draw agents (colored by health and action)
        for agent in snapshot.agents:
            pos = world_to_screen(agent['pos_x'], agent['pos_y'])

            # Color based on health
            health_ratio = agent['health'] / agent['max_health']
            if health_ratio > 0.7:
                base_color = (0, 150, 255)  # Blue for healthy
            elif health_ratio > 0.3:
                base_color = (255, 255, 0)  # Yellow for moderate health
            else:
                base_color = (255, 150, 0)  # Orange for low health

            # Adjust brightness based on action
            action = agent.get('action', 'wander')
            if action == 'seek_healing':
                color = (min(255, base_color[0] + 50), base_color[1], base_color[2])
            elif action == 'avoid_hazard':
                color = (255, base_color[1], base_color[2])
            else:
                color = base_color

            # Draw agent
            pygame.draw.circle(self.screen, color, pos, 5)
            pygame.draw.circle(self.screen, (255, 255, 255), pos, 5, 1)

            # Draw velocity vector
            vel_x = agent.get('velocity_x', 0)
            vel_y = agent.get('velocity_y', 0)
            if abs(vel_x) > 0.1 or abs(vel_y) > 0.1:
                end_pos = (
                    pos[0] + int(vel_x * 20),
                    pos[1] + int(vel_y * 20)
                )
                pygame.draw.line(self.screen, (255, 255, 255), pos, end_pos, 2)

        return self.screen

    def save_surface_as_image(self, surface: pygame.Surface, filepath: str):
        """Save a pygame surface as an image file"""
        if surface and self.initialized:
            pygame.image.save(surface, filepath)


class Visualizer:
    """Main visualization controller"""

    def __init__(self, output_dir: str = "output", capture_interval: float = 1.0):
        self.output_dir = output_dir
        self.capture_interval = capture_interval
        self.snapshots: List[WorldSnapshot] = []
        self.last_capture_time = 0

        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = os.path.join(output_dir, f"simulation_{timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)

        # Initialize components
        self.data_exporter = DataExporter(self.session_dir)
        self.graphics_renderer = GraphicsRenderer()

        logger.info(f"Visualizer initialized - output to {self.session_dir}")

    def capture_snapshot(self, game, agents: List[Any], hazards: List[Any], healing_stations: List[Any]):
        """Capture a snapshot of the current world state"""
        current_time = time.time()

        if current_time - self.last_capture_time < self.capture_interval:
            return

        # Convert agents to serializable format
        agent_data = []
        for agent in agents:
            if hasattr(agent, 'current_action'):
                action = agent.current_action.value
            elif hasattr(agent, 'state'):
                action = agent.state.value
            else:
                action = 'unknown'

            agent_data.append({
                'id': agent.id,
                'name': agent.name,
                'health': agent.stats.health,
                'max_health': agent.stats.max_health,
                'pos_x': agent.position.x,
                'pos_y': agent.position.y,
                'velocity_x': getattr(agent.velocity, 'x', 0),
                'velocity_y': getattr(agent.velocity, 'y', 0),
                'action': action
            })

        # Convert hazards to serializable format
        hazard_data = []
        for hazard in hazards:
            hazard_data.append({
                'id': hazard.id,
                'name': hazard.name,
                'pos_x': hazard.position.x,
                'pos_y': hazard.position.y,
                'radius': getattr(hazard, 'radius', 10)
            })

        # Convert healing stations to serializable format
        healing_data = []
        for station in healing_stations:
            healing_data.append({
                'id': station.id,
                'name': station.name,
                'pos_x': station.position.x,
                'pos_y': station.position.y,
                'radius': getattr(station, 'heal_radius', 10)
            })

        # Create snapshot
        snapshot = WorldSnapshot(
            timestamp=current_time,
            tick=game.current_tick,
            agents=agent_data,
            hazards=hazard_data,
            healing_stations=healing_data,
            world_stats=game.get_stats()
        )

        self.snapshots.append(snapshot)
        self.last_capture_time = current_time

        # Generate visualization
        if len(self.snapshots) % 5 == 0:  # Every 5th snapshot
            self._generate_visualization(snapshot)

        logger.debug(f"Captured snapshot {len(self.snapshots)} at tick {game.current_tick}")

    def _generate_visualization(self, snapshot: WorldSnapshot):
        """Generate a visualization for a snapshot"""
        if not self.graphics_renderer.initialized:
            return

        # Define world bounds (adjust based on your world size)
        world_bounds = (0, 0, 1000, 1000)

        # Render the snapshot
        surface = self.graphics_renderer.render_world_state(snapshot, world_bounds)
        if surface:
            # Save image
            image_filename = f"frame_{len(self.snapshots):04d}.png"
            image_path = os.path.join(self.session_dir, image_filename)
            self.graphics_renderer.save_surface_as_image(surface, image_path)

    def export_all_data(self):
        """Export all captured data"""
        if not self.snapshots:
            logger.warning("No snapshots to export")
            return

        logger.info(f"Exporting {len(self.snapshots)} snapshots...")

        # Export to different formats
        self.data_exporter.export_snapshots_csv(self.snapshots)
        self.data_exporter.export_snapshots_json(self.snapshots)
        self.data_exporter.export_summary_report(self.snapshots)

        # Create index file
        self._create_index_file()

        logger.info(f"All data exported to {self.session_dir}")

    def _create_index_file(self):
        """Create an index file explaining the output"""
        index_path = os.path.join(self.session_dir, "README.txt")

        with open(index_path, 'w') as f:
            f.write("MMO SIMULATION VISUALIZATION OUTPUT\n")
            f.write("=" * 40 + "\n\n")

            f.write("FILES IN THIS DIRECTORY:\n\n")

            f.write("simulation_data.csv - Raw simulation data in CSV format\n")
            f.write("  Columns: timestamp, tick, agent_id, agent_name, health, max_health,\n")
            f.write("           pos_x, pos_y, action, velocity_x, velocity_y\n\n")

            f.write("simulation_data.json - Raw simulation data in JSON format\n")
            f.write("  Complete snapshots with all world state information\n\n")

            f.write("summary_report.txt - Human-readable analysis report\n")
            f.write("  Agent statistics, movement patterns, health analysis\n\n")

            f.write("frame_*.png - World state visualizations\n")
            f.write("  Generated every 5 snapshots showing:\n")
            f.write("  - Red circles: Hazard zones\n")
            f.write("  - Green circles: Healing stations\n")
            f.write("  - Colored dots: Agents (color = health, arrows = velocity)\n")
            f.write("    Blue = healthy, Yellow = moderate, Orange = low health\n")
            f.write("    Brighter colors indicate special actions\n\n")

            f.write(f"Total snapshots captured: {len(self.snapshots)}\n")
            f.write(f"Capture interval: {self.capture_interval} seconds\n")

        logger.info(f"Created index file: {index_path}")

    def get_stats(self) -> Dict[str, Any]:
        """Get visualization statistics"""
        return {
            'snapshots_captured': len(self.snapshots),
            'output_directory': self.session_dir,
            'capture_interval': self.capture_interval,
            'graphics_available': self.graphics_renderer.initialized
        }