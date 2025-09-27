"""
Client Position Reconciliation System

This module implements smooth position reconciliation between client predictions
and server authority to eliminate position jumps and sync issues.

Key features:
- Detects server position corrections
- Smoothly interpolates client position to match server authority
- Maintains responsive movement while respecting server corrections
- Reduces visual position jumps and sync conflicts
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PositionState:
    """Tracks position state for reconciliation"""

    # Current display position (what we show)
    display_x: float = 0.0
    display_y: float = 0.0
    display_rotation: float = 0.0

    # Last server authoritative position
    server_x: float = 0.0
    server_y: float = 0.0
    server_rotation: float = 0.0
    server_timestamp: float = 0.0

    # Client predicted position
    predicted_x: float = 0.0
    predicted_y: float = 0.0
    predicted_rotation: float = 0.0

    # Reconciliation state
    is_reconciling: bool = False
    reconcile_start_time: float = 0.0
    reconcile_start_pos: Tuple[float, float] = (0.0, 0.0)
    reconcile_target_pos: Tuple[float, float] = (0.0, 0.0)

    # Movement state
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    last_movement_time: float = 0.0


class PositionReconciler:
    """Handles smooth position reconciliation between client and server"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.state = PositionState()

        # Reconciliation parameters
        self.correction_threshold = 1.0  # Distance that triggers reconciliation
        self.reconciliation_speed = 8.0  # How fast to reconcile (units/second)
        self.max_reconciliation_time = 0.5  # Max time to spend reconciling
        self.prediction_tolerance = 0.5  # Acceptable prediction error

        # Statistics
        self.stats = {
            "corrections_applied": 0,
            "reconciliations_started": 0,
            "reconciliations_completed": 0,
            "position_jumps_prevented": 0,
        }

    def set_server_position(
        self, x: float, y: float, rotation: float, timestamp: float
    ):
        """Update with authoritative server position"""
        old_server_x, old_server_y = self.state.server_x, self.state.server_y

        # Update server position
        self.state.server_x = x
        self.state.server_y = y
        self.state.server_rotation = rotation
        self.state.server_timestamp = timestamp

        # Check if this is a significant correction
        if old_server_x != 0.0 or old_server_y != 0.0:  # Not first update
            correction_distance = (
                (x - self.state.display_x) ** 2 + (y - self.state.display_y) ** 2
            ) ** 0.5

            if correction_distance > self.correction_threshold:
                logger.info(
                    f"🔄 Position correction detected for {self.agent_id[:8]}: "
                    f"display=({self.state.display_x:.2f}, {self.state.display_y:.2f}) "
                    f"server=({x:.2f}, {y:.2f}) distance={correction_distance:.2f}"
                )

                self._start_reconciliation(x, y, rotation)
                self.stats["corrections_applied"] += 1
                return True
        else:
            # First position update - set immediately
            self.state.display_x = x
            self.state.display_y = y
            self.state.display_rotation = rotation
            self.state.predicted_x = x
            self.state.predicted_y = y
            self.state.predicted_rotation = rotation

        return False

    def _start_reconciliation(
        self, target_x: float, target_y: float, target_rotation: float
    ):
        """Start smooth reconciliation to server position"""
        current_time = time.time()

        self.state.is_reconciling = True
        self.state.reconcile_start_time = current_time
        self.state.reconcile_start_pos = (self.state.display_x, self.state.display_y)
        self.state.reconcile_target_pos = (target_x, target_y)

        self.stats["reconciliations_started"] += 1

        logger.debug(
            f"🔄 Started position reconciliation for {self.agent_id[:8]}: "
            f"from ({self.state.display_x:.2f}, {self.state.display_y:.2f}) "
            f"to ({target_x:.2f}, {target_y:.2f})"
        )

    def update_prediction(
        self,
        predicted_x: float,
        predicted_y: float,
        predicted_rotation: float,
        velocity_x: float = 0.0,
        velocity_y: float = 0.0,
    ):
        """Update client-side prediction"""
        self.state.predicted_x = predicted_x
        self.state.predicted_y = predicted_y
        self.state.predicted_rotation = predicted_rotation
        self.state.velocity_x = velocity_x
        self.state.velocity_y = velocity_y
        self.state.last_movement_time = time.time()

    def update(self, delta_time: float) -> Tuple[float, float, float]:
        """
        Update reconciliation and return current display position

        Returns:
            (display_x, display_y, display_rotation) - the position to actually display
        """
        current_time = time.time()

        if self.state.is_reconciling:
            self._update_reconciliation(current_time, delta_time)
        else:
            # Not reconciling - use predicted position
            self.state.display_x = self.state.predicted_x
            self.state.display_y = self.state.predicted_y
            self.state.display_rotation = self.state.predicted_rotation

        return (self.state.display_x, self.state.display_y, self.state.display_rotation)

    def _update_reconciliation(self, current_time: float, delta_time: float):
        """Update smooth reconciliation interpolation"""
        reconcile_elapsed = current_time - self.state.reconcile_start_time

        # Check if reconciliation should complete
        if reconcile_elapsed >= self.max_reconciliation_time:
            self._complete_reconciliation()
            return

        # Calculate interpolation progress
        start_x, start_y = self.state.reconcile_start_pos
        target_x, target_y = self.state.reconcile_target_pos

        distance_to_target = (
            (target_x - self.state.display_x) ** 2
            + (target_y - self.state.display_y) ** 2
        ) ** 0.5

        # Complete if we're close enough
        if distance_to_target < 0.1:
            self._complete_reconciliation()
            return

        # Smooth interpolation toward target
        move_distance = self.reconciliation_speed * delta_time

        if distance_to_target > 0:
            # Move toward target
            move_ratio = min(1.0, move_distance / distance_to_target)

            self.state.display_x += (target_x - self.state.display_x) * move_ratio
            self.state.display_y += (target_y - self.state.display_y) * move_ratio

            # Smoothly interpolate rotation
            rotation_diff = target_y - self.state.display_rotation
            # Handle rotation wrapping
            if rotation_diff > 180:
                rotation_diff -= 360
            elif rotation_diff < -180:
                rotation_diff += 360

            self.state.display_rotation += rotation_diff * move_ratio

    def _complete_reconciliation(self):
        """Complete reconciliation and return to prediction mode"""
        target_x, target_y = self.state.reconcile_target_pos

        self.state.display_x = target_x
        self.state.display_y = target_y
        self.state.display_rotation = self.state.server_rotation

        # Update prediction to match server position
        self.state.predicted_x = target_x
        self.state.predicted_y = target_y
        self.state.predicted_rotation = self.state.server_rotation

        self.state.is_reconciling = False
        self.stats["reconciliations_completed"] += 1

        logger.debug(
            f"✅ Completed position reconciliation for {self.agent_id[:8]} "
            f"at ({target_x:.2f}, {target_y:.2f})"
        )

    def validate_movement(
        self, intended_x: float, intended_y: float
    ) -> Tuple[bool, str]:
        """
        Validate if a movement is likely to be accepted by server

        Returns:
            (is_valid, reason) - whether movement should be sent
        """
        # Check if we're too far from server position
        if self.state.server_timestamp > 0:  # Have server data
            server_distance = (
                (intended_x - self.state.server_x) ** 2
                + (intended_y - self.state.server_y) ** 2
            ) ** 0.5

            # Allow some prediction error but flag large discrepancies
            if server_distance > 5.0:  # More than 5 units from server position
                return (
                    False,
                    f"Too far from server position (distance: {server_distance:.2f})",
                )

        return True, "Movement valid"

    def get_interpolated_position(self, server_timestamp: float) -> Tuple[float, float]:
        """
        Get interpolated position based on server timestamp
        Used for action validation
        """
        if self.state.server_timestamp == 0:
            return self.state.display_x, self.state.display_y

        # Calculate time difference
        time_diff = server_timestamp - self.state.server_timestamp

        # If time difference is small, use server position
        if abs(time_diff) < 0.1:  # 100ms tolerance
            return self.state.server_x, self.state.server_y

        # Otherwise interpolate based on velocity
        if time_diff > 0:  # Future prediction
            predicted_x = self.state.server_x + self.state.velocity_x * time_diff
            predicted_y = self.state.server_y + self.state.velocity_y * time_diff
            return predicted_x, predicted_y
        else:  # Past position
            return self.state.server_x, self.state.server_y

    def is_position_stable(self) -> bool:
        """Check if position is stable (not reconciling)"""
        return not self.state.is_reconciling

    def get_position_error(self) -> float:
        """Get current position error from server"""
        if self.state.server_timestamp == 0:
            return 0.0

        return (
            (self.state.display_x - self.state.server_x) ** 2
            + (self.state.display_y - self.state.server_y) ** 2
        ) ** 0.5

    def get_stats(self) -> dict:
        """Get reconciliation statistics"""
        return {
            **self.stats,
            "is_reconciling": self.state.is_reconciling,
            "position_error": self.get_position_error(),
            "last_server_update": self.state.server_timestamp,
        }
