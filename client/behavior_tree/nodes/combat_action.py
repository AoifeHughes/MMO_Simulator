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
        # Use unified target manager for consistent target selection
        target_manager = agent.get_target_manager()
        self.current_target = target_manager.update_target_selection(
            agent,
            agent.visible_entities,
            self.enemy_types,
            max_range=self.attack_range * 1.5  # Allow targets slightly outside immediate range
        )

        if not self.current_target:
            return False

        # Check if target is in attack range
        dx = self.current_target["x"] - agent.x
        dy = self.current_target["y"] - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        return distance <= self.attack_range

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Check attack cooldown
        if current_time - self.last_attack_time < self.attack_cooldown:
            return NodeStatus.RUNNING

        # Use target manager to get current target (with persistence)
        target_manager = agent.get_target_manager()
        self.current_target = target_manager.update_target_selection(
            agent,
            agent.visible_entities,
            self.enemy_types,
            max_range=self.attack_range * 1.5
        )

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

    # Removed _find_nearest_enemy - now using unified TargetManager


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
        # Use unified target manager for consistent target selection
        target_manager = agent.get_target_manager()
        self.current_target = target_manager.update_target_selection(
            agent,
            agent.visible_entities,
            self.enemy_types,
            max_range=self.chase_range
        )
        return self.current_target is not None

    def update_action(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Use target manager to maintain target consistency
        target_manager = agent.get_target_manager()
        self.current_target = target_manager.update_target_selection(
            agent,
            agent.visible_entities,
            self.enemy_types,
            max_range=self.chase_range
        )

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

        # Get optimal attack range from server data if available
        optimal_range = 2.0  # Default safe attack range
        if hasattr(agent, 'get_attack_data'):
            # Try to get the best available attack range
            for attack_name in ['sword_slash', 'claw', 'punch']:
                attack_data = agent.get_attack_data(attack_name)
                if attack_data:
                    optimal_range = min(optimal_range, attack_data.get('max_range', 2.0) * 0.8)
                    break

        # Use movement manager for smooth chasing
        movement_manager = agent.get_movement_manager()
        target_pos = (target_x, target_y)

        # Import here to avoid circular import
        from client.behavior_tree.movement_manager import MovementMode

        arrived = movement_manager.update_movement(
            agent,
            target_pos,
            mode=MovementMode.CHASE,
            arrival_threshold=optimal_range
        )

        if arrived or distance <= optimal_range:
            return NodeStatus.SUCCESS

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        # Use movement manager to stop smoothly
        movement_manager = agent.get_movement_manager()
        movement_manager.stop_movement(agent)
        self.current_target = None

    # Removed _find_nearest_enemy - now using unified TargetManager
