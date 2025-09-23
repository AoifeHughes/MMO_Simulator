import math
import time
from typing import Optional, List, Dict, Any
from .base import ConditionNode
import logging

logger = logging.getLogger(__name__)

class HealthBelowThreshold(ConditionNode):
    """Check if agent health is below a threshold"""

    def __init__(self, threshold: float):
        super().__init__(f"HealthBelow{threshold}")
        self.threshold = threshold

    def check_condition(self, agent) -> bool:
        is_low_health = agent.health <= self.threshold

        # Force intention change for emergency health situations
        if is_low_health and hasattr(agent, 'force_intention'):
            agent.force_intention("Emergency")

        return is_low_health


class HealthAboveThreshold(ConditionNode):
    """Check if agent health is above a threshold"""

    def __init__(self, threshold: float):
        super().__init__(f"HealthAbove{threshold}")
        self.threshold = threshold

    def check_condition(self, agent) -> bool:
        return agent.health >= self.threshold


class EnemyInRange(ConditionNode):
    """Check if any enemy is within specified range"""

    def __init__(self, range_distance: float, enemy_types: List[str] = None):
        super().__init__(f"EnemyInRange{range_distance}")
        self.range_distance = range_distance
        self.enemy_types = enemy_types or ["enemy", "player"]  # Default enemy types
        self.detected_enemy: Optional[Dict[str, Any]] = None

    def check_condition(self, agent) -> bool:
        self.detected_enemy = None

        for entity in getattr(agent, 'visible_entities', []):
            # Fix: Use 'agent_type' instead of 'type' since entities come from AgentData.to_dict()
            if entity.get('agent_type') in self.enemy_types and entity.get('id') != agent.id:
                dx = entity['x'] - agent.x
                dy = entity['y'] - agent.y
                distance = math.sqrt(dx * dx + dy * dy)

                logger.debug(f"[ENEMY_DETECT] Agent {agent.id[:8]} sees {entity.get('agent_type')} at distance {distance:.1f} (threshold: {self.range_distance})")

                if distance <= self.range_distance:
                    self.detected_enemy = entity
                    logger.info(f"[COMBAT] Agent {agent.id[:8]} ({agent.agent_type}) detected enemy {entity.get('agent_type')} at {distance:.1f} units!")
                    return True

        return False

    def get_detected_enemy(self) -> Optional[Dict[str, Any]]:
        """Get the last detected enemy for use in actions"""
        return self.detected_enemy


class DistanceToTarget(ConditionNode):
    """Check if distance to target is within specified range"""

    def __init__(self, target_x: float, target_y: float, max_distance: float, min_distance: float = 0):
        super().__init__(f"DistanceToTarget{max_distance}")
        self.target_x = target_x
        self.target_y = target_y
        self.max_distance = max_distance
        self.min_distance = min_distance

    def check_condition(self, agent) -> bool:
        dx = self.target_x - agent.x
        dy = self.target_y - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        return self.min_distance <= distance <= self.max_distance

    def update_target(self, target_x: float, target_y: float):
        """Update the target position"""
        self.target_x = target_x
        self.target_y = target_y


class TargetVisible(ConditionNode):
    """Check if a specific target is visible"""

    def __init__(self, target_id: str):
        super().__init__(f"TargetVisible_{target_id[:8]}")
        self.target_id = target_id
        self.visible_target: Optional[Dict[str, Any]] = None

    def check_condition(self, agent) -> bool:
        self.visible_target = None

        for entity in getattr(agent, 'visible_entities', []):
            if entity.get('id') == self.target_id:
                self.visible_target = entity
                return True

        return False

    def get_visible_target(self) -> Optional[Dict[str, Any]]:
        """Get the visible target data"""
        return self.visible_target


