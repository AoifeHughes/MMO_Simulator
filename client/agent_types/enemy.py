from typing import Dict, Any, List, Optional
from client.agent import BaseAgent
from client.agent_goals import PatrolGoal, ChaseTargetGoal, GoalPriority
import math
import random
import time

class EnemyAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "enemy")
        self.target_id = None
        self.attack_range = 2.0
        self.chase_range = 15.0
        self.attack_cooldown = 1.0
        self.last_attack_time = 0
        self.aggression_level = random.uniform(0.5, 1.0)
        self.last_goal_change_time = 0
        self.goal_change_cooldown = 0.5  # Prevent rapid goal switching

        # Setup patrol route and start patrol goal
        self.patrol_points = self.setup_patrol_route()
        patrol_goal = PatrolGoal(self.patrol_points, GoalPriority.MEDIUM)
        self.goal_manager.add_goal(patrol_goal, self)

    def setup_patrol_route(self):
        patrol_points = []
        for i in range(3):
            angle = (2 * math.pi / 3) * i
            px = self.x + math.cos(angle) * 10
            py = self.y + math.sin(angle) * 10
            patrol_points.append((px, py))
        return patrol_points

    def update(self, delta_time: float):
        # Update goal system (this handles all movement control)
        self.goal_manager.update(self, delta_time)

        # Apply movement using the velocity system
        self.move(delta_time)


    def perceive(self, visible_entities: List[Dict[str, Any]]):
        self.visible_entities = visible_entities

        # Look for the closest player within chase range
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

        # If we found a target and it's different from current target, start chasing
        if closest_player:
            new_target_id = closest_player['id']
            current_time = time.time()
            if (new_target_id != self.target_id and
                current_time - self.last_goal_change_time > self.goal_change_cooldown):
                self.target_id = new_target_id
                self.last_goal_change_time = current_time
                chase_goal = ChaseTargetGoal(
                    target_id=new_target_id,
                    chase_range=self.chase_range,
                    attack_range=self.attack_range
                )
                self.goal_manager.add_goal(chase_goal, self)
        else:
            # No targets visible, clear target if we had one
            if self.target_id:
                self.target_id = None
                # Goal system will naturally fall back to patrol

    def decide(self) -> Optional[Dict[str, Any]]:
        # Check if we should attack based on current goal
        current_goal = self.goal_manager.current_goal
        if (current_goal and
            isinstance(current_goal, ChaseTargetGoal) and
            current_goal.status.value == "completed" and  # Goal completed means we're in attack range
            self.target_id):

            # Check attack cooldown
            current_time = time.time()
            if current_time - self.last_attack_time >= self.attack_cooldown:
                self.last_attack_time = current_time
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