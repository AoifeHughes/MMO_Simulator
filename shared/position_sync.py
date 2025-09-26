"""
Position Synchronization System

This module provides client-server position synchronization to prevent
position jumps and improve action validation consistency.
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """Represents an agent's position state with timing"""
    x: float
    y: float
    timestamp: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    is_predicted: bool = False  # Whether this is a client prediction


class PositionPredictor:
    """Predicts future positions based on current velocity and movement"""

    @staticmethod
    def predict_position(current_x: float, current_y: float,
                        velocity_x: float, velocity_y: float,
                        dt: float) -> Tuple[float, float]:
        """Predict position after time dt"""
        predicted_x = current_x + velocity_x * dt
        predicted_y = current_y + velocity_y * dt
        return predicted_x, predicted_y

    @staticmethod
    def get_action_position(agent_x: float, agent_y: float,
                          target_x: float, target_y: float,
                          max_approach_distance: float = 0.5) -> Tuple[float, float]:
        """
        Calculate optimal position for performing an action.

        This helps clients and servers agree on where the agent should be
        when performing resource actions.
        """
        # Calculate direction to target
        dx = target_x - agent_x
        dy = target_y - agent_y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance <= max_approach_distance:
            # Already close enough, use current position
            return agent_x, agent_y

        # Move towards target but stop at approach distance
        if distance > 0:
            approach_distance = min(distance - 0.1, max_approach_distance)
            normalized_dx = dx / distance
            normalized_dy = dy / distance

            approach_x = agent_x + normalized_dx * approach_distance
            approach_y = agent_y + normalized_dy * approach_distance

            return approach_x, approach_y

        return agent_x, agent_y


class PositionSyncManager:
    """Manages position synchronization between client and server"""

    def __init__(self, max_prediction_time: float = 0.5):
        self.agent_positions: Dict[str, PositionState] = {}
        self.max_prediction_time = max_prediction_time

    def update_agent_position(self, agent_id: str, x: float, y: float,
                            velocity_x: float = 0.0, velocity_y: float = 0.0,
                            is_predicted: bool = False):
        """Update an agent's position state"""
        self.agent_positions[agent_id] = PositionState(
            x=x, y=y, timestamp=time.time(),
            velocity_x=velocity_x, velocity_y=velocity_y,
            is_predicted=is_predicted
        )

    def get_current_position(self, agent_id: str) -> Optional[Tuple[float, float]]:
        """Get current position, with prediction if needed"""
        if agent_id not in self.agent_positions:
            return None

        state = self.agent_positions[agent_id]
        current_time = time.time()
        dt = current_time - state.timestamp

        # If position is recent (< 100ms), use as-is
        if dt < 0.1:
            return state.x, state.y

        # If position is old but we have velocity, predict forward
        if dt < self.max_prediction_time and (state.velocity_x != 0 or state.velocity_y != 0):
            predicted_x, predicted_y = PositionPredictor.predict_position(
                state.x, state.y, state.velocity_x, state.velocity_y, dt
            )
            return predicted_x, predicted_y

        # Otherwise use last known position
        return state.x, state.y

    def validate_action_position(self, agent_id: str, target_x: float, target_y: float,
                                max_distance: float, action_name: str = "action") -> Tuple[bool, str, Optional[Tuple[float, float]]]:
        """
        Validate if an agent can perform an action at the target.

        Returns:
            (is_valid, error_message, suggested_position)
        """
        current_pos = self.get_current_position(agent_id)
        if not current_pos:
            return False, f"Agent {agent_id} position unknown", None

        agent_x, agent_y = current_pos

        # Calculate distance to target
        dx = target_x - agent_x
        dy = target_y - agent_y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance <= max_distance:
            return True, "", (agent_x, agent_y)

        # Try to suggest a valid position
        suggested_pos = PositionPredictor.get_action_position(
            agent_x, agent_y, target_x, target_y, max_distance
        )

        # Check if suggested position is valid
        suggested_distance = ((target_x - suggested_pos[0]) ** 2 + (target_y - suggested_pos[1]) ** 2) ** 0.5

        if suggested_distance <= max_distance:
            return False, f"{action_name} distance {distance:.2f} > {max_distance:.2f}, can move to better position", suggested_pos
        else:
            return False, f"{action_name} distance {distance:.2f} > {max_distance:.2f}, target unreachable", None

    def smooth_position_correction(self, agent_id: str, server_x: float, server_y: float,
                                  max_correction: float = 2.0) -> Tuple[float, float]:
        """
        Apply smooth position correction to prevent jarring jumps.

        Returns the corrected position that should be used.
        """
        current_pos = self.get_current_position(agent_id)
        if not current_pos:
            return server_x, server_y

        client_x, client_y = current_pos

        # Calculate correction distance
        dx = server_x - client_x
        dy = server_y - client_y
        correction_distance = (dx * dx + dy * dy) ** 0.5

        # If correction is small, apply it directly
        if correction_distance <= 0.5:
            return server_x, server_y

        # If correction is large but within max, apply smoothly
        if correction_distance <= max_correction:
            # Apply 70% of the correction immediately, rest over time
            smooth_factor = 0.7
            corrected_x = client_x + dx * smooth_factor
            corrected_y = client_y + dy * smooth_factor

            logger.info(f"Smooth position correction for {agent_id[:8]}: "
                       f"{correction_distance:.2f} units -> applied {smooth_factor*100:.0f}%")

            return corrected_x, corrected_y

        # If correction is too large, it might be a teleport or major desync
        logger.warning(f"Large position correction for {agent_id[:8]}: "
                      f"{correction_distance:.2f} units (may cause visible jump)")

        return server_x, server_y


# Global position sync manager
global_position_sync = PositionSyncManager()


def get_position_sync() -> PositionSyncManager:
    """Get the global position sync manager"""
    return global_position_sync


def update_agent_position(agent_id: str, x: float, y: float,
                         velocity_x: float = 0.0, velocity_y: float = 0.0,
                         is_predicted: bool = False):
    """Convenience function to update agent position"""
    global_position_sync.update_agent_position(agent_id, x, y, velocity_x, velocity_y, is_predicted)


def get_current_position(agent_id: str) -> Optional[Tuple[float, float]]:
    """Convenience function to get current position"""
    return global_position_sync.get_current_position(agent_id)


def validate_action_position(agent_id: str, target_x: float, target_y: float,
                           max_distance: float, action_name: str = "action") -> Tuple[bool, str, Optional[Tuple[float, float]]]:
    """Convenience function to validate action position"""
    return global_position_sync.validate_action_position(agent_id, target_x, target_y, max_distance, action_name)


def smooth_position_correction(agent_id: str, server_x: float, server_y: float,
                              max_correction: float = 2.0) -> Tuple[float, float]:
    """Convenience function for smooth position correction"""
    return global_position_sync.smooth_position_correction(agent_id, server_x, server_y, max_correction)