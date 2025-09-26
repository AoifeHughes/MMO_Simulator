"""
Two-Phase Action System (MMO-Style)

This implements how real MMOs handle action-distance validation:

Phase 1: Position Confirmation
- Client requests "prepare for action" at target
- Server confirms valid position or suggests correction
- Agent moves to confirmed position

Phase 2: Action Execution
- Client requests actual action
- Server validates from confirmed position
- Action succeeds reliably

This prevents distance validation errors by ensuring proper positioning first.
"""

import time
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple, Any
import asyncio

logger = logging.getLogger(__name__)


class ActionPhase(Enum):
    """Phases of the two-phase action system"""
    POSITIONING = "positioning"     # Phase 1: Get into position
    EXECUTION = "execution"        # Phase 2: Execute the action
    COMPLETED = "completed"        # Action finished
    FAILED = "failed"             # Action failed


@dataclass
class ActionPreparation:
    """Represents an action being prepared"""
    request_id: str
    agent_id: str
    action_type: str              # "fishing", "harvest_wood", etc.
    target_x: float
    target_y: float

    # Positioning requirements
    required_distance: float = 1.2
    positioning_tolerance: float = 0.1

    # State tracking
    phase: ActionPhase = ActionPhase.POSITIONING
    confirmed_position: Optional[Tuple[float, float]] = None
    preparation_start_time: float = 0.0
    timeout_seconds: float = 10.0

    def __post_init__(self):
        if self.preparation_start_time == 0.0:
            self.preparation_start_time = time.time()


class ActionPositionCalculator:
    """Calculates optimal positions for different actions"""

    @staticmethod
    def calculate_action_position(action_type: str, target_x: float, target_y: float,
                                agent_x: float, agent_y: float) -> Tuple[float, float]:
        """Calculate where agent should stand to perform action"""

        if action_type in ["fishing", "harvest_wood"]:
            # For resource actions, position at exactly required distance
            required_distance = 1.0  # Safe distance that works reliably

            # Calculate direction from target to agent
            dx = agent_x - target_x
            dy = agent_y - target_y
            current_distance = (dx * dx + dy * dy) ** 0.5

            if current_distance < 0.1:  # Agent is on top of target
                # Default to positioning east of target
                return (target_x + required_distance, target_y)

            # Position at exactly required_distance from target
            normalized_dx = dx / current_distance
            normalized_dy = dy / current_distance

            optimal_x = target_x + normalized_dx * required_distance
            optimal_y = target_y + normalized_dy * required_distance

            return (optimal_x, optimal_y)

        # Default: current position is fine
        return (agent_x, agent_y)

    @staticmethod
    def validate_action_position(action_type: str, target_x: float, target_y: float,
                               agent_x: float, agent_y: float) -> Tuple[bool, float]:
        """Check if agent is properly positioned for action"""
        distance = ((target_x - agent_x) ** 2 + (target_y - agent_y) ** 2) ** 0.5

        if action_type in ["fishing", "harvest_wood"]:
            max_distance = 1.2  # Slightly generous for validation
            return distance <= max_distance, distance

        return True, distance


