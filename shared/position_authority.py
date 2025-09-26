"""
Server-Authoritative Position System

This module implements true MMO-style position authority where:
1. Server is the single source of truth for all positions
2. Server broadcasts authoritative positions to clients
3. Clients interpolate smoothly between server updates
4. Action validation uses server position data
"""

import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from shared.messages import Message, MessageType

logger = logging.getLogger(__name__)


@dataclass
class ServerPosition:
    """Authoritative server position data"""
    x: float
    y: float
    rotation: float
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    timestamp: float = 0.0


@dataclass
class ClientPositionState:
    """Client-side position interpolation state"""
    # Server authoritative position
    server_x: float = 0.0
    server_y: float = 0.0
    server_rotation: float = 0.0
    server_timestamp: float = 0.0

    # Previous server position (for interpolation)
    prev_server_x: float = 0.0
    prev_server_y: float = 0.0
    prev_server_rotation: float = 0.0
    prev_timestamp: float = 0.0

    # Current interpolated position (what we display)
    display_x: float = 0.0
    display_y: float = 0.0
    display_rotation: float = 0.0

    # Client prediction
    predicted_x: float = 0.0
    predicted_y: float = 0.0
    predicted_rotation: float = 0.0


class ServerPositionAuthority:
    """Server-side position authority system"""

    def __init__(self):
        self.agent_positions: Dict[str, ServerPosition] = {}
        self.last_broadcast_time = 0.0
        self.broadcast_interval = 0.1  # 100ms = 10 FPS position updates

    def update_agent_position(self, agent_id: str, x: float, y: float, rotation: float = 0.0,
                            velocity_x: float = 0.0, velocity_y: float = 0.0):
        """Update server's authoritative position for an agent"""
        self.agent_positions[agent_id] = ServerPosition(
            x=x, y=y, rotation=rotation,
            velocity_x=velocity_x, velocity_y=velocity_y,
            timestamp=time.time()
        )

    def get_agent_position(self, agent_id: str) -> Optional[ServerPosition]:
        """Get server's authoritative position for an agent"""
        return self.agent_positions.get(agent_id)

    def should_broadcast_positions(self) -> bool:
        """Check if it's time to broadcast position updates"""
        current_time = time.time()
        return (current_time - self.last_broadcast_time) >= self.broadcast_interval

    def create_position_broadcast(self, client_ids: List[str] = None) -> Message:
        """Create a position sync broadcast message"""
        positions_data = {}

        for agent_id, pos in self.agent_positions.items():
            positions_data[agent_id] = {
                "x": pos.x,
                "y": pos.y,
                "rotation": pos.rotation,
                "velocity_x": pos.velocity_x,
                "velocity_y": pos.velocity_y,
                "timestamp": pos.timestamp
            }

        self.last_broadcast_time = time.time()

        return Message(
            type=MessageType.POSITION_SYNC,
            payload={
                "positions": positions_data,
                "server_timestamp": self.last_broadcast_time
            },
            timestamp=self.last_broadcast_time
        )

    def remove_agent(self, agent_id: str):
        """Remove agent from position tracking"""
        if agent_id in self.agent_positions:
            del self.agent_positions[agent_id]


