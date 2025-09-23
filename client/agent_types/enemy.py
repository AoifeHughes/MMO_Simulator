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

    def patrol(self, delta_time: float):
        if not self.patrol_points:
            return

        target = self.patrol_points[self.current_patrol_index]
        dx = target[0] - self.x
        dy = target[1] - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 0.5:
            move_distance = min(distance, self.speed * 0.3 * delta_time)
            self.x += (dx / distance) * move_distance
            self.y += (dy / distance) * move_distance
            self.rotation = math.degrees(math.atan2(dy, dx))
        else:
            self.current_patrol_index = (self.current_patrol_index + 1) % len(self.patrol_points)

    def chase_target(self, delta_time: float):
        if not self.target_id:
            return

        target_entity = self.find_entity_by_id(self.target_id)
        if not target_entity:
            self.target_id = None
            self.behavior_state = "patrol"
            return

        dx = target_entity['x'] - self.x
        dy = target_entity['y'] - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance <= self.attack_range:
            self.behavior_state = "attack"
            self.last_attack_time = time.time()
            self.velocity_x = 0
            self.velocity_y = 0
        elif distance <= self.chase_range:
            move_distance = min(distance, self.speed * self.aggression_level * delta_time)
            self.x += (dx / distance) * move_distance
            self.y += (dy / distance) * move_distance
            self.rotation = math.degrees(math.atan2(dy, dx))
            self.velocity_x = (dx / distance) * self.speed * self.aggression_level
            self.velocity_y = (dy / distance) * self.speed * self.aggression_level
        else:
            self.target_id = None
            self.behavior_state = "patrol"

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