"""
Movement Management System for Behavior Trees

This system provides stable, smooth movement control to prevent the
jittery behavior caused by frequent direction changes and micro-adjustments.
"""

import logging
import math
import time
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class MovementMode(Enum):
    """Different movement modes for different behaviors"""

    DIRECT = "direct"  # Direct movement to target
    CHASE = "chase"  # Chase with prediction
    WANDER = "wander"  # Random wandering
    PATROL = "patrol"  # Patrol between waypoints
    FLEE = "flee"  # Fleeing from threat
    PATHFINDING = "pathfinding"  # Following calculated path


class MovementManager:
    """
    Unified movement management system for smooth agent movement.

    Prevents jittery behavior by:
    - Reducing update frequency
    - Smoothing direction changes
    - Adding movement commitment
    - Implementing arrival prediction
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

        # Movement state
        self.current_mode = MovementMode.DIRECT
        self.target_position: Optional[Tuple[float, float]] = None
        self.last_update_time = 0.0
        self.movement_start_time = 0.0

        # Smoothing parameters
        self.base_update_interval = 0.2  # 200ms between updates
        self.chase_update_interval = 0.15  # Faster for combat
        self.wander_update_interval = 0.3  # Slower for wandering
        self.pathfinding_update_interval = 0.1  # Faster for pathfinding

        # Movement commitment (minimum time to maintain direction)
        self.commitment_duration = 0.5  # 500ms minimum
        self.pathfinding_commitment_duration = 0.2  # Shorter for pathfinding
        self.last_direction_change = 0.0

        # Smoothing factors
        self.direction_smoothing = 0.3  # How much to smooth direction changes
        self.pathfinding_smoothing = 0.1  # Less smoothing for pathfinding
        self.last_velocity = (0.0, 0.0)
        self.target_velocity = (0.0, 0.0)

        # Arrival prediction
        self.arrival_threshold = 0.5  # Stop this distance from target
        self.prediction_time = 0.5  # Look ahead this many seconds

        logger.debug(f"MovementManager initialized for agent {agent_id[:8]}")

    def update_movement(
        self,
        agent,
        target_pos: Optional[Tuple[float, float]] = None,
        mode: MovementMode = MovementMode.DIRECT,
        speed_multiplier: float = 1.0,
        arrival_threshold: Optional[float] = None,
    ) -> bool:
        """
        Update agent movement with stability controls.

        Args:
            agent: The agent to move
            target_pos: Target position (x, y)
            mode: Movement mode
            speed_multiplier: Speed adjustment
            arrival_threshold: Custom arrival threshold

        Returns:
            True if agent has arrived at target, False otherwise
        """
        current_time = time.time()

        # Set target and mode
        if target_pos != self.target_position or mode != self.current_mode:
            self.target_position = target_pos
            self.current_mode = mode
            self.movement_start_time = current_time

        if not self.target_position:
            # No target, stop movement
            agent.velocity_x = 0
            agent.velocity_y = 0
            return True

        # Calculate distance to target
        dx = self.target_position[0] - agent.x
        dy = self.target_position[1] - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        # Check if we've arrived
        threshold = arrival_threshold if arrival_threshold else self.arrival_threshold
        if distance <= threshold:
            agent.velocity_x = 0
            agent.velocity_y = 0
            return True

        # Get update interval based on mode
        update_interval = self._get_update_interval(mode)

        # Only update movement at specified intervals
        if current_time - self.last_update_time < update_interval:
            return False

        # Calculate new movement direction
        new_velocity = self._calculate_target_velocity(
            agent, dx, dy, distance, speed_multiplier
        )

        # Apply movement smoothing
        smoothed_velocity = self._apply_movement_smoothing(new_velocity, current_time)

        # Update agent velocity
        agent.velocity_x = smoothed_velocity[0]
        agent.velocity_y = smoothed_velocity[1]

        # Update rotation to face movement direction
        if smoothed_velocity[0] != 0 or smoothed_velocity[1] != 0:
            agent.rotation = math.degrees(
                math.atan2(smoothed_velocity[1], smoothed_velocity[0])
            )

        self.last_update_time = current_time
        self.target_velocity = new_velocity

        logger.debug(
            f"Agent {self.agent_id[:8]} movement updated - mode: {mode.value}, dist: {distance:.1f}"
        )

        return False

    def stop_movement(self, agent):
        """Stop all movement immediately"""
        agent.velocity_x = 0
        agent.velocity_y = 0
        self.target_position = None
        self.last_velocity = (0.0, 0.0)
        self.target_velocity = (0.0, 0.0)

        logger.debug(f"Agent {self.agent_id[:8]} movement stopped")

    def set_movement_parameters(
        self,
        base_update_interval: Optional[float] = None,
        commitment_duration: Optional[float] = None,
        direction_smoothing: Optional[float] = None,
        arrival_threshold: Optional[float] = None,
    ):
        """Configure movement parameters"""
        if base_update_interval is not None:
            self.base_update_interval = base_update_interval
        if commitment_duration is not None:
            self.commitment_duration = commitment_duration
        if direction_smoothing is not None:
            self.direction_smoothing = direction_smoothing
        if arrival_threshold is not None:
            self.arrival_threshold = arrival_threshold

    def is_moving_toward_target(self) -> bool:
        """Check if agent is currently moving toward a target"""
        return self.target_position is not None and (
            self.target_velocity[0] != 0 or self.target_velocity[1] != 0
        )

    def get_time_since_movement_start(self) -> float:
        """Get time since current movement started"""
        return time.time() - self.movement_start_time

    def _get_update_interval(self, mode: MovementMode) -> float:
        """Get update interval based on movement mode"""
        if mode == MovementMode.CHASE:
            return self.chase_update_interval
        elif mode == MovementMode.WANDER:
            return self.wander_update_interval
        elif mode == MovementMode.PATHFINDING:
            return self.pathfinding_update_interval
        else:
            return self.base_update_interval

    def _calculate_target_velocity(
        self, agent, dx: float, dy: float, distance: float, speed_multiplier: float
    ) -> Tuple[float, float]:
        """Calculate desired velocity toward target"""
        if distance == 0:
            return (0.0, 0.0)

        # Normalize direction
        dir_x = dx / distance
        dir_y = dy / distance

        # Calculate speed with deceleration near target
        base_speed = agent.speed * speed_multiplier

        # Apply deceleration when close to target
        if distance < 3.0:
            decel_factor = max(0.3, distance / 3.0)  # Minimum 30% speed
            base_speed *= decel_factor

        return (dir_x * base_speed, dir_y * base_speed)

    def _apply_movement_smoothing(
        self, target_velocity: Tuple[float, float], current_time: float
    ) -> Tuple[float, float]:
        """Apply smoothing to reduce jittery movement"""
        # Get commitment duration and smoothing factor based on mode
        commitment_duration = (
            self.pathfinding_commitment_duration
            if self.current_mode == MovementMode.PATHFINDING
            else self.commitment_duration
        )
        smoothing_factor = (
            self.pathfinding_smoothing
            if self.current_mode == MovementMode.PATHFINDING
            else self.direction_smoothing
        )

        # Check movement commitment
        if (
            current_time - self.last_direction_change < commitment_duration
            and self.last_velocity[0] != 0
            or self.last_velocity[1] != 0
        ):
            # Still in commitment period, maintain current direction
            return self.last_velocity

        # Calculate direction change
        old_dir = math.atan2(self.last_velocity[1], self.last_velocity[0])
        new_dir = math.atan2(target_velocity[1], target_velocity[0])
        dir_change = abs(old_dir - new_dir)

        # Normalize direction change to [0, pi]
        if dir_change > math.pi:
            dir_change = 2 * math.pi - dir_change

        # For pathfinding mode, allow quicker direction changes
        direction_threshold = (
            math.pi / 6
            if self.current_mode == MovementMode.PATHFINDING
            else math.pi / 4
        )  # 30 vs 45 degrees

        # If direction change is significant, apply smoothing
        if dir_change > direction_threshold:
            # Smooth the transition
            smoothed_x = (
                self.last_velocity[0] * (1 - smoothing_factor)
                + target_velocity[0] * smoothing_factor
            )
            smoothed_y = (
                self.last_velocity[1] * (1 - smoothing_factor)
                + target_velocity[1] * smoothing_factor
            )

            self.last_direction_change = current_time
            result = (smoothed_x, smoothed_y)
        else:
            # Small change, use target velocity directly
            result = target_velocity

        self.last_velocity = result
        return result

    def predict_arrival_time(self, agent) -> Optional[float]:
        """Predict when agent will arrive at target"""
        if not self.target_position:
            return None

        dx = self.target_position[0] - agent.x
        dy = self.target_position[1] - agent.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance == 0:
            return 0.0

        # Calculate current speed
        current_speed = math.sqrt(agent.velocity_x**2 + agent.velocity_y**2)
        if current_speed == 0:
            current_speed = agent.speed

        return distance / current_speed

    def get_debug_info(self) -> dict:
        """Get debug information about movement state"""
        return {
            "mode": self.current_mode.value,
            "has_target": self.target_position is not None,
            "target_position": self.target_position,
            "movement_age": self.get_time_since_movement_start(),
            "last_velocity": self.last_velocity,
            "target_velocity": self.target_velocity,
        }
