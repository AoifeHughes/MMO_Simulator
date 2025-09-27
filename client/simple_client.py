"""
Simplified Game Client

This replaces the complex client system with a thin client that:
- Only handles display and user input
- Receives periodic world state updates from server
- Sends simple input commands to server
- No local AI, behavior trees, or complex state management

The server is the single source of truth for all game logic.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from shared.constants import SERVER_PORT
from shared.messages import Message, MessageType

logger = logging.getLogger(__name__)


class SimpleGameClient:
    """Simplified thin client that only handles display and input"""

    def __init__(self):
        self.tcp_reader: Optional[asyncio.StreamReader] = None
        self.tcp_writer: Optional[asyncio.StreamWriter] = None
        self.agent_id: Optional[str] = None
        self.client_id: Optional[str] = None
        self.connected = False

        # Simple state - just what we need for display
        self.world_state: Dict[str, Any] = {}
        self.agent_data: Dict[str, Any] = {}

        # Input queue for player commands
        self.pending_inputs: List[Dict[str, Any]] = []

        # Simple statistics
        self.stats = {
            "messages_received": 0,
            "messages_sent": 0,
            "updates_received": 0,
            "last_update_time": 0,
        }

    async def connect(self, host: str = "127.0.0.1", agent_type: str = "player"):
        """Connect to server and spawn agent"""
        try:
            # Establish TCP connection
            self.tcp_reader, self.tcp_writer = await asyncio.open_connection(
                host, SERVER_PORT
            )

            # Send connection request
            connect_msg = Message(
                type=MessageType.CONNECT,
                payload={"agent_type": agent_type},
                timestamp=time.time(),
            )
            await self._send_message(connect_msg)

            # Wait for spawn response
            response = await self._receive_message()
            if response and response.type == MessageType.SPAWN_AGENT:
                self.agent_id = response.payload["agent_id"]
                self.client_id = response.payload.get("client_id", self.agent_id)

                # Store initial agent data
                self.agent_data = {
                    "id": self.agent_id,
                    "x": response.payload.get("x", 50),
                    "y": response.payload.get("y", 50),
                    "rotation": response.payload.get("rotation", 0),
                    "agent_type": agent_type,
                    "health": 100.0,
                    "is_alive": True,
                }

                self.connected = True
                logger.info(
                    f"[SIMPLE CLIENT] Connected as {agent_type} agent {self.agent_id[:8]}"
                )
                return True

        except Exception as e:
            logger.error(f"[SIMPLE CLIENT] Connection failed: {e}")
            return False

        return False

    async def disconnect(self):
        """Disconnect from server"""
        if self.connected:
            disconnect_msg = Message(
                type=MessageType.DISCONNECT, payload={}, timestamp=time.time()
            )
            await self._send_message(disconnect_msg)

            if self.tcp_writer:
                self.tcp_writer.close()
                await self.tcp_writer.wait_closed()

            self.connected = False
            logger.info("[SIMPLE CLIENT] Disconnected from server")

    async def update(self):
        """Main update loop - handle messages and process inputs"""
        if not self.connected:
            return

        # Handle incoming messages
        await self._handle_messages()

        # Send pending inputs
        await self._send_pending_inputs()

    async def _handle_messages(self):
        """Handle all pending messages from server"""
        message = await self._receive_message()
        if not message:
            return

        self.stats["messages_received"] += 1

        if message.type == MessageType.WORLD_STATE_UPDATE:
            # Full world state update
            self.world_state = message.payload
            self._update_agent_from_world_state()
            self.stats["updates_received"] += 1
            self.stats["last_update_time"] = time.time()
            logger.debug(
                f"[SIMPLE CLIENT] Received world state with {len(self.world_state.get('agents', []))} agents"
            )

        elif message.type == MessageType.VISIBLE_ENTITIES_UPDATE:
            # Visible entities update (subset of world state)
            self.world_state["visible_entities"] = message.payload.get("entities", [])
            self.world_state["terrain"] = message.payload.get("terrain", {})
            logger.debug(
                f"[SIMPLE CLIENT] Received {len(self.world_state.get('visible_entities', []))} visible entities"
            )

        elif message.type == MessageType.AGENT_DEATH:
            # Handle agent death
            dead_agent_id = message.payload.get("dead_agent_id")
            if dead_agent_id == self.agent_id:
                self.agent_data["health"] = 0
                self.agent_data["is_alive"] = False
                logger.info(f"[SIMPLE CLIENT] Agent {self.agent_id[:8]} has died")

        elif message.type == MessageType.AGENT_RESPAWN:
            # Handle agent respawn
            agent_id = message.payload.get("agent_id")
            if agent_id == self.agent_id:
                self.agent_data["x"] = message.payload.get("x")
                self.agent_data["y"] = message.payload.get("y")
                self.agent_data["health"] = 100.0
                self.agent_data["is_alive"] = True
                logger.info(f"[SIMPLE CLIENT] Agent {self.agent_id[:8]} respawned")

        elif message.type == MessageType.DAMAGE_DEALT:
            # Handle damage received
            target_id = message.payload.get("target_id")
            if target_id == self.agent_id:
                new_health = message.payload.get("new_health", 0)
                self.agent_data["health"] = new_health
                damage = message.payload.get("damage", 0)
                logger.info(
                    f"[SIMPLE CLIENT] Agent {self.agent_id[:8]} took {damage} damage, health now {new_health}"
                )

    def _update_agent_from_world_state(self):
        """Update our agent data from world state"""
        if not self.agent_id or "agents" not in self.world_state:
            return

        # Find our agent in the world state
        for agent_data in self.world_state["agents"]:
            if agent_data.get("id") == self.agent_id:
                # Update our agent data with server's authoritative data
                self.agent_data.update(
                    {
                        "x": agent_data.get("x", self.agent_data.get("x", 0)),
                        "y": agent_data.get("y", self.agent_data.get("y", 0)),
                        "rotation": agent_data.get(
                            "rotation", self.agent_data.get("rotation", 0)
                        ),
                        "health": agent_data.get(
                            "health", self.agent_data.get("health", 100)
                        ),
                        "is_alive": agent_data.get(
                            "is_alive", self.agent_data.get("is_alive", True)
                        ),
                        "velocity_x": agent_data.get("velocity_x", 0),
                        "velocity_y": agent_data.get("velocity_y", 0),
                    }
                )
                break

    async def _send_pending_inputs(self):
        """Send any pending input commands to server"""
        while self.pending_inputs:
            input_data = self.pending_inputs.pop(0)
            message = Message(
                type=MessageType.AGENT_ACTION, payload=input_data, timestamp=time.time()
            )
            await self._send_message(message)
            self.stats["messages_sent"] += 1

    async def _send_message(self, message: Message):
        """Send message to server"""
        if not self.tcp_writer:
            return

        try:
            data = message.to_json() + "\n"
            self.tcp_writer.write(data.encode())
            await self.tcp_writer.drain()
        except Exception as e:
            logger.error(f"[SIMPLE CLIENT] Failed to send message: {e}")

    async def _receive_message(self) -> Optional[Message]:
        """Receive message from server"""
        if not self.tcp_reader:
            return None

        try:
            data = await self.tcp_reader.readline()
            if data:
                return Message.from_json(data.decode())
        except Exception as e:
            logger.error(f"[SIMPLE CLIENT] Failed to receive message: {e}")

        return None

    # Public interface for user input
    def move_to(self, x: float, y: float):
        """Queue a move command (for player agents)"""
        if self.agent_data.get("agent_type") == "player":
            self.pending_inputs.append(
                {"type": "move_to", "target_x": x, "target_y": y}
            )
            logger.debug(f"[SIMPLE CLIENT] Queued move to ({x:.1f}, {y:.1f})")

    def attack_target(self, target_id: str):
        """Queue an attack command (for player agents)"""
        if self.agent_data.get("agent_type") == "player":
            self.pending_inputs.append({"type": "attack", "target_id": target_id})
            logger.debug(f"[SIMPLE CLIENT] Queued attack on {target_id[:8]}")

    def use_item(self, item_id: str):
        """Queue an item use command"""
        self.pending_inputs.append({"type": "use_item", "item_id": item_id})
        logger.debug(f"[SIMPLE CLIENT] Queued use item {item_id}")

    # Public interface for display
    def get_agent_data(self) -> Dict[str, Any]:
        """Get current agent data for display"""
        return self.agent_data.copy()

    def get_world_state(self) -> Dict[str, Any]:
        """Get current world state for display"""
        return self.world_state.copy()

    def get_visible_entities(self) -> List[Dict[str, Any]]:
        """Get visible entities for display"""
        return self.world_state.get("visible_entities", [])

    def get_agent_position(self) -> tuple:
        """Get agent position for camera focus"""
        return (self.agent_data.get("x", 0), self.agent_data.get("y", 0))

    def is_agent_alive(self) -> bool:
        """Check if agent is alive"""
        return self.agent_data.get("is_alive", True)

    def get_agent_health(self) -> float:
        """Get agent health"""
        return self.agent_data.get("health", 100.0)

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics"""
        return self.stats.copy()

    # Compatibility method for existing code
    async def run_update_loop(self):
        """Run the main client update loop"""
        try:
            while self.connected:
                await self.update()
                await asyncio.sleep(0.033)  # ~30 FPS
        except asyncio.CancelledError:
            pass
