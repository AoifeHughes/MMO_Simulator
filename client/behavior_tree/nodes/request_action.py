"""
RequestAction Behavior Tree Node

This node integrates the new unified action system with behavior trees.
Instead of directly executing actions, behavior trees now REQUEST actions
from the server through the action manager.

This provides:
- Server-authoritative validation for all actions
- Client-side prediction for responsiveness
- Rollback support for rejected actions
- Unified request-response pattern
"""

import logging
import time
from typing import Any, Dict, Optional

from shared.actions import ActionPriority, ActionType
from .base import ActionNode, NodeStatus

logger = logging.getLogger(__name__)


class RequestAction(ActionNode):
    """
    Generic action node that requests actions through the action manager.

    This replaces direct action execution with server request-response pattern.
    """

    def __init__(
        self,
        name: str,
        action_type: ActionType,
        parameters: Dict[str, Any] = None,
        priority: ActionPriority = ActionPriority.NORMAL,
        predict: bool = True,
        timeout: float = 5.0,
    ):
        """
        Initialize RequestAction node.

        Args:
            name: Node name for debugging
            action_type: Type of action to request
            parameters: Static action parameters (can be overridden at runtime)
            priority: Action priority for server processing
            predict: Whether to apply client-side prediction
            timeout: Max time to wait for server response
        """
        super().__init__(name)
        self.action_type = action_type
        self.base_parameters = parameters or {}
        self.priority = priority
        self.predict = predict
        self.timeout = timeout

        # Execution state
        self.action_id: Optional[str] = None
        self.request_time: Optional[float] = None
        self.response_received = False
        self.final_result: Optional[NodeStatus] = None

    def start_action(self, agent) -> bool:
        """Start the action request"""
        if not hasattr(agent, 'action_manager'):
            logger.error(f"Agent {agent.id} does not have action_manager - cannot request actions")
            return False

        # Reset state
        self.action_id = None
        self.request_time = None
        self.response_received = False
        self.final_result = None

        return True

    def stop_action(self, agent) -> bool:
        """Stop the action request"""
        # Clean up any pending requests if needed
        self.action_id = None
        self.request_time = None
        self.response_received = False
        self.final_result = None
        return True

    async def update_action(self, agent, delta_time: float) -> NodeStatus:
        """Update the action request"""
        if not hasattr(agent, 'action_manager'):
            logger.error(f"Agent {agent.id} does not have action_manager")
            return NodeStatus.FAILURE

        # If we haven't sent the request yet, send it
        if self.action_id is None:
            parameters = self._build_parameters(agent)
            if parameters is None:
                logger.debug(f"Failed to build parameters for {self.name}")
                return NodeStatus.FAILURE

            try:
                self.action_id = await agent.action_manager.request_action(
                    action_type=self.action_type,
                    parameters=parameters,
                    priority=self.priority,
                    predict=self.predict,
                )
                self.request_time = time.time()
                logger.debug(f"Requested action {self.action_id} for agent {agent.id}")

                # Register callback to get notified when this action completes
                agent.action_manager.register_action_callback(
                    self.action_type,
                    self._make_response_callback()
                )

            except Exception as e:
                logger.error(f"Failed to request action {self.name}: {e}")
                return NodeStatus.FAILURE

        # Check for timeout
        if self.request_time and (time.time() - self.request_time) > self.timeout:
            logger.warning(f"Action {self.action_id} timed out after {self.timeout}s")
            return NodeStatus.FAILURE

        # If we got a response, return the final result
        if self.response_received and self.final_result is not None:
            return self.final_result

        # Still waiting for response
        return NodeStatus.RUNNING

    def _build_parameters(self, agent) -> Optional[Dict[str, Any]]:
        """Build action parameters at runtime (override in subclasses)"""
        return self.base_parameters.copy()

    def _make_response_callback(self):
        """Create callback for action response"""
        def callback(request, response, prediction):
            # Only handle responses for our specific action
            if request.action_id == self.action_id:
                self.response_received = True

                if response.result.value in ['approved', 'modified']:
                    self.final_result = NodeStatus.SUCCESS
                    logger.debug(f"Action {self.action_id} succeeded: {response.message}")
                else:
                    self.final_result = NodeStatus.FAILURE
                    logger.debug(f"Action {self.action_id} failed: {response.message}")

        return callback


