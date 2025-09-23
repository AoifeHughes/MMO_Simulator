from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from enum import Enum
import time
import math

class GoalPriority(Enum):
    CRITICAL = 1    # Emergency situations (under attack, health critical)
    HIGH = 2        # Important objectives (combat, specific orders)
    MEDIUM = 3      # Normal behavior (patrolling, exploring)
    LOW = 4         # Idle behavior (random movement, waiting)

class GoalStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"

class BaseGoal(ABC):
    def __init__(self, goal_id: str, priority: GoalPriority, timeout: float = 30.0):
        self.goal_id = goal_id
        self.priority = priority
        self.status = GoalStatus.PENDING
        self.created_time = time.time()
        self.timeout = timeout
        self.last_update_time = 0
        self.update_interval = 0.1  # Minimum time between updates (100ms)

    @abstractmethod
    def can_start(self, agent) -> bool:
        """Check if this goal can be started by the agent"""
        pass

    @abstractmethod
    def start(self, agent) -> bool:
        """Start executing this goal. Returns True if successfully started."""
        pass

    @abstractmethod
    def update(self, agent, delta_time: float) -> GoalStatus:
        """Update goal execution. Returns current status."""
        pass

    @abstractmethod
    def stop(self, agent):
        """Stop executing this goal and clean up"""
        pass

    def should_update(self) -> bool:
        """Check if enough time has passed to update this goal"""
        current_time = time.time()
        return current_time - self.last_update_time >= self.update_interval

    def mark_updated(self):
        """Mark that this goal was just updated"""
        self.last_update_time = time.time()

    def is_expired(self) -> bool:
        """Check if this goal has timed out"""
        return time.time() - self.created_time > self.timeout

    def can_be_interrupted_by(self, other_goal: 'BaseGoal') -> bool:
        """Check if this goal can be interrupted by another goal"""
        # Higher priority goals can interrupt lower priority ones
        return other_goal.priority.value < self.priority.value

class MoveToPositionGoal(BaseGoal):
    def __init__(self, target_x: float, target_y: float, priority: GoalPriority = GoalPriority.MEDIUM,
                 threshold: float = 1.0, timeout: float = 30.0):
        super().__init__(f"move_to_{target_x}_{target_y}", priority, timeout)
        self.target_x = target_x
        self.target_y = target_y
        self.threshold = threshold
        self.path_started = False

    def can_start(self, agent) -> bool:
        return True

    def start(self, agent) -> bool:
        self.status = GoalStatus.ACTIVE
        self.path_started = False
        return True

    def update(self, agent, delta_time: float) -> GoalStatus:
        if not self.should_update():
            return self.status

        self.mark_updated()

        # Check if we've reached the target
        dx = self.target_x - agent.x
        dy = self.target_y - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance <= self.threshold:
            agent.stop_movement()
            return GoalStatus.COMPLETED

        # Start movement if not already started
        if not self.path_started:
            # Try pathfinding first if available
            if agent.agent_map and agent.find_path_to(self.target_x, self.target_y):
                self.path_started = True
            else:
                # Fall back to direct movement
                agent.move_direct(self.target_x, self.target_y)
                self.path_started = True

        # Check if we're stuck (not moving towards target)
        if self.path_started and not agent.current_path:
            # If pathfinding completed but we're not at target, try direct movement
            if distance > self.threshold:
                agent.move_direct(self.target_x, self.target_y)

        return GoalStatus.ACTIVE

    def stop(self, agent):
        agent.stop_movement()
        self.status = GoalStatus.INTERRUPTED

class PatrolGoal(BaseGoal):
    def __init__(self, patrol_points: List[tuple], priority: GoalPriority = GoalPriority.MEDIUM):
        super().__init__("patrol", priority, timeout=float('inf'))  # Patrol never times out
        self.patrol_points = patrol_points
        self.current_index = 0
        self.current_move_goal: Optional[MoveToPositionGoal] = None

    def can_start(self, agent) -> bool:
        return len(self.patrol_points) > 0

    def start(self, agent) -> bool:
        self.status = GoalStatus.ACTIVE
        self.current_index = 0
        self._start_next_waypoint(agent)
        return True

    def _start_next_waypoint(self, agent):
        if self.current_index < len(self.patrol_points):
            target = self.patrol_points[self.current_index]
            self.current_move_goal = MoveToPositionGoal(
                target[0], target[1],
                priority=self.priority,
                threshold=0.5,
                timeout=15.0
            )
            self.current_move_goal.start(agent)

    def update(self, agent, delta_time: float) -> GoalStatus:
        if not self.should_update():
            return self.status

        self.mark_updated()

        if not self.current_move_goal:
            self._start_next_waypoint(agent)
            return GoalStatus.ACTIVE

        # Update current movement goal
        move_status = self.current_move_goal.update(agent, delta_time)

        if move_status == GoalStatus.COMPLETED:
            # Move to next patrol point
            self.current_index = (self.current_index + 1) % len(self.patrol_points)
            self._start_next_waypoint(agent)
        elif move_status == GoalStatus.FAILED:
            # Skip to next patrol point
            self.current_index = (self.current_index + 1) % len(self.patrol_points)
            self._start_next_waypoint(agent)

        return GoalStatus.ACTIVE

    def stop(self, agent):
        if self.current_move_goal:
            self.current_move_goal.stop(agent)
        agent.stop_movement()
        self.status = GoalStatus.INTERRUPTED

