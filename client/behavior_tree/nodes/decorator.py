import time
import random
from .base import DecoratorNode, BehaviorNode, NodeStatus
import logging

logger = logging.getLogger(__name__)

class CooldownDecorator(DecoratorNode):
    """
    Prevents child execution if not enough time has passed since last execution.
    Helps prevent stuttering by enforcing minimum time between action switches.
    """

    def __init__(self, name: str, child: BehaviorNode, cooldown_duration: float):
        super().__init__(name, child)
        self.cooldown_duration = cooldown_duration
        self.last_success_time = 0

    def execute(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Check if we're still in cooldown
        if current_time - self.last_success_time < self.cooldown_duration:
            self.status = NodeStatus.FAILURE
            self.log_execution(agent, self.status)
            return self.status

        # Execute child
        status = self.child.execute(agent, delta_time)

        # Update last success time if child succeeded
        if status == NodeStatus.SUCCESS:
            self.last_success_time = current_time

        self.status = status
        self.log_execution(agent, self.status)
        return self.status

    def reset(self):
        """Reset but preserve cooldown timing"""
        super().reset()
        # Don't reset last_success_time - cooldown persists across resets


class TimerDecorator(DecoratorNode):
    """
    Ensures child runs for at least minimum_duration before allowing it to complete.
    Prevents rapid action switching by enforcing minimum execution time.
    """

    def __init__(self, name: str, child: BehaviorNode, minimum_duration: float):
        super().__init__(name, child)
        self.minimum_duration = minimum_duration
        self.start_time = 0

    def execute(self, agent, delta_time: float) -> NodeStatus:
        current_time = time.time()

        # Start timing on first execution
        if self.status == NodeStatus.READY:
            self.start_time = current_time

        # Execute child
        child_status = self.child.execute(agent, delta_time)

        # If child is still running, pass through the status
        if child_status == NodeStatus.RUNNING:
            self.status = NodeStatus.RUNNING
            self.log_execution(agent, self.status)
            return self.status

        # Check if minimum duration has passed
        elapsed_time = current_time - self.start_time
        if elapsed_time < self.minimum_duration:
            # Force child to keep running even if it wants to complete
            self.status = NodeStatus.RUNNING
            self.log_execution(agent, self.status)
            return self.status

        # Minimum duration met, allow child status through
        self.status = child_status
        self.log_execution(agent, self.status)
        return self.status

    def reset(self):
        super().reset()
        self.start_time = 0


class RepeatDecorator(DecoratorNode):
    """
    Repeats child execution a specified number of times or indefinitely.
    """

    def __init__(self, name: str, child: BehaviorNode, repeat_count: int = -1):
        super().__init__(name, child)
        self.repeat_count = repeat_count  # -1 for infinite
        self.current_count = 0

    def execute(self, agent, delta_time: float) -> NodeStatus:
        # Check if we've reached repeat limit
        if self.repeat_count > 0 and self.current_count >= self.repeat_count:
            self.status = NodeStatus.SUCCESS
            self.log_execution(agent, self.status)
            return self.status

        # Execute child
        child_status = self.child.execute(agent, delta_time)

        if child_status == NodeStatus.RUNNING:
            self.status = NodeStatus.RUNNING
            self.log_execution(agent, self.status)
            return self.status

        # Child completed (success or failure)
        self.current_count += 1

        # Reset child for next iteration
        self.child.reset()

        # Check if we should continue repeating
        if self.repeat_count < 0 or self.current_count < self.repeat_count:
            self.status = NodeStatus.RUNNING  # Continue repeating
        else:
            self.status = NodeStatus.SUCCESS  # Completed all repetitions

        self.log_execution(agent, self.status)
        return self.status

    def reset(self):
        super().reset()
        self.current_count = 0


class InverterDecorator(DecoratorNode):
    """
    Inverts the result of child execution.
    SUCCESS becomes FAILURE, FAILURE becomes SUCCESS.
    RUNNING remains RUNNING.
    """

    def __init__(self, name: str, child: BehaviorNode):
        super().__init__(name, child)

    def execute(self, agent, delta_time: float) -> NodeStatus:
        child_status = self.child.execute(agent, delta_time)

        if child_status == NodeStatus.SUCCESS:
            self.status = NodeStatus.FAILURE
        elif child_status == NodeStatus.FAILURE:
            self.status = NodeStatus.SUCCESS
        else:  # RUNNING
            self.status = child_status

        self.log_execution(agent, self.status)
        return self.status


class ProbabilityDecorator(DecoratorNode):
    """
    Executes child with a given probability.
    Adds randomness to behavior for more natural movement.
    """

    def __init__(self, name: str, child: BehaviorNode, probability: float):
        super().__init__(name, child)
        self.probability = max(0.0, min(1.0, probability))  # Clamp to 0-1
        self.rolled = False
        self.will_execute = False

    def execute(self, agent, delta_time: float) -> NodeStatus:
        # Roll probability on first execution
        if not self.rolled:
            self.will_execute = random.random() < self.probability
            self.rolled = True

        if not self.will_execute:
            self.status = NodeStatus.FAILURE
            self.log_execution(agent, self.status)
            return self.status

        # Execute child
        self.status = self.child.execute(agent, delta_time)
        self.log_execution(agent, self.status)
        return self.status

    def reset(self):
        super().reset()
        self.rolled = False
        self.will_execute = False


class InterruptibleDecorator(DecoratorNode):
    """
    Allows child to be interrupted by higher priority conditions.
    Used for actions that can be stopped when more important things happen.
    """

    def __init__(self, name: str, child: BehaviorNode, can_be_interrupted: bool = True):
        super().__init__(name, child)
        self.can_be_interrupted = can_be_interrupted
        self.was_interrupted = False

    def execute(self, agent, delta_time: float) -> NodeStatus:
        # Check if we were interrupted from outside
        if self.was_interrupted:
            self.child.reset()
            self.was_interrupted = False
            self.status = NodeStatus.FAILURE
            self.log_execution(agent, self.status)
            return self.status

        # Execute child normally
        self.status = self.child.execute(agent, delta_time)
        self.log_execution(agent, self.status)
        return self.status

    def interrupt(self):
        """Force interruption of this decorator's child"""
        if self.can_be_interrupted:
            self.was_interrupted = True

    def reset(self):
        super().reset()
        self.was_interrupted = False