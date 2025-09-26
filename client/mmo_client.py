"""
MMO-Style Client Adapter

This module provides a client adapter that works with the new MMO server
architecture while maintaining compatibility with existing behavior trees.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from shared.messages import Message, MessageType
from shared.actions import ActionType, ActionRequest, ActionResponse, ActionResult

logger = logging.getLogger(__name__)


@dataclass
class ClientState:
    """Client-side state management"""
    agent_id: Optional[str] = None
    position: tuple = (0.0, 0.0)
    rotation: float = 0.0
    health: float = 100.0
    is_alive: bool = True
    inventory: Dict[str, Any] = None
    last_server_update: float = 0.0


class MMOClientAdapter:
    """
    Adapter class that provides MMO client functionality while maintaining
    compatibility with existing behavior tree and agent systems.
    """

    def __init__(self):
        self.connected = False
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.state = ClientState()

        # Action tracking
        self.pending_actions: Dict[str, asyncio.Future] = {}
        self.action_counter = 0

        # Event callbacks
        self.event_callbacks: Dict[str, List[Callable]] = {}

        # World state
        self.world_entities: Dict[str, Dict[str, Any]] = {}
        self.last_world_update = 0.0

    async def connect(self, agent_type: str = "player", host: str = "127.0.0.1", port: int = 9999) -> bool:
        """Connect to MMO server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)

            # Send connection request
            connect_msg = Message(MessageType.CONNECT, {
                "agent_type": agent_type
            })

            await self._send_message(connect_msg)

            # Wait for response
            response = await self._receive_message()

            if response.type == MessageType.CONNECT_RESPONSE and response.data.get("success"):
                self.connected = True
                self.state.agent_id = response.data.get("agent_id")

                spawn_pos = response.data.get("spawn_position", {})
                self.state.position = (spawn_pos.get("x", 0.0), spawn_pos.get("y", 0.0))

                logger.info(f"Connected to MMO server as agent {self.state.agent_id}")

                # Start message handling loop
                asyncio.create_task(self._message_loop())

                return True
            else:
                logger.error(f"Connection failed: {response.data.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False

    async def disconnect(self):
        """Disconnect from server"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

        self.connected = False
        self.state.agent_id = None
        logger.info("Disconnected from MMO server")

    async def request_action(self, action_type: ActionType, parameters: Dict[str, Any]) -> ActionResponse:
        """Request an action from the server and wait for response"""
        if not self.connected or not self.state.agent_id:
            return ActionResponse(
                action_id="error",
                agent_id="",
                action_type=action_type,
                result=ActionResult.ERROR,
                message="Not connected to server"
            )

        # Generate action ID
        self.action_counter += 1
        action_id = f"{self.state.agent_id}_{self.action_counter}"

        # Create future for response
        response_future = asyncio.Future()
        self.pending_actions[action_id] = response_future

        # Send action request
        action_msg = Message(MessageType.ACTION, {
            "action_id": action_id,
            "action_type": action_type.value,
            "parameters": parameters
        })

        try:
            await self._send_message(action_msg)

            # Wait for response with timeout
            response = await asyncio.wait_for(response_future, timeout=10.0)
            return response

        except asyncio.TimeoutError:
            # Clean up pending action
            if action_id in self.pending_actions:
                del self.pending_actions[action_id]

            return ActionResponse(
                action_id=action_id,
                agent_id=self.state.agent_id,
                action_type=action_type,
                result=ActionResult.ERROR,
                message="Action timeout"
            )
        except Exception as e:
            logger.error(f"Error requesting action: {e}")
            return ActionResponse(
                action_id=action_id,
                agent_id=self.state.agent_id,
                action_type=action_type,
                result=ActionResult.ERROR,
                message=f"Request failed: {str(e)}"
            )

    async def move_to(self, target_x: float, target_y: float, speed_multiplier: float = 1.0):
        """Request movement to target position"""
        move_msg = Message(MessageType.MOVEMENT, {
            "target_x": target_x,
            "target_y": target_y,
            "speed_multiplier": speed_multiplier
        })

        await self._send_message(move_msg)

    def get_world_state(self) -> Dict[str, Any]:
        """Get current world state for compatibility with existing systems"""
        world_state = {
            "agents": [],
            "world_objects": [],
            "timestamp": self.last_world_update
        }

        # Add our agent first
        if self.state.agent_id:
            our_agent = {
                "id": self.state.agent_id,
                "x": self.state.position[0],
                "y": self.state.position[1],
                "rotation": self.state.rotation,
                "health": self.state.health,
                "is_alive": self.state.is_alive,
                "inventory": self.state.inventory or {}
            }
            world_state["agents"].append(our_agent)

        # Add other entities
        for entity_id, entity_data in self.world_entities.items():
            if entity_id != self.state.agent_id:
                agent_data = {
                    "id": entity_id,
                    "x": entity_data.get("position", {}).get("x", 0.0),
                    "y": entity_data.get("position", {}).get("y", 0.0),
                    "rotation": entity_data.get("position", {}).get("rotation", 0.0),
                    "health": entity_data.get("health", {}).get("health", 100.0),
                    "is_alive": entity_data.get("health", {}).get("is_alive", True),
                }
                world_state["agents"].append(agent_data)

        return world_state

    def get_agent_position(self) -> tuple:
        """Get current agent position"""
        return self.state.position

    def get_agent_id(self) -> Optional[str]:
        """Get agent ID"""
        return self.state.agent_id

    def subscribe_to_event(self, event_type: str, callback: Callable):
        """Subscribe to server events"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)

    async def _send_message(self, message: Message):
        """Send message to server"""
        if not self.writer:
            raise ConnectionError("Not connected to server")

        try:
            data = message.to_json().encode()
            self.writer.write(len(data).to_bytes(4, 'big') + data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def _receive_message(self) -> Message:
        """Receive message from server"""
        if not self.reader:
            raise ConnectionError("Not connected to server")

        # Read message length
        length_bytes = await self.reader.readexactly(4)
        message_length = int.from_bytes(length_bytes, 'big')

        # Read message data
        data = await self.reader.readexactly(message_length)

        return Message.from_json(data.decode())

    async def _message_loop(self):
        """Main message handling loop"""
        while self.connected:
            try:
                message = await self._receive_message()
                await self._handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                break

    async def _handle_message(self, message: Message):
        """Handle incoming message from server"""
        try:
            if message.type == MessageType.WORLD_STATE:
                await self._handle_world_state(message)
            elif message.type == MessageType.ACTION_RESPONSE:
                await self._handle_action_response(message)
            elif message.type == MessageType.EVENT:
                await self._handle_event(message)
            elif message.type == MessageType.RESPAWN:
                await self._handle_respawn(message)
            elif message.type == MessageType.HEARTBEAT:
                # Respond to heartbeat
                await self._send_message(Message(MessageType.HEARTBEAT, {}))

        except Exception as e:
            logger.error(f"Error handling message {message.type}: {e}")

    async def _handle_world_state(self, message: Message):
        """Handle world state update"""
        data = message.data

        if data.get("type") == "partial_update":
            # Partial update - merge with existing state
            entities = data.get("entities", {})
            for entity_id, entity_data in entities.items():
                if entity_id == self.state.agent_id:
                    # Update our state
                    if "position" in entity_data:
                        pos_data = entity_data["position"]
                        self.state.position = (pos_data.get("x", self.state.position[0]),
                                             pos_data.get("y", self.state.position[1]))
                        self.state.rotation = pos_data.get("rotation", self.state.rotation)

                    if "health" in entity_data:
                        health_data = entity_data["health"]
                        self.state.health = health_data.get("health", self.state.health)
                        self.state.is_alive = health_data.get("is_alive", self.state.is_alive)
                else:
                    # Update other entities
                    if entity_id not in self.world_entities:
                        self.world_entities[entity_id] = {}

                    self.world_entities[entity_id].update(entity_data)
        else:
            # Full world state update
            agents = data.get("agents", [])
            for agent in agents:
                entity_id = agent.get("entity_id")
                if entity_id == self.state.agent_id:
                    # Update our state
                    if "position" in agent:
                        pos_data = agent["position"]
                        self.state.position = (pos_data.get("x", 0.0), pos_data.get("y", 0.0))
                        self.state.rotation = pos_data.get("rotation", 0.0)

                    if "health" in agent:
                        health_data = agent["health"]
                        self.state.health = health_data.get("health", 100.0)
                        self.state.is_alive = health_data.get("is_alive", True)

                    if "inventory" in agent:
                        self.state.inventory = agent["inventory"]
                else:
                    # Store other agents
                    self.world_entities[entity_id] = agent

        self.last_world_update = time.time()

    async def _handle_action_response(self, message: Message):
        """Handle action response from server"""
        data = message.data
        action_id = data.get("action_id")

        if action_id in self.pending_actions:
            future = self.pending_actions[action_id]

            response = ActionResponse(
                action_id=action_id,
                agent_id=data.get("agent_id", ""),
                action_type=ActionType(data.get("action_type", "ping")),
                result=ActionResult(data.get("result", "error")),
                message=data.get("message", ""),
                approved_parameters=data.get("approved_parameters")
            )

            future.set_result(response)
            del self.pending_actions[action_id]

    async def _handle_event(self, message: Message):
        """Handle server event"""
        event_data = message.data
        event_type = event_data.get("type", "unknown")

        # Call registered callbacks
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(event_data)
                except Exception as e:
                    logger.error(f"Error in event callback: {e}")

    async def _handle_respawn(self, message: Message):
        """Handle respawn notification"""
        data = message.data
        position = data.get("position", {})

        self.state.position = (position.get("x", 0.0), position.get("y", 0.0))
        self.state.health = 100.0
        self.state.is_alive = True

        logger.info(f"Agent respawned at {self.state.position}")