class ClientPositionInterpolator:
    """Client-side position interpolation system"""

    def __init__(self):
        self.agent_states: Dict[str, ClientPositionState] = {}
        self.interpolation_speed = 0.2  # How fast to interpolate (lower = smoother)

    def update_server_position(self, agent_id: str, server_data: Dict[str, float]):
        """Update server position data and prepare for interpolation"""
        if agent_id not in self.agent_states:
            self.agent_states[agent_id] = ClientPositionState()

        state = self.agent_states[agent_id]

        # Store previous position for interpolation
        state.prev_server_x = state.server_x
        state.prev_server_y = state.server_y
        state.prev_server_rotation = state.server_rotation
        state.prev_timestamp = state.server_timestamp

        # Check for large position jumps
        if state.prev_timestamp > 0.0:  # Not the first update
            distance = ((server_data["x"] - state.server_x) ** 2 + (server_data["y"] - state.server_y) ** 2) ** 0.5
            time_delta = server_data["timestamp"] - state.server_timestamp
            if distance > 2.0 and time_delta < 0.5:  # Large jump in short time
                logger.warning(f"🚨 CLIENT position jump detected for {agent_id[:8]}: "
                             f"moved {distance:.2f} units in {time_delta:.2f}s "
                             f"from ({state.server_x:.2f}, {state.server_y:.2f}) "
                             f"to ({server_data['x']:.2f}, {server_data['y']:.2f})")

        # Update with new server data
        state.server_x = server_data["x"]
        state.server_y = server_data["y"]
        state.server_rotation = server_data["rotation"]
        state.server_timestamp = server_data["timestamp"]

        # If this is the first update, set display position immediately
        if state.prev_timestamp == 0.0:
            state.display_x = state.server_x
            state.display_y = state.server_y
            state.display_rotation = state.server_rotation

        logger.debug(f"Client received server position for {agent_id[:8]}: "
                    f"({state.server_x:.2f}, {state.server_y:.2f})")

    def interpolate_positions(self, dt: float):
        """Interpolate display positions toward server positions"""
        for agent_id, state in self.agent_states.items():
            # Interpolate toward server position
            dx = state.server_x - state.display_x
            dy = state.server_y - state.display_y
            dr = state.server_rotation - state.display_rotation

            # Apply interpolation
            interpolation_factor = min(1.0, self.interpolation_speed * dt * 60)  # 60 FPS baseline

            state.display_x += dx * interpolation_factor
            state.display_y += dy * interpolation_factor
            state.display_rotation += dr * interpolation_factor

    def get_display_position(self, agent_id: str) -> Optional[Tuple[float, float, float]]:
        """Get current display position for agent (what the client should show)"""
        if agent_id not in self.agent_states:
            return None

        state = self.agent_states[agent_id]
        return (state.display_x, state.display_y, state.display_rotation)

    def get_server_position(self, agent_id: str) -> Optional[Tuple[float, float, float]]:
        """Get last known server position for agent (for action validation)"""
        if agent_id not in self.agent_states:
            return None

        state = self.agent_states[agent_id]
        return (state.server_x, state.server_y, state.server_rotation)

    def remove_agent(self, agent_id: str):
        """Remove agent from interpolation tracking"""
        if agent_id in self.agent_states:
            del self.agent_states[agent_id]


# Global instances
server_position_authority = ServerPositionAuthority()
client_position_interpolator = ClientPositionInterpolator()


def get_server_position_for_action(agent_id: str) -> Optional[Tuple[float, float]]:
    """
    Get server-authoritative position for action validation.
    This should be used by client-side action validation to match server calculations.
    """
    pos = client_position_interpolator.get_server_position(agent_id)
    if pos:
        logger.debug(f"Server position found for {agent_id[:8]}: ({pos[0]:.2f}, {pos[1]:.2f})")
        return (pos[0], pos[1])  # Return (x, y)
    else:
        logger.debug(f"No server position data available for {agent_id[:8]} - client has {len(client_position_interpolator.agent_states)} tracked agents")
        # Log which agents we do have data for
        if client_position_interpolator.agent_states:
            tracked_agents = [aid[:8] for aid in client_position_interpolator.agent_states.keys()]
            logger.debug(f"Tracked agents: {tracked_agents}")
    return None


def update_agent_server_position(agent_id: str, x: float, y: float, rotation: float = 0.0,
                                velocity_x: float = 0.0, velocity_y: float = 0.0):
    """Convenience function for server to update authoritative position"""
    server_position_authority.update_agent_position(agent_id, x, y, rotation, velocity_x, velocity_y)


def create_position_broadcast() -> Message:
    """Convenience function to create position broadcast"""
    return server_position_authority.create_position_broadcast()


def should_broadcast_positions() -> bool:
    """Convenience function to check if positions should be broadcast"""
    return server_position_authority.should_broadcast_positions()