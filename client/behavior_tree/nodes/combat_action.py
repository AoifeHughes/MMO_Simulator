"""
Combat-specific action nodes that work with behavior trees
"""

import logging
import math
import time
from typing import Any, Dict, Optional

from .base import ActionNode, NodeStatus

logger = logging.getLogger(__name__)


class AttackNearestEnemy(ActionNode):
    """Attack the nearest visible enemy"""

    def __init__(
        self,
        attack_name: str = "punch",
        damage: float = 10.0,
        attack_range: float = 3.0,
        enemy_types: list = None,
    ):
        super().__init__("AttackNearestEnemy")
        self.attack_name = attack_name
        self.damage = damage  # Fallback for legacy code
        self.attack_range = attack_range  # Fallback for legacy code
        self.enemy_types = enemy_types or ["enemy", "player"]
        self.last_attack_time = 0
        self.attack_cooldown = 1.0
        self.current_target: Optional[Dict[str, Any]] = None

    def start_action(self, agent) -> bool:
        self.current_target = self._find_nearest_enemy(agent)
        if not self.current_target:
            return False

        # Check if target is in range
        dx = self.current_target["x"] - agent.x
        dy = self.current_target["y"] - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        return distance <= self.attack_range

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Check attack cooldown
        if current_time - self.last_attack_time < self.attack_cooldown:
            return NodeStatus.RUNNING

        # Validate current target is still alive and visible
        if self.current_target:
            target_still_valid = False
            for entity in getattr(agent, "visible_entities", []):
                if entity.get("id") == self.current_target["id"] and entity.get(
                    "is_alive", True
                ):
                    target_still_valid = True
                    break

            if not target_still_valid:
                self.current_target = None

        # Find current target
        self.current_target = self._find_nearest_enemy(agent)
        if not self.current_target:
            return NodeStatus.FAILURE

        # Check if still in range
        dx = self.current_target["x"] - agent.x
        dy = self.current_target["y"] - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > self.attack_range:
            return NodeStatus.FAILURE

        # Stop movement and face target during attack
        agent.velocity_x = 0
        agent.velocity_y = 0

        # Calculate rotation to face target
        target_angle = math.degrees(math.atan2(dy, dx))
        agent.rotation = target_angle


        # Perform attack
        self.last_attack_time = current_time
        setattr(agent, "last_attack_time", current_time)

        logger.info(
            f"[ATTACK] Agent {agent.id[:8]} ({agent.agent_type}) attacking {self.current_target['id'][:8]} for {self.damage} damage"
        )

        # Send damage action to server
        damage_action = {
            "type": "damage",
            "target_id": self.current_target["id"],
            "attack_name": self.attack_name,
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
        # Stop movement when attack action ends
        agent.velocity_x = 0
        agent.velocity_y = 0
        self.current_target = None

    def _find_nearest_enemy(self, agent) -> Optional[Dict[str, Any]]:
        """Find the nearest enemy in visible entities"""
        nearest_enemy = None
        nearest_distance = float("inf")

        for entity in getattr(agent, "visible_entities", []):
            # Check if entity is an enemy type, alive, and not the agent itself
            if (
                entity.get("agent_type") in self.enemy_types
                and entity.get("id") != agent.id
                and entity.get(
                    "is_alive", True
                )  # Default to True for legacy compatibility
            ):
                dx = entity["x"] - agent.x
                dy = entity["y"] - agent.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_enemy = entity

        return nearest_enemy


class ChaseNearestEnemy(ActionNode):
    """Chase the nearest visible enemy"""

    def __init__(self, enemy_types: list = None, chase_range: float = 15.0):
        super().__init__("ChaseNearestEnemy")
        self.enemy_types = enemy_types or ["enemy", "player"]
        self.chase_range = chase_range
        self.current_target: Optional[Dict[str, Any]] = None
        self.last_movement_update = 0
        self.movement_update_interval = (
            0.3  # Update movement every 300ms to reduce jittering
        )

    def start_action(self, agent) -> bool:
        self.current_target = self._find_nearest_enemy(agent)
        return self.current_target is not None

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Validate current target is still alive and visible
        if self.current_target:
            target_still_valid = False
            for entity in getattr(agent, "visible_entities", []):
                if entity.get("id") == self.current_target["id"] and entity.get(
                    "is_alive", True
                ):
                    target_still_valid = True
                    break

            if not target_still_valid:
                self.current_target = None

        # Update target (enemies might move)
        self.current_target = self._find_nearest_enemy(agent)
        if not self.current_target:
            return NodeStatus.FAILURE

        target_x = self.current_target["x"]
        target_y = self.current_target["y"]

        # Check if target is too far (give up chase)
        dx = target_x - agent.x
        dy = target_y - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > self.chase_range:
            return NodeStatus.FAILURE

        # Only update movement periodically to reduce jitter
        if current_time - self.last_movement_update >= self.movement_update_interval:
            if distance > 0:
                agent.velocity_x = (dx / distance) * agent.speed
                agent.velocity_y = (dy / distance) * agent.speed
                agent.rotation = math.degrees(math.atan2(dy, dx))
                self.last_movement_update = current_time
                logger.debug(
                    f"[CHASE] Agent {agent.id[:8]} updated chase velocity toward {self.current_target['id'][:8]}"
                )

        # Success when close enough for attack - use smaller attack range for coordination
        if distance <= 2.0:  # Allow room for different attack ranges
            agent.velocity_x = 0
            agent.velocity_y = 0
            return NodeStatus.SUCCESS

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        agent.velocity_x = 0
        agent.velocity_y = 0
        self.current_target = None

    def _find_nearest_enemy(self, agent) -> Optional[Dict[str, Any]]:
        """Find the nearest enemy in visible entities"""
        nearest_enemy = None
        nearest_distance = float("inf")

        for entity in getattr(agent, "visible_entities", []):
            # Check if entity is an enemy type, alive, and not the agent itself
            if (
                entity.get("agent_type") in self.enemy_types
                and entity.get("id") != agent.id
                and entity.get(
                    "is_alive", True
                )  # Default to True for legacy compatibility
            ):
                dx = entity["x"] - agent.x
                dy = entity["y"] - agent.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_enemy = entity

        return nearest_enemy
