"""
Thin Client Agent System

This module provides simplified client agents that work with server-side AI.
These agents do not make decisions locally - they are pure renderers that
display the authoritative server state.

Key Features:
- No behavior trees or decision-making logic
- Minimal local state - everything comes from server
- Pure display/rendering functionality
- Significantly reduced complexity
- Eliminates client-server sync issues
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ThinBaseAgent(ABC):
    """
    Simplified base agent for server-side AI systems.

    This agent:
    - Receives state updates from server
    - Has no decision-making logic
    - Acts as a pure renderer/display interface
    - Cannot modify its own behavior
    """

    def __init__(self, agent_id: str, x: float, y: float, agent_type: str):
        self.id = agent_id
        self.x = x
        self.y = y
        self.rotation = 0.0
        self.agent_type = agent_type

        # Basic state (updated from server)
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.health = 100.0
        self.max_health = 100.0
        self.is_alive = True

        # Display state
        self.visible_entities: List[Dict[str, Any]] = []
        self.last_server_update = time.time()

        # Statistics for monitoring
        self.updates_received = 0
        self.last_position_update = time.time()

        logger.info(f"[THIN CLIENT] Created thin agent {agent_id[:8]} ({agent_type})")

    def update_from_server(self, server_data: Dict[str, Any]):
        """Update agent state from authoritative server data"""
        # Update position
        if "x" in server_data:
            self.x = server_data["x"]
        if "y" in server_data:
            self.y = server_data["y"]
        if "rotation" in server_data:
            self.rotation = server_data["rotation"]

        # Update movement
        if "velocity_x" in server_data:
            self.velocity_x = server_data["velocity_x"]
        if "velocity_y" in server_data:
            self.velocity_y = server_data["velocity_y"]

        # Update health
        if "health" in server_data:
            self.health = server_data["health"]
        if "max_health" in server_data:
            self.max_health = server_data["max_health"]
        if "is_alive" in server_data:
            self.is_alive = server_data["is_alive"]

        self.last_server_update = time.time()
        self.updates_received += 1

        logger.debug(f"[THIN CLIENT] Agent {self.id[:8]} updated from server")

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        """Update visible entities (pure display data from server)"""
        self.visible_entities = visible_entities
        logger.debug(f"[THIN CLIENT] Agent {self.id[:8]} received {len(visible_entities)} visible entities")

    def update(self, delta_time: float):
        """
        Minimal update method - no decision making.
        Server handles all logic, this just maintains display state.
        """
        # Check if we haven't received updates from server recently
        time_since_update = time.time() - self.last_server_update
        if time_since_update > 2.0:  # 2 seconds without server update
            logger.warning(f"[THIN CLIENT] Agent {self.id[:8]} hasn't received server update in {time_since_update:.1f}s")

        # Minimal local state maintenance for smooth rendering
        # (Server controls all real logic)
        pass

    def decide(self) -> Optional[Dict[str, Any]]:
        """
        Thin agents make no decisions - server controls all behavior.
        Returns None to indicate no client-side actions.
        """
        return None

    def handle_input(self, input_type: str, data: Dict[str, Any]):
        """
        Handle direct user input (for player agents).
        This is the only way thin agents can generate actions.
        """
        if input_type == "move_to":
            # For player agents, convert user input to server action
            return {
                "type": "user_move",
                "target_x": data.get("x", self.x),
                "target_y": data.get("y", self.y),
                "agent_id": self.id
            }
        return None

    def set_world_bounds(self, width: int, height: int):
        """Set world bounds (thin clients don't need collision detection)"""
        # Thin clients don't need collision detection or pathfinding
        # This is a no-op method to maintain compatibility
        logger.debug(f"[THIN CLIENT] Agent {self.id[:8]} received world bounds {width}x{height} (ignored)")

    def get_display_state(self) -> Dict[str, Any]:
        """Get current state for display/rendering purposes"""
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "agent_type": self.agent_type,
            "health": self.health,
            "max_health": self.max_health,
            "is_alive": self.is_alive,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
            "visible_entities": len(self.visible_entities),
            "last_update": self.last_server_update,
            "updates_received": self.updates_received
        }


class ThinPlayerAgent(ThinBaseAgent):
    """Simplified player agent for server-side AI"""

    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "player")
        logger.info(f"[THIN CLIENT] Created thin player agent {agent_id[:8]}")

    def handle_input(self, input_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle player input and convert to server actions"""
        if input_type == "move_to":
            return {
                "type": "user_move",
                "target_x": data.get("x", self.x),
                "target_y": data.get("y", self.y),
                "agent_id": self.id
            }
        elif input_type == "attack":
            return {
                "type": "user_attack",
                "agent_id": self.id
            }
        return None


class ThinEnemyAgent(ThinBaseAgent):
    """Simplified enemy agent for server-side AI"""

    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "enemy")
        logger.info(f"[THIN CLIENT] Created thin enemy agent {agent_id[:8]}")


class ThinNPCAgent(ThinBaseAgent):
    """Simplified NPC agent for server-side AI"""

    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "npc")
        logger.info(f"[THIN CLIENT] Created thin NPC agent {agent_id[:8]}")


# Factory function to create thin agents
def create_thin_agent(agent_id: str, x: float, y: float, agent_type: str) -> ThinBaseAgent:
    """Factory function to create the appropriate thin agent type"""
    if agent_type == "player":
        return ThinPlayerAgent(agent_id, x, y)
    elif agent_type == "enemy":
        return ThinEnemyAgent(agent_id, x, y)
    elif agent_type == "npc":
        return ThinNPCAgent(agent_id, x, y)
    else:
        # Default to base thin agent for unknown types
        return ThinBaseAgent(agent_id, x, y, agent_type)