import logging
import math
import random
import time
from typing import Any, Dict, List, Optional, Tuple

from .base import ActionNode, NodeStatus

logger = logging.getLogger(__name__)


class MoveToTarget(ActionNode):
    """Move directly to a target position"""

    def __init__(self, target_x: float, target_y: float, threshold: float = 1.0):
        super().__init__(f"MoveToTarget_{target_x}_{target_y}")
        self.target_x = target_x
        self.target_y = target_y
        self.threshold = threshold
        self.last_movement_update = 0
        self.movement_update_interval = (
            0.2  # Update movement every 200ms to reduce jittering
        )

    def start_action(self, agent) -> bool:
        logger.debug(
            f"Starting MoveToTarget to ({self.target_x}, {self.target_y}) for agent {agent.id[:8]}"
        )
        return True

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()
        dx = self.target_x - agent.x
        dy = self.target_y - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance <= self.threshold:
            return NodeStatus.SUCCESS

        # Only update movement periodically to reduce jitter
        if current_time - self.last_movement_update >= self.movement_update_interval:
            if distance > 0:
                agent.velocity_x = (dx / distance) * agent.speed
                agent.velocity_y = (dy / distance) * agent.speed
                agent.rotation = math.degrees(math.atan2(dy, dx))
                self.last_movement_update = current_time

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        agent.velocity_x = 0
        agent.velocity_y = 0

    def update_target(self, target_x: float, target_y: float):
        """Update the target position"""
        self.target_x = target_x
        self.target_y = target_y
        self.name = f"MoveToTarget_{target_x}_{target_y}"


class MoveToEntity(ActionNode):
    """Move toward a specific entity"""

    def __init__(self, entity_id: str, threshold: float = 2.0):
        super().__init__(f"MoveToEntity_{entity_id[:8]}")
        self.entity_id = entity_id
        self.threshold = threshold
        self.target_entity: Optional[Dict[str, Any]] = None
        self.last_movement_update = 0
        self.movement_update_interval = (
            0.2  # Update movement every 200ms to reduce jittering
        )

    def start_action(self, agent) -> bool:
        self.target_entity = self._find_entity(agent)
        return self.target_entity is not None

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Update target entity position
        self.target_entity = self._find_entity(agent)
        if not self.target_entity:
            return NodeStatus.FAILURE

        target_x = self.target_entity["x"]
        target_y = self.target_entity["y"]

        dx = target_x - agent.x
        dy = target_y - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance <= self.threshold:
            return NodeStatus.SUCCESS

        # Only update movement periodically to reduce jitter
        if current_time - self.last_movement_update >= self.movement_update_interval:
            if distance > 0:
                agent.velocity_x = (dx / distance) * agent.speed
                agent.velocity_y = (dy / distance) * agent.speed
                agent.rotation = math.degrees(math.atan2(dy, dx))
                self.last_movement_update = current_time

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        agent.velocity_x = 0
        agent.velocity_y = 0

    def _find_entity(self, agent) -> Optional[Dict[str, Any]]:
        """Find the target entity in visible entities"""
        for entity in getattr(agent, "visible_entities", []):
            if entity.get("id") == self.entity_id:
                return entity
        return None


class Patrol(ActionNode):
    """Patrol between a list of waypoints"""

    def __init__(self, waypoints: List[Tuple[float, float]], loop: bool = True):
        super().__init__("Patrol")
        self.waypoints = waypoints
        self.loop = loop
        self.current_waypoint_index = 0
        self.move_action: Optional[MoveToTarget] = None

    def start_action(self, agent) -> bool:
        if not self.waypoints:
            return False

        self.current_waypoint_index = 0
        target = self.waypoints[self.current_waypoint_index]
        self.move_action = MoveToTarget(target[0], target[1])
        return self.move_action.start_action(agent)

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        if not self.move_action:
            return NodeStatus.FAILURE

        status = self.move_action.update_action(agent, delta_time)

        if status == NodeStatus.SUCCESS:
            # Move to next waypoint
            self.current_waypoint_index += 1

            # Check if we've completed the patrol
            if self.current_waypoint_index >= len(self.waypoints):
                if self.loop:
                    self.current_waypoint_index = 0
                else:
                    return NodeStatus.SUCCESS

            # Start moving to next waypoint
            target = self.waypoints[self.current_waypoint_index]
            self.move_action.update_target(target[0], target[1])

        return (
            NodeStatus.RUNNING if status != NodeStatus.FAILURE else NodeStatus.FAILURE
        )

    def stop_action(self, agent):
        if self.move_action:
            self.move_action.stop_action(agent)


