"""
Two-Phase Action System (OOP Base Classes)

This provides a base class system for reliable action execution that eliminates
distance validation errors by ensuring proper positioning before action execution.

Base classes:
- TwoPhaseActionNode: Base for all actions requiring positioning
- ResourceActionNode: Base for resource-gathering actions (fishing, harvesting)

How it works:
1. Phase 1: Position Preparation - Agent moves to optimal position
2. Phase 2: Action Execution - Agent performs action from validated position

This eliminates the common "distance to target: 4.47 > 1.5 limit" errors.
"""

import logging
import math
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from shared.action_constants import DISTANCES, THRESHOLDS
from shared.position_authority import get_server_position_for_action
from world.tiles import TileType

from .base import ActionNode, NodeStatus

try:
    from debug_tracker import track_agent_position, track_resource_event
except ImportError:

    def track_resource_event(*args, **kwargs):
        pass

    def track_agent_position(*args, **kwargs):
        pass


logger = logging.getLogger(__name__)


class ActionPhase(Enum):
    """Phases of two-phase action execution"""

    PREPARATION = "preparation"  # Moving to optimal position
    READY = "ready"  # In position, ready to act
    EXECUTING = "executing"  # Performing the action
    COMPLETED = "completed"  # Action finished


class TwoPhaseActionNode(ActionNode, ABC):
    """
    Base class for all actions that require precise positioning.

    Subclasses only need to implement:
    - find_action_target()
    - calculate_optimal_position()
    - execute_action()
    - get_action_name()
    """

    def __init__(
        self,
        name: str,
        required_distance: float = 1.0,
        positioning_tolerance: float = None,
    ):
        super().__init__(name)
        self.required_distance = required_distance
        self.positioning_tolerance = (
            positioning_tolerance or THRESHOLDS.POSITIONING_TOLERANCE
        )

        # Use centralized validation buffer
        self.validation_buffer = THRESHOLDS.VALIDATION_BUFFER

        # Phase tracking
        self.phase = ActionPhase.PREPARATION
        self.target_position: Optional[Tuple[float, float]] = None
        self.optimal_agent_position: Optional[Tuple[float, float]] = None
        self.action_start_time = 0.0
        self.phase_start_time = 0.0

        # Timeouts
        self.positioning_timeout = 10.0  # Max time to get into position
        self.action_timeout = 8.0  # Max time for action execution

    def start_action(self, agent) -> bool:
        """Initialize the two-phase action sequence"""
        logger.info(
            f"🎯 Starting two-phase {self.get_action_name()}: Agent {agent.id[:8]}"
        )

        # Phase 1: Find target and calculate positioning
        target_pos = self.find_action_target(agent)
        if not target_pos:
            logger.warning(
                f"{self.get_action_name()}: Agent {agent.id[:8]} - no valid target found"
            )
            return False

        self.target_position = target_pos

        # Calculate where agent should stand to perform action
        self.optimal_agent_position = self.calculate_optimal_position(agent, target_pos)
        if not self.optimal_agent_position:
            logger.warning(
                f"{self.get_action_name()}: Agent {agent.id[:8]} - no valid position found"
            )
            return False

        # Check if already in optimal position using server position for consistency
        server_pos = get_server_position_for_action(agent.id)
        if server_pos:
            agent_pos = server_pos
        else:
            agent_pos = (agent.x, agent.y)
        distance_to_optimal = self._distance(agent_pos, self.optimal_agent_position)

        if distance_to_optimal <= self.positioning_tolerance:
            # Already positioned - check if can perform action
            if self._validate_action_position(agent):
                logger.info(
                    f"✅ {self.get_action_name()}: Agent {agent.id[:8]} already optimally positioned"
                )
                self.phase = ActionPhase.READY
                self.phase_start_time = time.time()
                return True

        # Need to move to optimal position
        self.phase = ActionPhase.PREPARATION
        self.phase_start_time = time.time()

        logger.info(
            f"🚶 {self.get_action_name()}: Agent {agent.id[:8]} moving to optimal position "
            f"({self.optimal_agent_position[0]:.2f}, {self.optimal_agent_position[1]:.2f})"
        )

        # Start movement to optimal position
        self._start_positioning_movement(agent)

        # Track positioning attempt
        track_agent_position(
            agent.id, agent.x, agent.y, f"start_{self.get_action_name()}_positioning"
        )

        return True

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Update the two-phase action based on current phase"""
        current_time = time.time()

        if self.phase == ActionPhase.PREPARATION:
            return self._update_positioning_phase(agent, current_time)
        elif self.phase == ActionPhase.READY:
            return self._update_ready_phase(agent, current_time)
        elif self.phase == ActionPhase.EXECUTING:
            return self._update_execution_phase(agent, current_time)
        elif self.phase == ActionPhase.COMPLETED:
            return NodeStatus.SUCCESS

        return NodeStatus.FAILURE

    def _update_positioning_phase(self, agent, current_time: float) -> NodeStatus:
        """Update positioning phase - moving to optimal position"""

        # Check positioning timeout
        if current_time - self.phase_start_time > self.positioning_timeout:
            logger.warning(
                f"⏰ {self.get_action_name()}: Agent {agent.id[:8]} positioning timeout"
            )
            return NodeStatus.FAILURE

        # Check if reached optimal position using server position for consistency
        server_pos = get_server_position_for_action(agent.id)
        if server_pos:
            agent_pos = server_pos
        else:
            agent_pos = (agent.x, agent.y)
        distance_to_optimal = self._distance(agent_pos, self.optimal_agent_position)

        if distance_to_optimal <= self.positioning_tolerance:
            # Reached optimal position - validate action capability
            logger.info(
                f"🎯 {self.get_action_name()}: Agent {agent.id[:8]} reached optimal position "
                f"(distance to optimal: {distance_to_optimal:.3f})"
            )

            if self._validate_action_position(agent):
                logger.info(
                    f"✅ {self.get_action_name()}: Agent {agent.id[:8]} positioned successfully "
                    f"(distance to optimal: {distance_to_optimal:.3f})"
                )

                # Stop movement
                agent.stop_movement()

                # Transition to ready phase
                self.phase = ActionPhase.READY
                self.phase_start_time = current_time

                # Track successful positioning
                track_agent_position(
                    agent.id, agent.x, agent.y, f"{self.get_action_name()}_positioned"
                )

                return NodeStatus.RUNNING
            else:
                logger.warning(
                    f"❌ {self.get_action_name()}: Agent {agent.id[:8]} at optimal position but action validation failed"
                )
                logger.info(
                    f"   Optimal position was ({self.optimal_agent_position[0]:.3f}, {self.optimal_agent_position[1]:.3f})"
                )
                logger.info(f"   Agent actually at ({agent.x:.3f}, {agent.y:.3f})")
                logger.info(
                    f"   Target is at ({self.target_position[0]:.3f}, {self.target_position[1]:.3f})"
                )
                return NodeStatus.FAILURE

        # Still moving to position
        return NodeStatus.RUNNING

    def _update_ready_phase(self, agent, current_time: float) -> NodeStatus:
        """Update ready phase - about to execute action"""

        # Validate position one more time before execution
        if not self._validate_action_position(agent):
            logger.warning(
                f"❌ {self.get_action_name()}: Agent {agent.id[:8]} lost valid position"
            )
            return NodeStatus.FAILURE

        # Execute the action
        logger.info(
            f"🎬 {self.get_action_name()}: Agent {agent.id[:8]} executing action"
        )

        success = self.execute_action(agent, self.target_position)
        if not success:
            logger.warning(
                f"❌ {self.get_action_name()}: Agent {agent.id[:8]} action execution failed"
            )
            return NodeStatus.FAILURE

        # Transition to execution phase
        self.phase = ActionPhase.EXECUTING
        self.action_start_time = current_time
        self.phase_start_time = current_time

        # Track action execution
        track_resource_event(
            agent.id,
            f"{self.get_action_name()}_execution",
            self.get_resource_type(),
            self.target_position,
            (agent.x, agent.y),
            self.name,
        )

        return NodeStatus.RUNNING

    def _update_execution_phase(self, agent, current_time: float) -> NodeStatus:
        """Update execution phase - action in progress"""

        # Keep agent stationary during action
        agent.stop_movement()

        # Check action timeout
        if current_time - self.action_start_time > self.action_timeout:
            logger.info(
                f"✅ {self.get_action_name()}: Agent {agent.id[:8]} action completed (timeout)"
            )
            self.phase = ActionPhase.COMPLETED
            return NodeStatus.SUCCESS

        # Check if action should complete early (subclass can override)
        if self.should_complete_action(agent, current_time - self.action_start_time):
            logger.info(
                f"✅ {self.get_action_name()}: Agent {agent.id[:8]} action completed"
            )
            self.phase = ActionPhase.COMPLETED
            return NodeStatus.SUCCESS

        return NodeStatus.RUNNING

    def stop_action(self, agent):
        """Stop the action and clean up"""
        agent.stop_movement()
        self.phase = ActionPhase.PREPARATION
        self.target_position = None
        self.optimal_agent_position = None

    def reset(self):
        """Reset action state"""
        super().reset()
        self.phase = ActionPhase.PREPARATION
        self.target_position = None
        self.optimal_agent_position = None
        self.action_start_time = 0.0
        self.phase_start_time = 0.0

    # Abstract methods that subclasses must implement

    @abstractmethod
    def find_action_target(self, agent) -> Optional[Tuple[float, float]]:
        """Find the target for this action (e.g., water tile, wood tile)"""
        pass

    @abstractmethod
    def calculate_optimal_position(
        self, agent, target_pos: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """Calculate where the agent should stand to perform the action"""
        pass

    @abstractmethod
    def execute_action(self, agent, target_pos: Tuple[float, float]) -> bool:
        """Execute the actual action (send request to server)"""
        pass

    @abstractmethod
    def get_action_name(self) -> str:
        """Get the display name of this action"""
        pass

    @abstractmethod
    def get_resource_type(self) -> str:
        """Get the resource type for debugging (e.g., 'water', 'wood')"""
        pass

    # Helper methods

    def _start_positioning_movement(self, agent):
        """Start movement toward optimal position"""
        if hasattr(agent, "find_path_to"):
            # Try pathfinding first
            if agent.find_path_to(
                self.optimal_agent_position[0], self.optimal_agent_position[1]
            ):
                return

        # Fallback to direct movement
        dx = self.optimal_agent_position[0] - agent.x
        dy = self.optimal_agent_position[1] - agent.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance > 0:
            agent.velocity_x = (dx / distance) * agent.speed
            agent.velocity_y = (dy / distance) * agent.speed
            agent.rotation = math.degrees(math.atan2(dy, dx))

    def _validate_action_position(self, agent) -> bool:
        """Check if agent is properly positioned for action using SERVER AUTHORITY"""
        if not self.target_position:
            logger.warning(
                f"❌ {self.get_action_name()}: Agent {agent.id[:8]} validation failed - no target position"
            )
            return False

        # Get server position for better accuracy
        server_pos = get_server_position_for_action(agent.id)
        if server_pos:
            # Use server-authoritative position for validation
            agent_pos = server_pos
            logger.info(
                f"✅ {self.get_action_name()}: Agent {agent.id[:8]} CLIENT validation success - using server position ({server_pos[0]:.3f}, {server_pos[1]:.3f})"
            )
        else:
            # Fallback to client position with warning
            agent_pos = (agent.x, agent.y)
            logger.warning(
                f"⚠️ {self.get_action_name()}: Server query failed, using client validation"
            )

        client_distance = self._distance(agent_pos, self.target_position)
        is_valid = client_distance <= (self.required_distance + 0.1)  # Add small buffer

        logger.info(
            f"✅ {self.get_action_name()}: Agent {agent.id[:8]} CLIENT validation {'success' if is_valid else 'failed'} - "
            f"client distance {client_distance:.3f} {'≤' if is_valid else '>'} required {self.required_distance:.3f}"
        )

        return is_valid

    def _query_server_for_validation(self, agent) -> Optional[Dict[str, Any]]:
        """Query server for authoritative action validation"""
        if not hasattr(agent, "action_manager") or not agent.action_manager:
            return None

        try:
            # Create validation query
            import uuid

            from shared.server_queries import create_action_validation_query

            query = create_action_validation_query(
                query_id=str(uuid.uuid4())[:8],
                agent_id=agent.id,
                action_name=self.get_action_name(),
                target_x=self.target_position[0],
                target_y=self.target_position[1],
            )

            # TODO: Implement server query mechanism
            # For now, return None to use fallback
            return None

        except Exception as e:
            logger.error(f"Server query error: {e}")
            return None

    def _validate_action_position_client_side(self, agent) -> bool:
        """Fallback client-side validation (original implementation)"""
        distance = self._distance((agent.x, agent.y), self.target_position)
        # Add small buffer to handle floating point precision issues
        is_valid = distance <= (self.required_distance + self.validation_buffer)

        # DEBUG: Log client's view of agent position
        logger.debug(
            f"🔍 CLIENT position for {agent.id[:8]}: ({agent.x:.3f}, {agent.y:.3f})"
        )
        logger.debug(
            f"🔍 CLIENT calculating distance to target ({self.target_position[0]:.3f}, {self.target_position[1]:.3f}): {distance:.3f}"
        )

        if not is_valid:
            logger.warning(
                f"❌ {self.get_action_name()}: Agent {agent.id[:8]} CLIENT validation failed - "
                f"client distance {distance:.3f} > required {self.required_distance:.3f}"
            )
            logger.info(
                f"   Agent at ({agent.x:.3f}, {agent.y:.3f}), target at ({self.target_position[0]:.3f}, {self.target_position[1]:.3f})"
            )
        else:
            logger.info(
                f"✅ {self.get_action_name()}: Agent {agent.id[:8]} CLIENT validation success - "
                f"client distance {distance:.3f} ≤ required {self.required_distance:.3f}"
            )

        return is_valid

    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate distance between two positions"""
        dx = pos2[0] - pos1[0]
        dy = pos2[1] - pos1[1]
        return (dx * dx + dy * dy) ** 0.5

    def should_complete_action(self, agent, elapsed_time: float) -> bool:
        """Override this to provide custom completion logic"""
        return False  # Default: wait for timeout


