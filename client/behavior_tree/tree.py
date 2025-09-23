import logging
import time
from typing import Any, Dict, List, Optional

from .nodes.base import BehaviorNode, NodeStatus

logger = logging.getLogger(__name__)


class BehaviorTree:
    """
    Main behavior tree coordinator that manages execution of behavior trees.
    Provides stable execution with built-in evaluation throttling.
    """

    def __init__(self, root_node: BehaviorNode, name: str = "BehaviorTree"):
        self.root_node = root_node
        self.name = name
        self.last_update_time = 0
        self.update_interval = 0.1  # Minimum time between evaluations (100ms)
        self.execution_count = 0
        self.last_status = NodeStatus.READY
        self.performance_stats = {
            "total_executions": 0,
            "avg_execution_time": 0,
            "last_execution_time": 0,
            "status_history": [],
        }

    def update(self, agent, delta_time: float) -> NodeStatus:
        """
        Update the behavior tree. Returns current status.
        Includes built-in throttling to prevent excessive evaluation.
        """
        current_time = time.time()

        # Check if enough time has passed for another evaluation
        if current_time - self.last_update_time < self.update_interval:
            return self.last_status

        # Record start time for performance tracking
        start_time = current_time

        # Execute the root node
        self.execution_count += 1
        self.last_update_time = current_time

        # Log tree execution start
        logger.debug(f"[BT] Agent {agent.id[:8]} executing tree {self.name}")

        try:
            status = self.root_node.execute(agent, delta_time)
            self.last_status = status

            # Log result
            action_path = self.get_current_action_path()
            if action_path:
                logger.debug(f"[BT] Agent {agent.id[:8]} current action: {action_path}")
            logger.debug(f"[BT] Agent {agent.id[:8]} tree status: {status.value}")

            # Reset tree if execution completed
            if status in [NodeStatus.SUCCESS, NodeStatus.FAILURE]:
                self.root_node.reset()

        except Exception as e:
            logger.error(
                f"Error executing behavior tree {self.name} for agent {agent.id[:8]}: {e}"
            )
            status = NodeStatus.FAILURE
            self.last_status = status

        # Update performance statistics
        execution_time = time.time() - start_time
        self._update_performance_stats(execution_time, status)

        return status

    def reset(self):
        """Reset the entire behavior tree to initial state"""
        self.root_node.reset()
        self.last_status = NodeStatus.READY
        self.execution_count = 0

    def set_update_interval(self, interval: float):
        """Set the minimum time between tree evaluations"""
        self.update_interval = max(0.016, interval)  # Minimum 16ms (60fps)

    def get_status(self) -> NodeStatus:
        """Get the last execution status"""
        return self.last_status

    def get_current_action_path(self) -> str:
        """Get the path of currently executing nodes for debugging"""
        return self._get_executing_path(self.root_node)

    def _get_executing_path(self, node: BehaviorNode) -> str:
        """Recursively find the path of currently executing nodes"""
        if node.status == NodeStatus.RUNNING:
            # Check children for running nodes
            if hasattr(node, "children"):
                for child in node.children:
                    child_path = self._get_executing_path(child)
                    if child_path:
                        return f"{node.name}/{child_path}"

            if hasattr(node, "child") and node.child:
                child_path = self._get_executing_path(node.child)
                if child_path:
                    return f"{node.name}/{child_path}"

            # Leaf node that's running
            return node.name

        return ""

    def _update_performance_stats(self, execution_time: float, status: NodeStatus):
        """Update performance tracking statistics"""
        stats = self.performance_stats

        stats["total_executions"] += 1
        stats["last_execution_time"] = execution_time

        # Update average execution time
        if stats["avg_execution_time"] == 0:
            stats["avg_execution_time"] = execution_time
        else:
            # Rolling average
            stats["avg_execution_time"] = (stats["avg_execution_time"] * 0.9) + (
                execution_time * 0.1
            )

        # Keep limited status history
        stats["status_history"].append((time.time(), status))
        if len(stats["status_history"]) > 100:
            stats["status_history"].pop(0)

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for debugging/optimization"""
        return self.performance_stats.copy()

    def get_debug_info(self, agent) -> Dict[str, Any]:
        """Get comprehensive debug information about tree state"""
        return {
            "tree_name": self.name,
            "agent_id": agent.id[:8],
            "last_status": self.last_status.value,
            "execution_count": self.execution_count,
            "update_interval": self.update_interval,
            "current_action_path": self.get_current_action_path(),
            "performance": self.get_performance_stats(),
            "root_node_status": self.root_node.status.value,
            "time_since_last_update": time.time() - self.last_update_time,
        }


class BehaviorTreeBuilder:
    """
    Helper class for building behavior trees with a fluent interface.
    Makes it easier to construct complex behavior trees.
    """

    def __init__(self):
        self.stack: List[BehaviorNode] = []

    def priority_selector(self, name: str = "PrioritySelector"):
        """Add a priority selector node"""
        from .nodes import PrioritySelector

        node = PrioritySelector(name)
        self._add_node(node)
        return self

    def sequence(self, name: str = "Sequence"):
        """Add a sequence node"""
        from .nodes import Sequence

        node = Sequence(name)
        self._add_node(node)
        return self

    def parallel(self, name: str = "Parallel", required_successes: int = 1):
        """Add a parallel node"""
        from .nodes import Parallel

        node = Parallel(name, required_successes=required_successes)
        self._add_node(node)
        return self

    def cooldown(self, duration: float, name: str = None):
        """Add a cooldown decorator"""
        from .nodes import CooldownDecorator

        if not name:
            name = f"Cooldown_{duration}"

        def decorator_func(child):
            return CooldownDecorator(name, child, duration)

        self._add_decorator(decorator_func)
        return self

    def timer(self, duration: float, name: str = None):
        """Add a timer decorator"""
        from .nodes import TimerDecorator

        if not name:
            name = f"Timer_{duration}"

        def decorator_func(child):
            return TimerDecorator(name, child, duration)

        self._add_decorator(decorator_func)
        return self

    def condition(self, condition_node: BehaviorNode):
        """Add a condition node"""
        self._add_node(condition_node)
        return self

    def action(self, action_node: BehaviorNode):
        """Add an action node"""
        self._add_node(action_node)
        return self

    def end(self):
        """End current composite/decorator and return to parent"""
        if len(self.stack) > 1:
            self.stack.pop()
        return self

    def build(self, name: str = "BehaviorTree") -> BehaviorTree:
        """Build and return the behavior tree"""
        if not self.stack:
            raise ValueError("No nodes added to behavior tree")

        root_node = self.stack[0]
        return BehaviorTree(root_node, name)

    def _add_node(self, node: BehaviorNode):
        """Add a node to the current level"""
        if self.stack:
            current = self.stack[-1]
            if hasattr(current, "add_child"):
                current.add_child(node)
            else:
                raise ValueError(f"Cannot add child to {type(current).__name__}")

        self.stack.append(node)

    def _add_decorator(self, decorator_func):
        """Add a decorator that will wrap the next added child"""
        # This is a placeholder for decorator logic
        # For now, decorators need to be created manually
        pass
