from typing import Dict, Any, List, Optional
from client.agent import BaseAgent
import random
import math
import time

class NPCAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "npc")
        self.behavior_state = "idle"
        self.wander_target = None
        self.idle_time = 0
        self.max_idle_time = random.uniform(2, 5)
        self.wander_radius = 15.0
        self.home_x = x
        self.home_y = y

    def update(self, delta_time: float):
        # Update pathfinding state
        self.update_pathfinding(delta_time)

        if self.behavior_state == "idle":
            self.idle_time += delta_time
            if not self.current_path:  # Only stop if not pathfinding
                self.velocity_x = 0
                self.velocity_y = 0
            if self.idle_time >= self.max_idle_time:
                self.start_wandering()

        elif self.behavior_state == "wandering":
            # Check if pathfinding is handling movement
            if self.current_path:
                # Pathfinding is active, check if we've reached destination
                if not self.current_waypoint:
                    # Path completed
                    self.behavior_state = "idle"
                    self.idle_time = 0
                    self.max_idle_time = random.uniform(2, 5)
                    self.wander_target = None
            elif self.wander_target:
                # Fallback to direct movement if no pathfinding
                dx = self.wander_target[0] - self.x
                dy = self.wander_target[1] - self.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance > 0.5:
                    wander_speed = self.speed * 0.5
                    self.velocity_x = (dx / distance) * wander_speed
                    self.velocity_y = (dy / distance) * wander_speed
                    self.rotation = math.degrees(math.atan2(dy, dx))
                else:
                    self.behavior_state = "idle"
                    self.idle_time = 0
                    self.max_idle_time = random.uniform(2, 5)
                    self.wander_target = None
                    self.velocity_x = 0
                    self.velocity_y = 0

        # Apply movement using the velocity system
        self.move(delta_time)

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        self.visible_entities = visible_entities

        for entity in visible_entities:
            if entity.get('type') == 'player':
                if self.behavior_state == "idle":
                    self.behavior_state = "alert"
                    break

    def decide(self) -> Optional[Dict[str, Any]]:
        if self.behavior_state == "alert":
            self.behavior_state = "idle"
            return {
                'type': 'emote',
                'emote': 'wave'
            }
        return None

    def start_wandering(self):
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(3, self.wander_radius)

        target_x = self.home_x + math.cos(angle) * distance
        target_y = self.home_y + math.sin(angle) * distance

        self.wander_target = (target_x, target_y)
        self.behavior_state = "wandering"

        # Try pathfinding first, fall back to direct movement
        if not self.find_path_to(target_x, target_y):
            # No path found, use direct movement
            dx = target_x - self.x
            dy = target_y - self.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                self.velocity_x = (dx / dist) * self.speed * 0.5
                self.velocity_y = (dy / dist) * self.speed * 0.5