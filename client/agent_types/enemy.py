from typing import Dict, Any, List, Optional
from client.agent import BaseAgent
import math
import random
import time

class EnemyAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "enemy")
        self.target_id = None
        self.behavior_state = "patrol"
        self.patrol_points = []
        self.current_patrol_index = 0
        self.attack_range = 2.0
        self.chase_range = 15.0
        self.attack_cooldown = 1.0
        self.last_attack_time = 0
        self.aggression_level = random.uniform(0.5, 1.0)
        self.setup_patrol_route()

    def setup_patrol_route(self):
        for i in range(3):
            angle = (2 * math.pi / 3) * i
            px = self.x + math.cos(angle) * 10
            py = self.y + math.sin(angle) * 10
            self.patrol_points.append((px, py))

    def update(self, delta_time: float):
        # Update pathfinding state
        self.update_pathfinding(delta_time)

        current_time = time.time()

        if self.behavior_state == "patrol":
            self.patrol(delta_time)

        elif self.behavior_state == "chase":
            if self.target_id:
                self.chase_target(delta_time)
            else:
                self.behavior_state = "patrol"

        elif self.behavior_state == "attack":
            if current_time - self.last_attack_time >= self.attack_cooldown:
                self.behavior_state = "chase"

        # Apply movement using the velocity system
        self.move(delta_time)

    def patrol(self, delta_time: float):
        if not self.patrol_points:
            self.stop_movement()
            return

        target = self.patrol_points[self.current_patrol_index]

        # Check if pathfinding is active
        if self.current_path:
            if not self.current_waypoint:
                # Reached patrol point, move to next
                self.current_patrol_index = (self.current_patrol_index + 1) % len(self.patrol_points)
                next_target = self.patrol_points[self.current_patrol_index]
                # Try pathfinding to next patrol point
                if not self.find_path_to(next_target[0], next_target[1]):
                    # Fallback to direct movement
                    self.move_direct(next_target[0], next_target[1])
                    self.velocity_x *= 0.3  # Patrol speed
                    self.velocity_y *= 0.3
        else:
            # No active pathfinding, check distance to current patrol target
            dx = target[0] - self.x
            dy = target[1] - self.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 0.5:
                # Try pathfinding first, fall back to direct movement
                if not self.find_path_to(target[0], target[1]):
                    patrol_speed = self.speed * 0.3
                    self.velocity_x = (dx / distance) * patrol_speed
                    self.velocity_y = (dy / distance) * patrol_speed
                    self.rotation = math.degrees(math.atan2(dy, dx))
            else:
                # Reached patrol point, move to next
                self.current_patrol_index = (self.current_patrol_index + 1) % len(self.patrol_points)
                self.velocity_x = 0
                self.velocity_y = 0

    def chase_target(self, delta_time: float):
        if not self.target_id:
            self.stop_movement()
            return

        target_entity = self.find_entity_by_id(self.target_id)
        if not target_entity:
            self.target_id = None
            self.behavior_state = "patrol"
            self.stop_movement()
            return

        target_x = target_entity['x']
        target_y = target_entity['y']
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance <= self.attack_range:
            self.behavior_state = "attack"
            self.last_attack_time = time.time()
            self.stop_movement()
        elif distance <= self.chase_range:
            # Try pathfinding first for intelligent chasing
            if not self.find_path_to(target_x, target_y):
                # Fallback to direct movement
                chase_speed = self.speed * self.aggression_level
                self.velocity_x = (dx / distance) * chase_speed
                self.velocity_y = (dy / distance) * chase_speed
                self.rotation = math.degrees(math.atan2(dy, dx))
        else:
            self.target_id = None
            self.behavior_state = "patrol"
            self.stop_movement()

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        self.visible_entities = visible_entities

        closest_player = None
        closest_distance = float('inf')

        for entity in visible_entities:
            if entity.get('type') == 'player':
                dx = entity['x'] - self.x
                dy = entity['y'] - self.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < closest_distance and distance <= self.chase_range:
                    closest_distance = distance
                    closest_player = entity

        if closest_player:
            self.target_id = closest_player['id']
            if self.behavior_state == "patrol":
                self.behavior_state = "chase"

    def decide(self) -> Optional[Dict[str, Any]]:
        if self.behavior_state == "attack" and self.target_id:
            return {
                'type': 'attack',
                'target_id': self.target_id,
                'damage': 10 * self.aggression_level
            }
        return None

    def find_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        for entity in self.visible_entities:
            if entity.get('id') == entity_id:
                return entity
        return None