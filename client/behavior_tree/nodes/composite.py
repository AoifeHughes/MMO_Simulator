import logging
from typing import List

from .base import BehaviorNode, CompositeNode, NodeStatus

logger = logging.getLogger(__name__)


class PrioritySelector(CompositeNode):
    """
    Executes children in order until one succeeds.
    Returns SUCCESS if any child succeeds.
    Returns FAILURE if all children fail.
    Returns RUNNING if a child is running.

    Respects agent intention cooldown to prevent rapid switching.
    """

    def __init__(self, name: str, children: List[BehaviorNode] = None):
        super().__init__(name, children)
        self.active_child_index = -1  # Track which child is currently active

    def execute(self, agent, delta_time: float) -> NodeStatus:
        self.execution_count += 1

        # If we have an active child and can't change intention, stick with it
        if (
            self.active_child_index >= 0
            and hasattr(agent, "can_change_intention")
            and not agent.can_change_intention()
        ):
            # Continue executing the currently active child
            if self.active_child_index < len(self.children):
                active_child = self.children[self.active_child_index]
                status = active_child.execute(agent, delta_time)

                if status == NodeStatus.RUNNING:
                    self.status = NodeStatus.RUNNING
                    return self.status
                elif status == NodeStatus.SUCCESS:
                    self.status = NodeStatus.SUCCESS
                    return self.status
                # If child failed, we'll fall through to try other children

        # Normal priority selection (intention change allowed or no active child)
        for i, child in enumerate(self.children):
            status = child.execute(agent, delta_time)

            if status == NodeStatus.SUCCESS:
                # Child succeeded, track intention change if needed
                if i != self.active_child_index and hasattr(agent, "set_intention"):
                    agent.set_intention(child.name)

                self.active_child_index = i

                # Reset other children
                for j, other_child in enumerate(self.children):
                    if j != i:
                        other_child.reset()

                self.status = NodeStatus.SUCCESS
                self.log_execution(agent, self.status)
                return self.status

            elif status == NodeStatus.RUNNING:
                # Child is running, track intention change if needed
                if i != self.active_child_index and hasattr(agent, "set_intention"):
                    agent.set_intention(child.name)

                self.active_child_index = i

                # Reset other children
                for j, other_child in enumerate(self.children):
                    if j != i:
                        other_child.reset()

                self.status = NodeStatus.RUNNING
                self.log_execution(agent, self.status)
                return self.status

            # Child failed, try next child
            child.reset()

        # All children failed
        self.active_child_index = -1
        self.status = NodeStatus.FAILURE
        self.log_execution(agent, self.status)
        return self.status

    def reset(self):
        """Reset the selector and all children"""
        super().reset()
        self.active_child_index = -1


class Sequence(CompositeNode):
    """
    Executes children in order until one fails or all succeed.
    Returns SUCCESS if all children succeed.
    Returns FAILURE if any child fails.
    Returns RUNNING if a child is running.
    """

    def __init__(self, name: str, children: List[BehaviorNode] = None):
        super().__init__(name, children)

    def execute(self, agent, delta_time: float) -> NodeStatus:
        self.execution_count += 1

        for i in range(self.current_child_index, len(self.children)):
            child = self.children[i]
            status = child.execute(agent, delta_time)

            if status == NodeStatus.FAILURE:
                # Child failed, reset and return failure
                self.reset()
                self.status = NodeStatus.FAILURE
                self.log_execution(agent, self.status)
                return self.status

            elif status == NodeStatus.RUNNING:
                # Child is running, store current position and return running
                self.current_child_index = i
                self.status = NodeStatus.RUNNING
                self.log_execution(agent, self.status)
                return self.status

            # Child succeeded, continue to next child
            self.current_child_index = i + 1

        # All children succeeded
        self.reset()
        self.status = NodeStatus.SUCCESS
        self.log_execution(agent, self.status)
        return self.status


class Parallel(CompositeNode):
    """
    Executes all children simultaneously.
    Returns SUCCESS if required_successes children succeed.
    Returns FAILURE if too many children fail to reach required_successes.
    Returns RUNNING if still waiting for results.
    """

    def __init__(
        self,
        name: str,
        children: List[BehaviorNode] = None,
        required_successes: int = 1,
    ):
        super().__init__(name, children)
        self.required_successes = min(required_successes, len(self.children))

    def execute(self, agent, delta_time: float) -> NodeStatus:
        self.execution_count += 1

        success_count = 0
        failure_count = 0
        running_count = 0

        for child in self.children:
            status = child.execute(agent, delta_time)

            if status == NodeStatus.SUCCESS:
                success_count += 1
            elif status == NodeStatus.FAILURE:
                failure_count += 1
            elif status == NodeStatus.RUNNING:
                running_count += 1

        # Check if we have enough successes
        if success_count >= self.required_successes:
            # Stop any running children
            for child in self.children:
                if child.status == NodeStatus.RUNNING:
                    child.reset()
            self.status = NodeStatus.SUCCESS
            self.log_execution(agent, self.status)
            return self.status

        # Check if we can never reach required successes
        max_possible_successes = success_count + running_count
        if max_possible_successes < self.required_successes:
            self.reset()
            self.status = NodeStatus.FAILURE
            self.log_execution(agent, self.status)
            return self.status

        # Still waiting for more results
        self.status = NodeStatus.RUNNING
        self.log_execution(agent, self.status)
        return self.status