class ChaseTargetGoal(BaseGoal):
    def __init__(self, target_id: str, chase_range: float = 15.0, attack_range: float = 2.0):
        super().__init__(f"chase_{target_id}", GoalPriority.HIGH, timeout=10.0)
        self.target_id = target_id
        self.chase_range = chase_range
        self.attack_range = attack_range
        self.last_target_position = None

    def can_start(self, agent) -> bool:
        target = self._find_target(agent)
        return target is not None

    def start(self, agent) -> bool:
        self.status = GoalStatus.ACTIVE
        return True

    def _find_target(self, agent):
        """Find the target entity in visible entities"""
        for entity in getattr(agent, 'visible_entities', []):
            if entity.get('id') == self.target_id:
                return entity
        return None

    def update(self, agent, delta_time: float) -> GoalStatus:
        if not self.should_update():
            return self.status

        self.mark_updated()

        target = self._find_target(agent)
        if not target:
            agent.stop_movement()
            return GoalStatus.FAILED

        target_x, target_y = target['x'], target['y']
        dx = target_x - agent.x
        dy = target_y - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        # Check if target is in attack range
        if distance <= self.attack_range:
            agent.stop_movement()
            return GoalStatus.COMPLETED  # Ready to attack

        # Check if target is out of chase range
        if distance > self.chase_range:
            agent.stop_movement()
            return GoalStatus.FAILED

        # Move towards target (only if position changed significantly)
        if (self.last_target_position is None or
            abs(target_x - self.last_target_position[0]) > 1.0 or
            abs(target_y - self.last_target_position[1]) > 1.0):

            if agent.agent_map and agent.find_path_to(target_x, target_y):
                pass  # Pathfinding will handle movement
            else:
                agent.move_direct(target_x, target_y)

            self.last_target_position = (target_x, target_y)

        return GoalStatus.ACTIVE

    def stop(self, agent):
        agent.stop_movement()
        self.status = GoalStatus.INTERRUPTED

class GoalManager:
    def __init__(self):
        self.goals: List[BaseGoal] = []
        self.current_goal: Optional[BaseGoal] = None

    def add_goal(self, goal: BaseGoal, agent) -> bool:
        """Add a goal to the queue. Returns True if goal was started immediately."""
        # Check if this goal should interrupt current goal
        if self.current_goal and self.current_goal.can_be_interrupted_by(goal):
            self.current_goal.stop(agent)
            self.current_goal = None

        # Insert goal in priority order
        inserted = False
        for i, existing_goal in enumerate(self.goals):
            if goal.priority.value < existing_goal.priority.value:
                self.goals.insert(i, goal)
                inserted = True
                break

        if not inserted:
            self.goals.append(goal)

        # Start goal immediately if no current goal
        if not self.current_goal:
            return self._start_next_goal(agent)

        return False

    def _start_next_goal(self, agent) -> bool:
        """Start the next available goal"""
        while self.goals:
            goal = self.goals.pop(0)

            # Remove expired goals
            if goal.is_expired():
                continue

            if goal.can_start(agent) and goal.start(agent):
                self.current_goal = goal
                return True

        self.current_goal = None
        return False

    def update(self, agent, delta_time: float):
        """Update the current goal"""
        if not self.current_goal:
            self._start_next_goal(agent)
            return

        status = self.current_goal.update(agent, delta_time)

        if status in [GoalStatus.COMPLETED, GoalStatus.FAILED]:
            self.current_goal = None
            self._start_next_goal(agent)

    def clear_goals(self, agent):
        """Clear all goals and stop current activity"""
        if self.current_goal:
            self.current_goal.stop(agent)
            self.current_goal = None
        self.goals.clear()

    def has_active_goal(self) -> bool:
        """Check if there's an active goal"""
        return self.current_goal is not None

    def get_current_goal_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the current goal for debugging"""
        if self.current_goal:
            return {
                'goal_id': self.current_goal.goal_id,
                'priority': self.current_goal.priority.name,
                'status': self.current_goal.status.value,
                'time_active': time.time() - self.current_goal.created_time
            }
        return None