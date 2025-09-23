from typing import Dict, Any, List, Optional, Set, Tuple
from client.agent import BaseAgent
import math
import random
import time

class ExplorerAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "explorer")
        self.explored_tiles: Set[Tuple[int, int]] = set()
        self.current_target = None
        self.exploration_radius = 30.0
        self.stuck_counter = 0
        self.last_position = (x, y)
        self.last_position_time = time.time()
        self.exploration_mode = "spiral"  # Can be "spiral", "random", "frontier"
        self.spiral_angle = 0
        self.spiral_radius = 5
        self.home_base = (x, y)
        self.exploration_history = []
        self.max_history = 100

    def update(self, delta_time: float):
        # Check if stuck
        current_time = time.time()
        if current_time - self.last_position_time > 2.0:
            dist_moved = math.sqrt((self.x - self.last_position[0])**2 +
                                  (self.y - self.last_position[1])**2)
            if dist_moved < 1.0:
                self.stuck_counter += 1
                if self.stuck_counter > 3:
                    self.choose_new_exploration_target()
                    self.stuck_counter = 0
            else:
                self.stuck_counter = 0

            self.last_position = (self.x, self.y)
            self.last_position_time = current_time

        # Move towards current target
        if self.current_target:
            dx = self.current_target[0] - self.x
            dy = self.current_target[1] - self.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 0.5:
                move_distance = min(distance, self.speed * delta_time)
                self.x += (dx / distance) * move_distance
                self.y += (dy / distance) * move_distance
                self.rotation = math.degrees(math.atan2(dy, dx))

                # Update velocity for network sync
                self.velocity_x = (dx / distance) * self.speed
                self.velocity_y = (dy / distance) * self.speed
            else:
                # Reached target, record as explored
                tile_x = int(self.x)
                tile_y = int(self.y)
                self.explored_tiles.add((tile_x, tile_y))

                # Add to exploration history
                self.exploration_history.append((self.x, self.y, time.time()))
                if len(self.exploration_history) > self.max_history:
                    self.exploration_history.pop(0)

                # Choose new target
                self.choose_new_exploration_target()
        else:
            self.choose_new_exploration_target()

    def choose_new_exploration_target(self):
        """Select next exploration target based on mode"""
        if self.exploration_mode == "spiral":
            self.spiral_explore()
        elif self.exploration_mode == "random":
            self.random_explore()
        elif self.exploration_mode == "frontier":
            self.frontier_explore()

    def spiral_explore(self):
        """Explore in expanding spiral pattern"""
        self.spiral_angle += 30  # degrees
        if self.spiral_angle >= 360:
            self.spiral_angle = 0
            self.spiral_radius = min(self.spiral_radius + 3, self.exploration_radius)

        angle_rad = math.radians(self.spiral_angle)
        target_x = self.home_base[0] + math.cos(angle_rad) * self.spiral_radius
        target_y = self.home_base[1] + math.sin(angle_rad) * self.spiral_radius

        self.current_target = (target_x, target_y)

    def random_explore(self):
        """Choose random unexplored location within radius"""
        attempts = 0
        while attempts < 10:
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(5, self.exploration_radius)

            target_x = self.x + math.cos(angle) * distance
            target_y = self.y + math.sin(angle) * distance

            tile_x = int(target_x)
            tile_y = int(target_y)

            if (tile_x, tile_y) not in self.explored_tiles:
                self.current_target = (target_x, target_y)
                break

            attempts += 1

        # If no unexplored tiles found, pick random location
        if attempts >= 10:
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(10, self.exploration_radius)
            self.current_target = (self.x + math.cos(angle) * distance,
                                  self.y + math.sin(angle) * distance)

    def frontier_explore(self):
        """Move towards nearest unexplored frontier"""
        # Find edges of explored area
        frontier_tiles = []

        for tile in self.explored_tiles:
            x, y = tile
            # Check neighbors
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (x + dx, y + dy)
                    if neighbor not in self.explored_tiles:
                        dist = math.sqrt((neighbor[0] - self.x)**2 +
                                       (neighbor[1] - self.y)**2)
                        if dist <= self.exploration_radius:
                            frontier_tiles.append((dist, neighbor))

        if frontier_tiles:
            # Choose nearest frontier
            frontier_tiles.sort()
            _, target_tile = frontier_tiles[0]
            self.current_target = (target_tile[0] + 0.5, target_tile[1] + 0.5)
        else:
            # No frontiers, switch to random
            self.random_explore()

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        """Process what the explorer can see"""
        self.visible_entities = visible_entities

        # Record visible tiles as explored
        for entity in visible_entities:
            tile_x = int(entity.get('x', 0))
            tile_y = int(entity.get('y', 0))
            self.explored_tiles.add((tile_x, tile_y))

        # React to other explorers - spread out if too close
        for entity in visible_entities:
            if entity.get('agent_type') == 'explorer' and entity.get('id') != self.id:
                dx = entity.get('x', 0) - self.x
                dy = entity.get('y', 0) - self.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < 5.0:  # Too close to another explorer
                    # Move away
                    angle = math.atan2(-dy, -dx)
                    new_target_x = self.x + math.cos(angle) * 10
                    new_target_y = self.y + math.sin(angle) * 10
                    self.current_target = (new_target_x, new_target_y)
                    break

    def decide(self) -> Optional[Dict[str, Any]]:
        """Make decisions based on exploration progress"""
        # Report exploration progress periodically
        if len(self.explored_tiles) > 0 and len(self.explored_tiles) % 10 == 0:
            return {
                'type': 'exploration_report',
                'explored_count': len(self.explored_tiles),
                'current_mode': self.exploration_mode,
                'position': (self.x, self.y)
            }
        return None

    def set_exploration_mode(self, mode: str):
        """Change exploration strategy"""
        if mode in ["spiral", "random", "frontier"]:
            self.exploration_mode = mode
            self.choose_new_exploration_target()

    def get_exploration_stats(self) -> Dict[str, Any]:
        """Get exploration statistics"""
        return {
            'tiles_explored': len(self.explored_tiles),
            'exploration_mode': self.exploration_mode,
            'current_target': self.current_target,
            'stuck_counter': self.stuck_counter,
            'coverage_percentage': (len(self.explored_tiles) /
                                   (math.pi * self.exploration_radius**2)) * 100
        }