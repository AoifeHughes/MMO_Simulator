import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"
    READY = "ready"


class BehaviorNode(ABC):
    """Abstract base class for all behavior tree nodes"""

    def __init__(self, name: str):
        self.name = name
        self.parent: Optional["BehaviorNode"] = None
        self.status = NodeStatus.READY
        self.last_execution_time = 0
        self.execution_count = 0
        self.start_time = 0

    @abstractmethod
    def execute(self, agent, delta_time: float) -> NodeStatus:
        """Execute this node and return the status"""
        pass

    def reset(self):
        """Reset the node to its initial state"""
        self.status = NodeStatus.READY
        self.start_time = 0

    def set_parent(self, parent: "BehaviorNode"):
        """Set the parent node"""
        self.parent = parent

    def get_root(self) -> "BehaviorNode":
        """Get the root node of the tree"""
        if self.parent is None:
            return self
        return self.parent.get_root()

    def get_path(self) -> str:
        """Get the path from root to this node for debugging"""
        if self.parent is None:
            return self.name
        return f"{self.parent.get_path()}/{self.name}"

    def log_execution(self, agent, status: NodeStatus):
        """Log node execution for debugging"""
        # Log all important node executions for debugging
        if (
            status == NodeStatus.SUCCESS
            or status == NodeStatus.FAILURE
            or not hasattr(self, "children")
        ):
            logger.info(
                f"[BT] Agent {agent.id[:8]} ({agent.agent_type}) - {self.get_path()}: {status.value}"
            )


class CompositeNode(BehaviorNode):
    """Base class for nodes that have multiple children"""

    def __init__(self, name: str, children: List[BehaviorNode] = None):
        super().__init__(name)
        self.children = children or []
        self.current_child_index = 0

        # Set parent references
        for child in self.children:
            child.set_parent(self)

    def add_child(self, child: BehaviorNode):
        """Add a child node"""
        child.set_parent(self)
        self.children.append(child)

    def reset(self):
        """Reset this node and all children"""
        super().reset()
        self.current_child_index = 0
        for child in self.children:
            child.reset()


class DecoratorNode(BehaviorNode):
    """Base class for nodes that modify the behavior of a single child"""

    def __init__(self, name: str, child: BehaviorNode):
        super().__init__(name)
        self.child = child
        child.set_parent(self)

    def reset(self):
        """Reset this node and its child"""
        super().reset()
        if self.child:
            self.child.reset()


class ConditionNode(BehaviorNode):
    """Base class for leaf nodes that check conditions"""

    def __init__(self, name: str):
        super().__init__(name)

    @abstractmethod
    def check_condition(self, agent) -> bool:
        """Check if the condition is met"""
        pass

    def execute(self, agent, delta_time: float) -> NodeStatus:
        """Execute the condition check"""
        self.execution_count += 1
        self.last_execution_time = time.time()

        if self.check_condition(agent):
            self.status = NodeStatus.SUCCESS
        else:
            self.status = NodeStatus.FAILURE

        self.log_execution(agent, self.status)
        return self.status


class ActionNode(BehaviorNode):
    """Base class for leaf nodes that perform actions"""

    def __init__(self, name: str):
        super().__init__(name)
        self.is_running = False

    @abstractmethod
    def start_action(self, agent) -> bool:
        """Start the action. Return True if started successfully."""
        pass

    @abstractmethod
    def update_action(self, agent, delta_time: float) -> NodeStatus:
        """Update the running action. Return current status."""
        pass

    @abstractmethod
    def stop_action(self, agent):
        """Stop/cleanup the action"""
        pass

    def execute(self, agent, delta_time: float) -> NodeStatus:
        """Execute the action"""
        self.execution_count += 1
        self.last_execution_time = time.time()

        # Start action if not already running
        if not self.is_running:
            if self.start_action(agent):
                self.is_running = True
                self.start_time = time.time()
            else:
                self.status = NodeStatus.FAILURE
                self.log_execution(agent, self.status)
                return self.status

        # Update running action
        self.status = self.update_action(agent, delta_time)

        # Stop action if completed or failed
        if self.status in [NodeStatus.SUCCESS, NodeStatus.FAILURE]:
            self.stop_action(agent)
            self.is_running = False

        self.log_execution(agent, self.status)
        return self.status

    def reset(self):
        """Reset the action node"""
        super().reset()
        self.is_running = False
