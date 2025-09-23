from typing import Dict, Any, List, Optional
from client.agent import BaseAgent
from client.agent_goals import PatrolGoal, ChaseTargetGoal, GoalPriority
import math
import random
import time

class PlayerAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "player")
        self.target_id = None
        self.attack_range = 3.0
        self.chase_range = 20.0
        self.attack_cooldown = 1.5
        self.last_attack_time = 0
        self.last_goal_change_time = 0
        self.goal_change_cooldown = 0.5  # Prevent rapid goal switching

        # Setup defensive patrol area around spawn point
        self.patrol_points = self.setup_defensive_patrol(x, y)
        patrol_goal = PatrolGoal(self.patrol_points, GoalPriority.MEDIUM)
        self.goal_manager.add_goal(patrol_goal, self)

    def setup_defensive_patrol(self, spawn_x: float, spawn_y: float):
        """Setup a small defensive patrol area around spawn point"""
        patrol_points = []
        patrol_radius = 8.0
        for i in range(4):
            angle = (2 * math.pi / 4) * i
            px = spawn_x + math.cos(angle) * patrol_radius
            py = spawn_y + math.sin(angle) * patrol_radius
            patrol_points.append((px, py))
        return patrol_points

    def update(self, delta_time: float):
        # Update goal system (this handles all movement control)
        self.goal_manager.update(self, delta_time)

        # Apply movement using the velocity system
        self.move(delta_time)

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        self.visible_entities = visible_entities

        # Look for the closest enemy within chase range (defensive behavior)
        closest_enemy = None
        closest_distance = float('inf')

        for entity in visible_entities:
            if entity.get('type') == 'enemy':
                dx = entity['x'] - self.x
                dy = entity['y'] - self.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < closest_distance and distance <= self.chase_range:
                    closest_distance = distance
                    closest_enemy = entity

        # If we found an enemy and it's different from current target, start chasing
        if closest_enemy:
            new_target_id = closest_enemy['id']
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
            # No enemies visible, clear target if we had one
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
                    'damage': 15  # Players hit harder than enemies
                }

        return None