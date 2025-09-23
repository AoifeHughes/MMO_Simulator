import math
import time
from typing import Any, Dict, List, Optional, Tuple

from client.agent import BaseAgent


class PathfindingTestAgent(BaseAgent):
    def __init__(
        self,
        agent_id: str,
        x: float,
        y: float,
        test_waypoints: List[Tuple[float, float]] = None,
    ):
        super().__init__(agent_id, x, y, "pathfinding_test")
        self.test_waypoints = test_waypoints or [
            (10, 10),
            (90, 10),
            (90, 90),
            (10, 90),
            (50, 50),
            (10, 10),
        ]
        self.current_waypoint_index = 0
        self.waypoint_reached_threshold = 1.0
        self.movement_state = "moving_to_waypoint"
        self.last_position_update = time.time()

        # Movement tracking for tests
        self.visited_waypoints = []
        self.movement_history = []
        self.start_time = time.time()

    def update(self, delta_time: float):
        # Update pathfinding state
        self.update_pathfinding(delta_time)

        # Record position for testing
        current_time = time.time()
        if current_time - self.last_position_update >= 0.1:  # Record every 100ms
            self.movement_history.append(
                {
                    "time": current_time - self.start_time,
                    "position": (self.x, self.y),
                    "target_waypoint": self.get_current_target_waypoint(),
                    "pathfinding_active": self.current_path is not None,
                }
            )
            self.last_position_update = current_time

        if self.movement_state == "moving_to_waypoint":
            self.move_to_next_waypoint()
        elif self.movement_state == "completed":
            self.stop_movement()

        # Apply movement using the velocity system
        self.move(delta_time)

    def move_to_next_waypoint(self):
        if self.current_waypoint_index >= len(self.test_waypoints):
            self.movement_state = "completed"
            self.stop_movement()
            return

        target_waypoint = self.test_waypoints[self.current_waypoint_index]
        target_x, target_y = target_waypoint

        # Check if we've reached the current waypoint
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance <= self.waypoint_reached_threshold:
            # Waypoint reached
            self.visited_waypoints.append(
                {
                    "waypoint": target_waypoint,
                    "time_reached": time.time() - self.start_time,
                    "actual_position": (self.x, self.y),
                }
            )

            self.current_waypoint_index += 1
            self.stop_movement()  # Clear any existing path

            if self.current_waypoint_index < len(self.test_waypoints):
                # Move to next waypoint
                next_target = self.test_waypoints[self.current_waypoint_index]
                self.start_movement_to(next_target[0], next_target[1])
            else:
                self.movement_state = "completed"
        else:
            # Continue moving to current waypoint
            if not self.current_path and not self.current_waypoint:
                # No active pathfinding, start movement
                self.start_movement_to(target_x, target_y)

    def start_movement_to(self, target_x: float, target_y: float):
        """Start movement to target position using pathfinding or direct movement"""
        # Try pathfinding first if agent_map is available
        if self.agent_map and self.find_path_to(target_x, target_y):
            return  # Pathfinding will handle movement
        else:
            # Fall back to direct movement
            self.move_direct(target_x, target_y)

    def get_current_target_waypoint(self) -> Optional[Tuple[float, float]]:
        """Get the current target waypoint"""
        if self.current_waypoint_index < len(self.test_waypoints):
            return self.test_waypoints[self.current_waypoint_index]
        return None

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        self.visible_entities = visible_entities

    def decide(self) -> Optional[Dict[str, Any]]:
        # This agent doesn't need to make decisions, it just follows waypoints
        return None

    def get_test_results(self) -> Dict[str, Any]:
        """Get test results for validation"""
        return {
            "visited_waypoints": self.visited_waypoints,
            "movement_history": self.movement_history,
            "current_waypoint_index": self.current_waypoint_index,
            "total_waypoints": len(self.test_waypoints),
            "completed": self.movement_state == "completed",
            "current_position": (self.x, self.y),
            "total_test_time": time.time() - self.start_time,
        }