class Wander(ActionNode):
    """Wander randomly around a center point"""

    def __init__(self, center_x: float, center_y: float, wander_radius: float = 10.0):
        super().__init__("Wander")
        self.center_x = center_x
        self.center_y = center_y
        self.wander_radius = wander_radius
        self.move_action: Optional[MoveToTarget] = None
        self.last_target_time = 0
        self.target_duration = 5.0  # How long to move toward each target

    def start_action(self, agent) -> bool:
        self._choose_new_target(agent)
        return self.move_action is not None

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Check if we need a new target
        if (
            not self.move_action
            or current_time - self.last_target_time > self.target_duration
            or self.move_action.update_action(agent, delta_time) == NodeStatus.SUCCESS
        ):
            self._choose_new_target(agent)

        # Continue moving toward current target
        return NodeStatus.RUNNING

    def stop_action(self, agent):
        if self.move_action:
            self.move_action.stop_action(agent)

    def _choose_new_target(self, agent):
        """Choose a new random target within wander radius"""
        angle = random.uniform(0, 2 * math.pi)
        distance = random.uniform(3, self.wander_radius)

        target_x = self.center_x + math.cos(angle) * distance
        target_y = self.center_y + math.sin(angle) * distance

        self.move_action = MoveToTarget(target_x, target_y, threshold=0.5)
        self.move_action.start_action(agent)
        self.last_target_time = time.time()


class Attack(ActionNode):
    """Attack a target entity"""

    def __init__(self, target_id: str, damage: float = 10.0, attack_range: float = 2.0):
        super().__init__(f"Attack_{target_id[:8]}")
        self.target_id = target_id
        self.damage = damage
        self.attack_range = attack_range
        self.last_attack_time = 0
        self.attack_cooldown = 1.0

    def start_action(self, agent) -> bool:
        target = self._find_target(agent)
        if not target:
            return False

        # Check if target is in range
        dx = target["x"] - agent.x
        dy = target["y"] - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        return distance <= self.attack_range

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Check attack cooldown
        if current_time - self.last_attack_time < self.attack_cooldown:
            return NodeStatus.RUNNING

        target = self._find_target(agent)
        if not target:
            return NodeStatus.FAILURE

        # Check if still in range
        dx = target["x"] - agent.x
        dy = target["y"] - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > self.attack_range:
            return NodeStatus.FAILURE

        # Perform attack
        self.last_attack_time = current_time
        setattr(agent, "last_attack_time", current_time)

        logger.info(
            f"[ATTACK] Agent {agent.id[:8]} ({agent.agent_type}) attacking {self.target_id[:8]} for {self.damage} damage"
        )

        # Send damage action to server
        damage_action = {
            "type": "damage",
            "target_id": self.target_id,
            "damage": self.damage,
            "attacker_id": agent.id,
            "position": {"x": agent.x, "y": agent.y},
        }

        # Queue the damage action to be sent to server
        if not hasattr(agent, "pending_actions"):
            agent.pending_actions = []
        agent.pending_actions.append(damage_action)

        # Set attack action time for tracking
        setattr(agent, "last_attack_action_time", current_time)

        return NodeStatus.SUCCESS

    def stop_action(self, agent):
        pass  # No cleanup needed for attack

    def _find_target(self, agent) -> Optional[Dict[str, Any]]:
        """Find the target entity"""
        for entity in getattr(agent, "visible_entities", []):
            if entity.get("id") == self.target_id:
                return entity
        return None


