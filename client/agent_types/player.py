from typing import Dict, Any, List, Optional
from client.agent import BaseAgent
import math

class PlayerAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "player")
        self.target_x = x
        self.target_y = y
        self.is_moving = False
        self.input_buffer = []

    def update(self, delta_time: float):
        # Update pathfinding state
        self.update_pathfinding(delta_time)

        # If no active pathfinding, use direct movement
        if self.is_moving and not self.current_path:
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 0.1:
                self.velocity_x = (dx / distance) * self.speed
                self.velocity_y = (dy / distance) * self.speed
                self.rotation = math.degrees(math.atan2(dy, dx))
            else:
                self.is_moving = False
                self.velocity_x = 0
                self.velocity_y = 0

        # Apply movement using the velocity system
        self.move(delta_time)

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        self.visible_entities = visible_entities

    def decide(self) -> Optional[Dict[str, Any]]:
        if self.input_buffer:
            action = self.input_buffer.pop(0)
            return action
        return None

    def handle_input(self, input_type: str, data: Dict[str, Any]):
        if input_type == "move_to":
            self.target_x = data['x']
            self.target_y = data['y']

            # Try pathfinding first, fall back to direct movement
            if not self.find_path_to(self.target_x, self.target_y):
                # No path found, use direct movement
                self.is_moving = True
                self.move_direct(self.target_x, self.target_y)
            else:
                # Pathfinding active, stop direct movement
                self.is_moving = False

            self.input_buffer.append({
                'type': 'move',
                'target_x': self.target_x,
                'target_y': self.target_y
            })

        elif input_type == "stop":
            self.is_moving = False
            self.stop_movement()  # This clears both velocity and pathfinding
            self.input_buffer.append({'type': 'stop'})

        elif input_type == "attack":
            target_id = data.get('target_id')
            if target_id:
                self.input_buffer.append({
                    'type': 'attack',
                    'target_id': target_id
                })

    def get_visible_entity_info(self) -> List[Dict[str, Any]]:
        return self.visible_entities