class ResourceActionNode(TwoPhaseActionNode, ABC):
    """
    Base class for resource gathering actions (fishing, wood harvesting, mining, etc.)

    Provides common functionality for finding and approaching resources.
    """

    def __init__(
        self,
        name: str,
        resource_tile_type,
        max_search_distance: float = 5.0,
        required_distance: float = None,
    ):
        # Use centralized distance constants if not specified
        if required_distance is None:
            if resource_tile_type == TileType.WATER:
                required_distance = DISTANCES.FISHING_RANGE
            elif resource_tile_type == TileType.WOOD:
                required_distance = DISTANCES.WOOD_HARVESTING_RANGE
            else:
                required_distance = DISTANCES.MINING_RANGE

        super().__init__(name, required_distance=required_distance)
        self.resource_tile_type = resource_tile_type
        self.max_search_distance = max_search_distance

    def find_action_target(self, agent) -> Optional[Tuple[float, float]]:
        """Find the nearest resource tile of the specified type"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        # Search for nearest resource tile
        nearest_resource = None
        nearest_distance = float("inf")

        agent_x, agent_y = int(agent.x), int(agent.y)
        search_radius = int(self.max_search_distance)

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = agent_x + dx
                check_y = agent_y + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == self.resource_tile_type:
                        # Calculate real distance to tile center
                        tile_center_x = check_x + 0.5
                        tile_center_y = check_y + 0.5
                        distance = self._distance(
                            (agent.x, agent.y), (tile_center_x, tile_center_y)
                        )

                        if distance < nearest_distance:
                            nearest_distance = distance
                            nearest_resource = (tile_center_x, tile_center_y)

        if nearest_resource:
            logger.info(
                f"🎯 {self.get_action_name()}: Agent {agent.id[:8]} found target at "
                f"({nearest_resource[0]:.1f}, {nearest_resource[1]:.1f}) distance {nearest_distance:.2f}"
            )

            # Track resource discovery
            track_resource_event(
                agent.id,
                "discovered",
                self.get_resource_type(),
                (int(nearest_resource[0]), int(nearest_resource[1])),
                (agent.x, agent.y),
                self.name,
            )

        return nearest_resource

    def calculate_optimal_position(
        self, agent, target_pos: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """Calculate optimal position for resource gathering"""
        target_x, target_y = target_pos
        agent_x, agent_y = agent.x, agent.y

        # Calculate direction from target to agent
        dx = agent_x - target_x
        dy = agent_y - target_y
        current_distance = (dx * dx + dy * dy) ** 0.5

        if current_distance < 0.1:
            # Agent is on top of target - default to east side
            return (target_x + self.required_distance, target_y)

        # Position at slightly less than required distance to ensure validation passes
        # This accounts for movement precision and floating point errors
        safe_distance = self.required_distance - 0.02  # 2cm safety margin

        normalized_dx = dx / current_distance
        normalized_dy = dy / current_distance

        optimal_x = target_x + normalized_dx * safe_distance
        optimal_y = target_y + normalized_dy * safe_distance

        # Check if this position is valid (not in water/walls for land-based actions)
        if self._is_position_valid(agent, optimal_x, optimal_y):
            return (optimal_x, optimal_y)

        # Try alternative positions around the target
        for angle_offset in [30, -30, 60, -60, 90, -90]:
            angle = (
                math.degrees(math.atan2(normalized_dy, normalized_dx)) + angle_offset
            )
            rad = math.radians(angle)

            alt_x = target_x + math.cos(rad) * self.required_distance
            alt_y = target_y + math.sin(rad) * self.required_distance

            if self._is_position_valid(agent, alt_x, alt_y):
                return (alt_x, alt_y)

        # Fallback: use original position
        return (optimal_x, optimal_y)

    def _is_position_valid(self, agent, x: float, y: float) -> bool:
        """Check if a position is valid for the agent to stand"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return True

        tile_x, tile_y = int(x), int(y)

        if not agent.agent_map.is_tile_known(tile_x, tile_y):
            return True  # Assume valid if unknown

        tile_type = agent.agent_map.get_tile_type(tile_x, tile_y)

        # Position is valid if it's walkable terrain
        from world.tiles import TileType

        return tile_type not in [TileType.WATER, TileType.WALL, TileType.LAVA]