class TwoPhaseActionManager:
    """Manages two-phase action system on server side"""

    def __init__(self, world, agent_registry, action_processor):
        self.world = world
        self.agent_registry = agent_registry
        self.action_processor = action_processor

        # Track active action preparations
        self.active_preparations: Dict[str, ActionPreparation] = {}  # agent_id -> preparation
        self.completed_actions: Dict[str, Any] = {}

        # Statistics
        self.total_preparations = 0
        self.successful_actions = 0
        self.position_corrections = 0

    async def prepare_action(self, agent_id: str, action_type: str,
                           target_x: float, target_y: float) -> Dict[str, Any]:
        """
        Phase 1: Prepare for action by confirming position

        Returns preparation response with positioning instructions
        """
        self.total_preparations += 1
        request_id = f"prep_{int(time.time() * 1000)}_{agent_id[:8]}"

        agent = self.agent_registry.get_agent(agent_id)
        if not agent or not agent.is_alive:
            return {
                "success": False,
                "error": "Agent not found or not alive",
                "request_id": request_id
            }

        # Calculate optimal position for this action
        optimal_x, optimal_y = ActionPositionCalculator.calculate_action_position(
            action_type, target_x, target_y, agent.position[0], agent.position[1]
        )

        # Check if agent is already properly positioned
        is_positioned, distance = ActionPositionCalculator.validate_action_position(
            action_type, target_x, target_y, agent.position[0], agent.position[1]
        )

        # Create preparation object
        preparation = ActionPreparation(
            request_id=request_id,
            agent_id=agent_id,
            action_type=action_type,
            target_x=target_x,
            target_y=target_y
        )

        if is_positioned:
            # Agent is already in position - can proceed directly to execution
            preparation.phase = ActionPhase.EXECUTION
            preparation.confirmed_position = agent.position

            logger.info(f"✅ Action preparation: {agent_id[:8]} already positioned for {action_type} "
                       f"at distance {distance:.2f}")

            response = {
                "success": True,
                "request_id": request_id,
                "phase": "execution",
                "message": "Agent already positioned, ready for action",
                "confirmed_position": agent.position,
                "distance_to_target": distance
            }
        else:
            # Agent needs to move to optimal position
            movement_distance = ((optimal_x - agent.position[0]) ** 2 + (optimal_y - agent.position[1]) ** 2) ** 0.5

            if movement_distance > 0.1:  # Need to move
                self.position_corrections += 1

                logger.info(f"🎯 Action preparation: {agent_id[:8]} needs positioning for {action_type}. "
                           f"Current distance: {distance:.2f}, moving to ({optimal_x:.2f}, {optimal_y:.2f})")

                # Move agent to optimal position
                success = self.world.move_agent(agent_id, optimal_x, optimal_y, agent.rotation)

                if success:
                    preparation.confirmed_position = (optimal_x, optimal_y)
                    preparation.phase = ActionPhase.EXECUTION

                    response = {
                        "success": True,
                        "request_id": request_id,
                        "phase": "execution",
                        "message": f"Agent positioned for action (moved {movement_distance:.2f} units)",
                        "confirmed_position": (optimal_x, optimal_y),
                        "distance_to_target": 1.0  # Should be exactly right now
                    }
                else:
                    preparation.phase = ActionPhase.FAILED
                    response = {
                        "success": False,
                        "request_id": request_id,
                        "error": "Failed to move agent to optimal position",
                        "suggested_position": (optimal_x, optimal_y)
                    }
            else:
                # Very small adjustment, consider positioned
                preparation.phase = ActionPhase.EXECUTION
                preparation.confirmed_position = agent.position
                response = {
                    "success": True,
                    "request_id": request_id,
                    "phase": "execution",
                    "message": "Agent positioned for action",
                    "confirmed_position": agent.position,
                    "distance_to_target": distance
                }

        # Store the preparation
        self.active_preparations[agent_id] = preparation

        return response

    async def execute_prepared_action(self, agent_id: str, request_id: str) -> Dict[str, Any]:
        """
        Phase 2: Execute the action from confirmed position
        """
        if agent_id not in self.active_preparations:
            return {
                "success": False,
                "error": "No active preparation found for agent",
                "request_id": request_id
            }

        preparation = self.active_preparations[agent_id]

        if preparation.request_id != request_id:
            return {
                "success": False,
                "error": "Request ID mismatch",
                "request_id": request_id
            }

        if preparation.phase != ActionPhase.EXECUTION:
            return {
                "success": False,
                "error": f"Action not ready for execution (phase: {preparation.phase})",
                "request_id": request_id
            }

        # Validate position one more time
        agent = self.agent_registry.get_agent(agent_id)
        is_positioned, distance = ActionPositionCalculator.validate_action_position(
            preparation.action_type, preparation.target_x, preparation.target_y,
            agent.position[0], agent.position[1]
        )

        if not is_positioned:
            logger.warning(f"❌ Action execution failed: {agent_id[:8]} position validation failed. "
                         f"Distance: {distance:.2f} (expected ≤1.2)")

            # Clean up failed preparation
            preparation.phase = ActionPhase.FAILED
            del self.active_preparations[agent_id]

            return {
                "success": False,
                "error": f"Position validation failed before execution (distance: {distance:.2f})",
                "request_id": request_id
            }

        # Execute the action through existing action processor
        from shared.actions import ActionRequest, ActionType

        action_request = ActionRequest(
            action_id=f"exec_{request_id}",
            agent_id=agent_id,
            action_type=getattr(ActionType, preparation.action_type.upper()),
            parameters={
                "target_x": preparation.target_x,
                "target_y": preparation.target_y
            }
        )

        # Execute through action processor
        try:
            from server.action_processor import ActionContext
            context = ActionContext(self.action_processor)
            context.world = self.world
            context.agent_registry = self.agent_registry

            response = await self.action_processor.process_action(action_request, context)

            if response.result.name == "SUCCESS":
                self.successful_actions += 1
                preparation.phase = ActionPhase.COMPLETED

                logger.info(f"✅ Action executed successfully: {agent_id[:8]} {preparation.action_type} "
                           f"at distance {distance:.2f}")

                result = {
                    "success": True,
                    "request_id": request_id,
                    "message": "Action executed successfully",
                    "action_result": response.message,
                    "final_distance": distance
                }
            else:
                preparation.phase = ActionPhase.FAILED
                result = {
                    "success": False,
                    "request_id": request_id,
                    "error": f"Action execution failed: {response.message}",
                    "final_distance": distance
                }

            # Clean up completed preparation
            del self.active_preparations[agent_id]
            return result

        except Exception as e:
            logger.error(f"Error executing prepared action: {e}")
            preparation.phase = ActionPhase.FAILED
            del self.active_preparations[agent_id]

            return {
                "success": False,
                "request_id": request_id,
                "error": f"Action execution error: {str(e)}"
            }

    def cleanup_expired_preparations(self):
        """Clean up expired action preparations"""
        current_time = time.time()
        expired_agents = []

        for agent_id, preparation in self.active_preparations.items():
            if current_time - preparation.preparation_start_time > preparation.timeout_seconds:
                expired_agents.append(agent_id)
                logger.warning(f"Action preparation expired for {agent_id[:8]} after {preparation.timeout_seconds}s")

        for agent_id in expired_agents:
            del self.active_preparations[agent_id]

    def get_preparation_stats(self) -> Dict[str, Any]:
        """Get statistics for the two-phase action system"""
        success_rate = self.successful_actions / max(1, self.total_preparations)
        correction_rate = self.position_corrections / max(1, self.total_preparations)

        return {
            "total_preparations": self.total_preparations,
            "successful_actions": self.successful_actions,
            "position_corrections": self.position_corrections,
            "active_preparations": len(self.active_preparations),
            "success_rate": success_rate,
            "position_correction_rate": correction_rate
        }


# Convenience functions for easy integration
_global_action_manager: Optional[TwoPhaseActionManager] = None

def initialize_action_manager(world, agent_registry, action_processor):
    """Initialize the global action manager"""
    global _global_action_manager
    _global_action_manager = TwoPhaseActionManager(world, agent_registry, action_processor)
    return _global_action_manager

def get_action_manager() -> Optional[TwoPhaseActionManager]:
    """Get the global action manager"""
    return _global_action_manager

async def prepare_action(agent_id: str, action_type: str, target_x: float, target_y: float) -> Dict[str, Any]:
    """Convenience function for action preparation"""
    if _global_action_manager:
        return await _global_action_manager.prepare_action(agent_id, action_type, target_x, target_y)
    return {"success": False, "error": "Action manager not initialized"}

async def execute_prepared_action(agent_id: str, request_id: str) -> Dict[str, Any]:
    """Convenience function for action execution"""
    if _global_action_manager:
        return await _global_action_manager.execute_prepared_action(agent_id, request_id)
    return {"success": False, "error": "Action manager not initialized"}