class Idle(ActionNode):
    """Remain idle for a specified duration"""

    def __init__(self, duration: float = 2.0):
        super().__init__(f"Idle_{duration}")
        self.duration = duration

    def start_action(self, agent) -> bool:
        return True

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        elapsed = time.time() - self.start_time

        if elapsed >= self.duration:
            return NodeStatus.SUCCESS

        # Ensure agent stops moving
        agent.velocity_x = 0
        agent.velocity_y = 0

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        pass


class Flee(ActionNode):
    """Flee from a target entity"""

    def __init__(self, threat_id: str, flee_distance: float = 20.0):
        super().__init__(f"Flee_{threat_id[:8]}")
        self.threat_id = threat_id
        self.flee_distance = flee_distance
        self.move_action: Optional[MoveToTarget] = None

    def start_action(self, agent) -> bool:
        threat = self._find_threat(agent)
        if not threat:
            return False

        # Calculate flee target (opposite direction from threat)
        dx = agent.x - threat["x"]
        dy = agent.y - threat["y"]
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 0:
            flee_x = agent.x + (dx / distance) * self.flee_distance
            flee_y = agent.y + (dy / distance) * self.flee_distance

            self.move_action = MoveToTarget(flee_x, flee_y, threshold=2.0)
            return self.move_action.start_action(agent)

        return False

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        if not self.move_action:
            return NodeStatus.FAILURE

        # Check if we're far enough from threat
        threat = self._find_threat(agent)
        if threat:
            dx = agent.x - threat["x"]
            dy = agent.y - threat["y"]
            distance = math.sqrt(dx * dx + dy * dy)

            if distance >= self.flee_distance:
                return NodeStatus.SUCCESS

        return self.move_action.update_action(agent, delta_time)

    def stop_action(self, agent):
        if self.move_action:
            self.move_action.stop_action(agent)

    def _find_threat(self, agent) -> Optional[Dict[str, Any]]:
        """Find the threat entity"""
        for entity in getattr(agent, "visible_entities", []):
            if entity.get("id") == self.threat_id:
                return entity
        return None


class Explore(ActionNode):
    """Explore by moving to unexplored areas"""

    def __init__(self, exploration_radius: float = 20.0, mode: str = "random"):
        super().__init__(f"Explore_{mode}")
        self.exploration_radius = exploration_radius
        self.mode = mode  # "random", "spiral", "frontier"
        self.move_action: Optional[MoveToTarget] = None
        self.explored_tiles = set()

    def start_action(self, agent) -> bool:
        self._choose_exploration_target(agent)
        return self.move_action is not None

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        if not self.move_action:
            return NodeStatus.FAILURE

        status = self.move_action.update_action(agent, delta_time)

        if status == NodeStatus.SUCCESS:
            # Mark current area as explored
            tile_x = int(agent.x)
            tile_y = int(agent.y)
            self.explored_tiles.add((tile_x, tile_y))

            # Choose new exploration target
            self._choose_exploration_target(agent)

        return (
            NodeStatus.RUNNING if status != NodeStatus.FAILURE else NodeStatus.FAILURE
        )

    def stop_action(self, agent):
        if self.move_action:
            self.move_action.stop_action(agent)

    def _choose_exploration_target(self, agent):
        """Choose next exploration target based on mode"""
        if self.mode == "random":
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(5, self.exploration_radius)
            target_x = agent.x + math.cos(angle) * distance
            target_y = agent.y + math.sin(angle) * distance
        else:
            # Default to random if mode not supported
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(5, self.exploration_radius)
            target_x = agent.x + math.cos(angle) * distance
            target_y = agent.y + math.sin(angle) * distance

        self.move_action = MoveToTarget(target_x, target_y, threshold=1.0)
        self.move_action.start_action(agent)
