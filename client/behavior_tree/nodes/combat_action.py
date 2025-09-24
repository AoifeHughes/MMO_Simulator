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
        # Pathfinding support
        self.current_path: Optional[List[Tuple[float, float]]] = None
        self.path_target_id: Optional[str] = None
        self.last_pathfind_time = 0
        self.pathfind_cooldown = 1.0  # Recalculate path every 1 second max

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
            self._clear_pathfinding_state()
            return NodeStatus.FAILURE

        target_x = self.current_target["x"]
        target_y = self.current_target["y"]
        target_id = self.current_target["id"]

        # Check if target is too far (give up chase)
        dx = target_x - agent.x
        dy = target_y - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > self.chase_range:
            self._clear_pathfinding_state()
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

        # Check if we've reached the target
        if distance <= optimal_range:
            self._clear_pathfinding_state()
            return NodeStatus.SUCCESS

        # Determine if we need pathfinding by checking for obstacles
        needs_pathfinding = self._check_needs_pathfinding(agent, target_x, target_y)

        if needs_pathfinding:
            # Use pathfinding for complex navigation
            success = self._update_pathfinding_movement(agent, target_x, target_y, target_id, optimal_range, current_time)
            if not success:
                # Fallback: try to get closer using direct movement, but give up after some time
                if not hasattr(self, 'fallback_start_time'):
                    self.fallback_start_time = current_time
                    logger.debug(f"Agent {agent.id[:8]} pathfinding failed, trying fallback movement")

                # Give up if fallback has been going too long
                if current_time - self.fallback_start_time > 3.0:  # 3 second timeout
                    logger.warning(f"Agent {agent.id[:8]} fallback timeout, giving up chase")
                    return NodeStatus.FAILURE

                # Try direct movement as fallback
                self._update_direct_movement(agent, target_x, target_y, optimal_range)
            else:
                # Reset fallback timer on successful pathfinding
                if hasattr(self, 'fallback_start_time'):
                    delattr(self, 'fallback_start_time')
        else:
            # Use direct movement for simple cases
            self._update_direct_movement(agent, target_x, target_y, optimal_range)

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        # Use movement manager to stop smoothly
        movement_manager = agent.get_movement_manager()
        movement_manager.stop_movement(agent)
        self.current_target = None
        self._clear_pathfinding_state()

    def _clear_pathfinding_state(self):
        """Clear pathfinding state when target is lost or reached"""
        self.current_path = None
        self.path_target_id = None

    def _check_needs_pathfinding(self, agent, target_x: float, target_y: float) -> bool:
        """Check if direct movement to target would hit obstacles"""
        # Get agent map for pathfinding
        if not hasattr(agent, 'agent_map') or agent.agent_map is None:
            return False  # No map knowledge, use direct movement

        # Quick check: if direct line crosses known unwalkable terrain, use pathfinding
        agent_map = agent.agent_map
        start_x, start_y = int(agent.x), int(agent.y)
        target_tile_x, target_tile_y = int(target_x), int(target_y)

        # Use simple line algorithm to check tiles along path
        dx = abs(target_tile_x - start_x)
        dy = abs(target_tile_y - start_y)
        x, y = start_x, start_y
        sx = 1 if start_x < target_tile_x else -1
        sy = 1 if start_y < target_tile_y else -1

        if dx > dy:
            err = dx / 2.0
            while x != target_tile_x:
                x += sx
                err -= dy
                if err < 0:
                    y += sy
                    err += dx

                # Check if this tile is known and unwalkable
                if (agent_map.is_tile_known(x, y) and
                    not agent_map.is_walkable(x, y)):
                    logger.debug(f"Agent {agent.id[:8]} detected obstacle at ({x},{y}), using pathfinding")
                    return True
        else:
            err = dy / 2.0
            while y != target_tile_y:
                y += sy
                err -= dx
                if err < 0:
                    x += sx
                    err += dy

                # Check if this tile is known and unwalkable
                if (agent_map.is_tile_known(x, y) and
                    not agent_map.is_walkable(x, y)):
                    logger.debug(f"Agent {agent.id[:8]} detected obstacle at ({x},{y}), using pathfinding")
                    return True

        return False

    def _update_pathfinding_movement(self, agent, target_x: float, target_y: float,
                                   target_id: str, optimal_range: float, current_time: float) -> bool:
        """Update movement using pathfinding to avoid obstacles"""
        # Check if we need to recalculate path
        should_recalculate = (
            self.current_path is None or
            self.path_target_id != target_id or
            current_time - self.last_pathfind_time > self.pathfind_cooldown
        )

        if should_recalculate:
            # Calculate new path using agent's pathfinding system
            if hasattr(agent, 'agent_map') and hasattr(agent, 'pathfinder'):
                start_pos = (agent.x, agent.y)
                goal_pos = (target_x, target_y)

                self.current_path = agent.pathfinder.find_path(agent.agent_map, start_pos, goal_pos)
                self.path_target_id = target_id
                self.last_pathfind_time = current_time

                if not self.current_path:
                    logger.warning(f"Agent {agent.id[:8]} could not find path to target at ({target_x:.1f}, {target_y:.1f})")
                    return False
                else:
                    logger.debug(f"Agent {agent.id[:8]} found path with {len(self.current_path)} waypoints")
            else:
                logger.warning(f"Agent {agent.id[:8]} missing pathfinding components")
                return False

        # Follow the path
        if self.current_path:
            # Get next waypoint
            next_waypoint = agent.pathfinder.get_next_waypoint(
                self.current_path, (agent.x, agent.y), waypoint_threshold=0.5
            )

            if next_waypoint:
                # Use movement manager with pathfinding mode
                movement_manager = agent.get_movement_manager()
                from client.behavior_tree.movement_manager import MovementMode

                movement_manager.update_movement(
                    agent,
                    next_waypoint,
                    mode=MovementMode.PATHFINDING,  # Use pathfinding mode for waypoints
                    arrival_threshold=0.5  # Closer threshold for waypoints
                )
                return True

        return False

    def _update_direct_movement(self, agent, target_x: float, target_y: float, optimal_range: float):
        """Update movement using direct path (no obstacles detected)"""
        # Use movement manager for smooth chasing
        movement_manager = agent.get_movement_manager()
        target_pos = (target_x, target_y)

        # Import here to avoid circular import
        from client.behavior_tree.movement_manager import MovementMode

        movement_manager.update_movement(
            agent,
            target_pos,
            mode=MovementMode.CHASE,
            arrival_threshold=optimal_range
        )

    # Removed _find_nearest_enemy - now using unified TargetManager
