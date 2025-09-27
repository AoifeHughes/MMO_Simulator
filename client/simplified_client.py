"""
Simplified Game Client with Preserved Behavior Trees

This maintains client-side decision making while simplifying the sync mechanisms:
- Behavior trees remain on client side for decision making
- Simplified TCP-only communication
- Direct position updates from server (no complex interpolation)
- Simple action request-response pattern
- Reduced message complexity while preserving AI autonomy
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from client.agent import BaseAgent
from client.agent_types.enemy import EnemyAgent
from client.agent_types.explorer import ExplorerAgent
from client.agent_types.npc import NPCAgent
from client.agent_types.pathfinding_test import PathfindingTestAgent
from client.agent_types.player import PlayerAgent
from shared.constants import SERVER_PORT
from shared.simple_messages import (
    SimpleActionType,
    SimpleMessage,
    SimpleMessageType,
    create_action_request_message,
    create_connect_message,
    create_disconnect_message,
)

logger = logging.getLogger(__name__)


class SimplifiedGameClient:
    """
    Simplified client that preserves behavior trees while fixing sync issues
    """

    def __init__(self):
        # Connection
        self.tcp_reader: Optional[asyncio.StreamReader] = None
        self.tcp_writer: Optional[asyncio.StreamWriter] = None
        self.connected = False

        # Agent (preserves behavior tree system)
        self.agent: Optional[BaseAgent] = None
        self.agent_id: Optional[str] = None
        self.client_id: Optional[str] = None

        # Simple state tracking
        self.world_state: Dict[str, Any] = {}
        self.other_agents: List[Dict[str, Any]] = []

        # Action management (simplified)
        self.pending_action_requests: Dict[str, float] = {}  # request_id -> timestamp
        self.action_sequence = 0

        # Statistics
        self.stats = {
            "messages_received": 0,
            "messages_sent": 0,
            "actions_sent": 0,
            "actions_completed": 0,
            "last_world_update": 0,
        }

    async def connect(self, host: str = "127.0.0.1", agent_type: str = "player"):
        """Connect to simplified server"""
        try:
            # Establish TCP connection
            self.tcp_reader, self.tcp_writer = await asyncio.open_connection(
                host, SERVER_PORT
            )

            # Send connection request
            connect_msg = create_connect_message(agent_type)
            await self._send_message(connect_msg)

            # Wait for connection response
            response = await self._receive_message()
            if response and response.type == SimpleMessageType.WORLD_UPDATE:
                payload = response.payload

                if payload.get("connection_success"):
                    self.agent_id = payload["agent_id"]
                    self.client_id = payload["client_id"]
                    agent_data = payload["agent_data"]

                    # Create agent with behavior tree system
                    self._create_agent(agent_type, agent_data)

                    self.connected = True
                    logger.info(
                        f"[SIMPLIFIED CLIENT] Connected as {agent_type} agent {self.agent_id[:8]}"
                    )
                    return True

        except Exception as e:
            logger.error(f"[SIMPLIFIED CLIENT] Connection failed: {e}")
            return False

        return False

    def _create_agent(self, agent_type: str, agent_data: Dict[str, Any]):
        """Create agent with behavior tree (preserves existing system)"""
        x = agent_data.get("x", 50)
        y = agent_data.get("y", 50)
        rotation = agent_data.get("rotation", 0)

        # Create agent based on type (preserves behavior tree system)
        if agent_type == "player":
            self.agent = PlayerAgent(self.agent_id, x, y)
        elif agent_type == "npc":
            self.agent = NPCAgent(self.agent_id, x, y)
        elif agent_type == "enemy":
            self.agent = EnemyAgent(self.agent_id, x, y)
        elif agent_type == "explorer":
            self.agent = ExplorerAgent(self.agent_id, x, y)
        elif agent_type == "pathfinding_test":
            self.agent = PathfindingTestAgent(self.agent_id, x, y, [(10, 10), (90, 90)])
        else:
            # Default to explorer
            self.agent = ExplorerAgent(self.agent_id, x, y)

        # Set initial properties
        self.agent.rotation = rotation
        self.agent.health = agent_data.get("health", 100)

        # Set simplified action callback
        self.agent.simplified_action_callback = self._send_agent_action

        # Set world bounds for pathfinding
        self.agent.set_world_bounds(100, 100)  # Default bounds, will be updated

        # Add simplified behavior trees if agent doesn't have one
        if not hasattr(self.agent, "behavior_tree") or not self.agent.behavior_tree:
            from client.behavior_tree_adapter import add_simplified_trees_to_agent

            add_simplified_trees_to_agent(self.agent)

        logger.info(
            f"[SIMPLIFIED CLIENT] Created {agent_type} agent {self.agent_id[:8]} with behavior tree"
        )

    async def disconnect(self):
        """Disconnect from server"""
        if self.connected:
            disconnect_msg = create_disconnect_message()
            await self._send_message(disconnect_msg)

            if self.tcp_writer:
                self.tcp_writer.close()
                await self.tcp_writer.wait_closed()

            self.connected = False
            logger.info("[SIMPLIFIED CLIENT] Disconnected from server")

    async def update(self):
        """Main update loop"""
        if not self.connected or not self.agent:
            return

        # Handle server messages
        await self._handle_messages()

        # Update agent behavior tree (preserves client-side AI)
        delta_time = 0.016  # ~60 FPS
        if hasattr(self.agent, "update_behavior_tree"):
            self.agent.update_behavior_tree(delta_time)
        else:
            self.agent.update(delta_time)

        # Clean up old action requests
        await self._cleanup_old_requests()

    async def _handle_messages(self):
        """Handle incoming messages from server"""
        message = await self._receive_message()
        if not message:
            return

        self.stats["messages_received"] += 1

        if message.type == SimpleMessageType.WORLD_UPDATE:
            await self._handle_world_update(message)
        elif message.type == SimpleMessageType.ACTION_RESPONSE:
            await self._handle_action_response(message)
        elif message.type == SimpleMessageType.GAME_EVENT:
            await self._handle_game_event(message)

    async def _handle_world_update(self, message: SimpleMessage):
        """Handle world state update from server"""
        payload = message.payload
        self.world_state = payload
        self.stats["last_world_update"] = time.time()

        # Update world bounds
        world_info = payload.get("world_info", {})
        if world_info and self.agent:
            width = world_info.get("width", 100)
            height = world_info.get("height", 100)
            if not self.agent.world_bounds or self.agent.world_bounds != (
                width,
                height,
            ):
                self.agent.set_world_bounds(width, height)

        # Get agents data
        agents = payload.get("agents", [])

        # Update our agent with server's authoritative data
        for agent_data in agents:
            if agent_data.get("id") == self.agent_id:
                self._update_agent_from_server(agent_data)
                break

        # Store other agents for visibility/perception
        self.other_agents = [a for a in agents if a.get("id") != self.agent_id]

        # Update agent perception (for behavior tree)
        if self.agent:
            self.agent.perceive(self.other_agents)

        logger.debug(
            f"[SIMPLIFIED CLIENT] World update: {len(agents)} agents, {len(self.other_agents)} visible"
        )

    def _update_agent_from_server(self, server_data: Dict[str, Any]):
        """Update agent with authoritative server data"""
        if not self.agent:
            return

        # Update position (server authority)
        self.agent.x = server_data.get("x", self.agent.x)
        self.agent.y = server_data.get("y", self.agent.y)
        self.agent.rotation = server_data.get("rotation", self.agent.rotation)

        # Update health and status
        self.agent.health = server_data.get("health", self.agent.health)
        self.agent.max_health = server_data.get("max_health", self.agent.max_health)
        self.agent.is_alive = server_data.get("is_alive", self.agent.is_alive)

        # Update velocity for smooth display
        self.agent.velocity_x = server_data.get("velocity_x", 0)
        self.agent.velocity_y = server_data.get("velocity_y", 0)

    async def _handle_action_response(self, message: SimpleMessage):
        """Handle action response from server"""
        payload = message.payload
        request_id = payload.get("request_id")
        success = payload.get("success", False)
        result_message = payload.get("message", "")

        # Remove from pending requests
        if request_id in self.pending_action_requests:
            del self.pending_action_requests[request_id]
            self.stats["actions_completed"] += 1

        if success:
            logger.debug(
                f"[SIMPLIFIED CLIENT] Action {request_id} succeeded: {result_message}"
            )

            # Handle specific action results
            result_data = payload.get("result", {})
            if "fishing_time" in result_data:
                fishing_success = result_data.get("success", False)
                if fishing_success:
                    logger.info(f"🎣 Agent {self.agent_id[:8]} caught a fish!")
                else:
                    logger.info(f"🎣 Agent {self.agent_id[:8]} fishing unsuccessful")
            elif "harvest_time" in result_data:
                logger.info(f"🌲 Agent {self.agent_id[:8]} harvested wood!")
        else:
            logger.warning(
                f"[SIMPLIFIED CLIENT] Action {request_id} failed: {result_message}"
            )

    async def _handle_game_event(self, message: SimpleMessage):
        """Handle game events from server"""
        payload = message.payload
        event_type = payload.get("event_type")
        event_data = payload.get("data", {})

        if event_type == "agent_death":
            dead_agent_id = event_data.get("dead_agent_id")
            if dead_agent_id == self.agent_id:
                logger.info(f"[SIMPLIFIED CLIENT] Agent {self.agent_id[:8]} has died")
                if self.agent:
                    self.agent.is_alive = False
                    self.agent.health = 0
        elif event_type == "agent_respawn":
            respawn_agent_id = event_data.get("agent_id")
            if respawn_agent_id == self.agent_id:
                logger.info(f"[SIMPLIFIED CLIENT] Agent {self.agent_id[:8]} respawned")
                if self.agent:
                    self.agent.is_alive = True
                    self.agent.health = self.agent.max_health

    async def _send_agent_action(self, action_type: str, parameters: Dict[str, Any]):
        """Send action request to server (called by agent behavior tree)"""
        if not self.connected:
            return

        # Generate request ID
        self.action_sequence += 1
        request_id = f"{self.agent_id[:8]}_{self.action_sequence}"

        # Create and send action request
        action_msg = create_action_request_message(
            action_type, parameters, self.agent_id, request_id
        )
        await self._send_message(action_msg)

        # Track pending request
        self.pending_action_requests[request_id] = time.time()
        self.stats["actions_sent"] += 1

        logger.debug(
            f"[SIMPLIFIED CLIENT] Sent action {action_type} with ID {request_id}"
        )

    async def _send_message(self, message: SimpleMessage):
        """Send message to server"""
        if not self.tcp_writer:
            return

        try:
            data = message.to_json() + "\n"
            self.tcp_writer.write(data.encode())
            await self.tcp_writer.drain()
            self.stats["messages_sent"] += 1
        except Exception as e:
            logger.error(f"[SIMPLIFIED CLIENT] Failed to send message: {e}")

    async def _receive_message(self) -> Optional[SimpleMessage]:
        """Receive message from server"""
        if not self.tcp_reader:
            return None

        try:
            data = await self.tcp_reader.readline()
            if data:
                return SimpleMessage.from_json(data.decode())
        except Exception as e:
            logger.error(f"[SIMPLIFIED CLIENT] Failed to receive message: {e}")

        return None

    async def _cleanup_old_requests(self):
        """Clean up old pending action requests"""
        current_time = time.time()
        timeout = 10.0  # 10 second timeout

        expired_requests = [
            req_id
            for req_id, timestamp in self.pending_action_requests.items()
            if (current_time - timestamp) > timeout
        ]

        for req_id in expired_requests:
            del self.pending_action_requests[req_id]
            logger.warning(f"[SIMPLIFIED CLIENT] Action request {req_id} timed out")

    # Public interface methods (for compatibility)
    def get_world_state(self) -> Dict[str, Any]:
        """Get world state for external use"""
        return self.world_state

    def get_agent_state(self) -> Optional[Dict[str, Any]]:
        """Get agent state for external use"""
        if self.agent:
            return self.agent.get_state()
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        stats = self.stats.copy()
        stats["pending_requests"] = len(self.pending_action_requests)
        stats["connected"] = self.connected
        return stats

    async def run_update_loop(self):
        """Run the main client update loop"""
        try:
            while self.connected:
                await self.update()
                await asyncio.sleep(0.033)  # ~30 FPS
        except asyncio.CancelledError:
            pass


# Helper function to add simplified action capability to existing agents
def add_simplified_action_support(agent: BaseAgent):
    """Add simplified action support to existing agent"""

    def send_move_action(target_x: float, target_y: float):
        if hasattr(agent, "simplified_action_callback"):
            asyncio.create_task(
                agent.simplified_action_callback(
                    SimpleActionType.MOVE_TO,
                    {"target_x": target_x, "target_y": target_y},
                )
            )

    def send_attack_action(target_id: str):
        if hasattr(agent, "simplified_action_callback"):
            asyncio.create_task(
                agent.simplified_action_callback(
                    SimpleActionType.ATTACK, {"target_id": target_id}
                )
            )

    def send_fish_action():
        if hasattr(agent, "simplified_action_callback"):
            asyncio.create_task(
                agent.simplified_action_callback(SimpleActionType.FISH, {})
            )

    def send_harvest_wood_action():
        if hasattr(agent, "simplified_action_callback"):
            asyncio.create_task(
                agent.simplified_action_callback(SimpleActionType.HARVEST_WOOD, {})
            )

    def send_stop_action():
        if hasattr(agent, "simplified_action_callback"):
            asyncio.create_task(
                agent.simplified_action_callback(SimpleActionType.STOP, {})
            )

    # Add methods to agent
    agent.send_move_action = send_move_action
    agent.send_attack_action = send_attack_action
    agent.send_fish_action = send_fish_action
    agent.send_harvest_wood_action = send_harvest_wood_action
    agent.send_stop_action = send_stop_action