class RequestMoveTo(RequestAction):
    """Request MOVE_TO action"""

    def __init__(
        self,
        target_x: float,
        target_y: float,
        speed_multiplier: float = 1.0,
        dynamic_target: bool = False,
    ):
        """
        Initialize RequestMoveTo node.

        Args:
            target_x: Target X coordinate (or callable if dynamic_target=True)
            target_y: Target Y coordinate (or callable if dynamic_target=True)
            speed_multiplier: Movement speed multiplier
            dynamic_target: If True, target_x/target_y are evaluated each update
        """
        self.target_x = target_x
        self.target_y = target_y
        self.speed_multiplier = speed_multiplier
        self.dynamic_target = dynamic_target

        super().__init__(
            name=f"RequestMoveTo_{target_x}_{target_y}",
            action_type=ActionType.MOVE_TO,
            priority=ActionPriority.NORMAL,
            predict=True,
        )

    def _make_response_callback(self):
        """Create callback for movement action response with position sync handling"""
        def callback(request, response, prediction):
            # Only handle responses for our specific action
            if request.action_id == self.action_id:
                self.response_received = True

                if response.result.value in ['approved', 'modified']:
                    self.final_result = NodeStatus.SUCCESS
                    logger.debug(f"Movement {self.action_id} succeeded: {response.message}")
                else:
                    self.final_result = NodeStatus.FAILURE
                    logger.debug(f"Movement {self.action_id} rejected: {response.message}")

                    # Handle position sync for rejected movements
                    if hasattr(response, 'approved_parameters') and response.approved_parameters:
                        server_x = response.approved_parameters.get('server_position_x')
                        server_y = response.approved_parameters.get('server_position_y')
                        if server_x is not None and server_y is not None:
                            logger.debug(f"Server reports agent position as ({server_x:.2f}, {server_y:.2f})")
                            # Note: Position reconciliation will happen through normal position sync

        return callback

    def _build_parameters(self, agent) -> Optional[Dict[str, Any]]:
        """Build movement parameters"""
        if self.dynamic_target:
            # Evaluate target coordinates dynamically
            if callable(self.target_x):
                target_x = self.target_x(agent)
            else:
                target_x = self.target_x

            if callable(self.target_y):
                target_y = self.target_y(agent)
            else:
                target_y = self.target_y
        else:
            target_x = self.target_x
            target_y = self.target_y

        return {
            "target_x": float(target_x),
            "target_y": float(target_y),
            "current_x": float(agent.x),
            "current_y": float(agent.y),
            "speed_multiplier": self.speed_multiplier,
        }


class RequestAttack(RequestAction):
    """Request ATTACK_TARGET action"""

    def __init__(
        self,
        target_id: str = None,
        attack_name: str = "punch",
        target_selector: callable = None,
    ):
        """
        Initialize RequestAttack node.

        Args:
            target_id: Static target ID (if known)
            attack_name: Name of attack to use
            target_selector: Function to select target dynamically: target_selector(agent) -> target_id
        """
        self.static_target_id = target_id
        self.attack_name = attack_name
        self.target_selector = target_selector

        super().__init__(
            name=f"RequestAttack_{attack_name}",
            action_type=ActionType.ATTACK_TARGET,
            priority=ActionPriority.HIGH,
            predict=False,  # Don't predict combat actions
        )

    def _build_parameters(self, agent) -> Optional[Dict[str, Any]]:
        """Build attack parameters"""
        # Determine target
        if self.target_selector:
            target_id = self.target_selector(agent)
        elif self.static_target_id:
            target_id = self.static_target_id
        else:
            logger.error("No target specified for attack")
            return None

        if not target_id:
            logger.debug("No valid target found for attack")
            return None

        return {
            "target_id": target_id,
            "attack_name": self.attack_name,
        }


class RequestStopMovement(RequestAction):
    """Request STOP_MOVEMENT action"""

    def __init__(self):
        super().__init__(
            name="RequestStopMovement",
            action_type=ActionType.STOP_MOVEMENT,
            priority=ActionPriority.NORMAL,
            predict=True,
        )

    def _build_parameters(self, agent) -> Optional[Dict[str, Any]]:
        """No parameters needed for stop movement"""
        return {}


# Helper functions for creating common action nodes

def create_move_to_entity(entity_types: list, distance: float = 1.0) -> RequestMoveTo:
    """Create a RequestMoveTo that targets the nearest entity of specified types"""

    def get_target_x(agent):
        entity = agent.get_nearest_entity_of_type(entity_types)
        return entity["x"] if entity else agent.x

    def get_target_y(agent):
        entity = agent.get_nearest_entity_of_type(entity_types)
        return entity["y"] if entity else agent.y

    return RequestMoveTo(
        target_x=get_target_x,
        target_y=get_target_y,
        dynamic_target=True,
    )


def create_attack_nearest(enemy_types: list, attack_name: str = "punch") -> RequestAttack:
    """Create a RequestAttack that targets the nearest enemy"""

    def select_target(agent):
        entity = agent.get_nearest_entity_of_type(enemy_types)
        return entity["id"] if entity else None

    return RequestAttack(
        attack_name=attack_name,
        target_selector=select_target,
    )


def create_chase_and_attack(enemy_types: list, attack_name: str = "punch", attack_range: float = 2.0):
    """Create a composite behavior that chases then attacks enemies"""
    from .composite import PrioritySelector, Sequence
    from .condition import DistanceToTarget

    return PrioritySelector(
        "ChaseAndAttack",
        [
            # Attack if in range
            Sequence(
                "AttackSequence",
                [
                    # Check if enemy is in range (would need to be updated for new system)
                    # DistanceToTarget(enemy_types, attack_range),
                    create_attack_nearest(enemy_types, attack_name),
                ]
            ),
            # Otherwise chase
            create_move_to_entity(enemy_types),
        ]
    )