class PathExists(ConditionNode):
    """Check if a path exists to target location"""

    def __init__(self, target_x: float, target_y: float):
        super().__init__(f"PathExists_{target_x}_{target_y}")
        self.target_x = target_x
        self.target_y = target_y

    def check_condition(self, agent) -> bool:
        if not hasattr(agent, 'pathfinder') or not hasattr(agent, 'agent_map'):
            return False

        if not agent.agent_map:
            return False

        # Use pathfinder to check if path exists
        path = agent.pathfinder.find_path(
            agent.agent_map,
            (agent.x, agent.y),
            (self.target_x, self.target_y)
        )

        return path is not None and len(path) > 0

    def update_target(self, target_x: float, target_y: float):
        """Update the target position"""
        self.target_x = target_x
        self.target_y = target_y


class TimeSinceLastAction(ConditionNode):
    """Check if enough time has passed since last action"""

    def __init__(self, action_name: str, min_time: float):
        super().__init__(f"TimeSince{action_name}_{min_time}")
        self.action_name = action_name
        self.min_time = min_time

    def check_condition(self, agent) -> bool:
        last_action_time = getattr(agent, f'last_{self.action_name}_time', 0)
        return time.time() - last_action_time >= self.min_time


class IsAgentType(ConditionNode):
    """Check if agent matches specific type"""

    def __init__(self, agent_type: str):
        super().__init__(f"IsAgentType_{agent_type}")
        self.agent_type = agent_type

    def check_condition(self, agent) -> bool:
        return getattr(agent, 'agent_type', None) == self.agent_type


class HasTarget(ConditionNode):
    """Check if agent has a current target"""

    def __init__(self):
        super().__init__("HasTarget")

    def check_condition(self, agent) -> bool:
        return getattr(agent, 'current_target', None) is not None


class IsStuck(ConditionNode):
    """Check if agent appears to be stuck (not moving)"""

    def __init__(self, stuck_threshold: float = 1.0, time_threshold: float = 2.0):
        super().__init__(f"IsStuck_{stuck_threshold}_{time_threshold}")
        self.stuck_threshold = stuck_threshold
        self.time_threshold = time_threshold

    def check_condition(self, agent) -> bool:
        last_position = getattr(agent, 'last_position', None)
        last_position_time = getattr(agent, 'last_position_time', None)

        if last_position is None or last_position_time is None:
            return False

        current_time = time.time()
        if current_time - last_position_time < self.time_threshold:
            return False

        dx = agent.x - last_position[0]
        dy = agent.y - last_position[1]
        distance_moved = math.sqrt(dx * dx + dy * dy)

        return distance_moved < self.stuck_threshold


class IsIdle(ConditionNode):
    """Check if agent is currently idle"""

    def __init__(self):
        super().__init__("IsIdle")

    def check_condition(self, agent) -> bool:
        # Check if agent has no velocity
        velocity_x = getattr(agent, 'velocity_x', 0)
        velocity_y = getattr(agent, 'velocity_y', 0)
        velocity = math.sqrt(velocity_x * velocity_x + velocity_y * velocity_y)

        # Check if agent has no current path or target
        has_path = getattr(agent, 'current_path', None) is not None
        has_target = getattr(agent, 'current_target', None) is not None

        return velocity < 0.1 and not has_path and not has_target


class NearOtherAgent(ConditionNode):
    """Check if another agent of specified type is nearby"""

    def __init__(self, agent_types: List[str], max_distance: float):
        super().__init__(f"NearOther_{max_distance}")
        self.agent_types = agent_types
        self.max_distance = max_distance
        self.nearby_agent: Optional[Dict[str, Any]] = None

    def check_condition(self, agent) -> bool:
        self.nearby_agent = None

        for entity in getattr(agent, 'visible_entities', []):
            if (entity.get('agent_type') in self.agent_types and
                entity.get('id') != agent.id):

                dx = entity['x'] - agent.x
                dy = entity['y'] - agent.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance <= self.max_distance:
                    self.nearby_agent = entity
                    return True

        return False

    def get_nearby_agent(self) -> Optional[Dict[str, Any]]:
        """Get the nearby agent data"""
        return self.nearby_agent


class CustomCondition(ConditionNode):
    """Generic condition that accepts a lambda function"""

    def __init__(self, name: str, condition_func):
        super().__init__(name)
        self.condition_func = condition_func

    def check_condition(self, agent) -> bool:
        return self.condition_func(agent)