"""
Manages client connections and communication
"""

import asyncio
import time
import logging
from typing import Dict, Optional, Any
import json

from shared.messages import (
    Message, MessageType, Protocol, ClientInfo,
    ConnectMessage, WelcomeMessage, ActionMessage,
    QueryMessage, ErrorMessage
)
from shared.math_utils import Vector2
from shared.constants import (
    CLIENT_TIMEOUT, HEARTBEAT_INTERVAL, MAX_CLIENTS,
    RATE_LIMIT_WINDOW, ACTIONS_PER_SECOND
)

logger = logging.getLogger(__name__)


class ClientConnection:
    """Represents a single client connection"""

    def __init__(self, client_id: str, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter):
        self.id = client_id
        self.reader = reader
        self.writer = writer
        self.info: Optional[ClientInfo] = None
        self.connected = True
        self.last_heartbeat = time.time()

        # Rate limiting
        self.action_times: list[float] = []
        self.rate_limit_tokens = ACTIONS_PER_SECOND

    async def send(self, message: Message):
        """Send message to client"""
        if not self.connected:
            return

        try:
            data = Protocol.encode_message(message)
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending to client {self.id}: {e}")
            self.connected = False

    async def receive(self) -> Optional[Message]:
        """Receive message from client"""
        try:
            data = await self.reader.readline()
            if not data:
                self.connected = False
                return None

            message = Protocol.decode_message(data.strip())
            if message:
                self.last_heartbeat = time.time()

            return message
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"Error receiving from client {self.id}: {e}")
            self.connected = False
            return None

    def check_rate_limit(self) -> bool:
        """Check if client is within rate limits"""
        current_time = time.time()

        # Remove old action times
        self.action_times = [t for t in self.action_times
                           if current_time - t < RATE_LIMIT_WINDOW]

        # Check rate
        if len(self.action_times) >= ACTIONS_PER_SECOND:
            return False

        self.action_times.append(current_time)
        return True

    async def disconnect(self):
        """Disconnect client"""
        self.connected = False
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass


class ClientManager:
    """Manages all client connections"""

    def __init__(self, world_server):
        self.world_server = world_server
        self.clients: Dict[str, ClientConnection] = {}
        self.client_info: Dict[str, ClientInfo] = {}
        self.client_counter = 0

        logger.info("ClientManager initialized")

    async def handle_client(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter):
        """Handle a new client connection"""
        client_id = f"client_{self.client_counter}"
        self.client_counter += 1

        # Check max clients
        if len(self.clients) >= MAX_CLIENTS:
            error = ErrorMessage("Server full")
            writer.write(Protocol.encode_message(error))
            await writer.drain()
            writer.close()
            return

        # Create connection
        connection = ClientConnection(client_id, reader, writer)
        self.clients[client_id] = connection

        addr = writer.get_extra_info('peername')
        logger.info(f"Client {client_id} connected from {addr}")

        try:
            # Handle client messages
            await self._handle_client_messages(connection)
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            # Clean up
            await self._disconnect_client(client_id)

    async def _handle_client_messages(self, connection: ClientConnection):
        """Process messages from a client"""
        # Wait for connect message
        timeout = 5.0
        connect_msg = None

        try:
            connect_msg = await asyncio.wait_for(connection.receive(), timeout)
        except asyncio.TimeoutError:
            await connection.send(ErrorMessage("Connection timeout"))
            return

        if not connect_msg or connect_msg.type != MessageType.CONNECT:
            await connection.send(ErrorMessage("Expected CONNECT message"))
            return

        # Process connection
        connect_data = connect_msg
        if isinstance(connect_data, ConnectMessage):
            await self._handle_connect(connection, connect_data)
        else:
            await connection.send(ErrorMessage("Invalid CONNECT format"))
            return

        # Main message loop
        while connection.connected:
            try:
                # Check heartbeat timeout
                if time.time() - connection.last_heartbeat > CLIENT_TIMEOUT:
                    logger.warning(f"Client {connection.id} timed out")
                    break

                # Receive message with short timeout
                message = await asyncio.wait_for(connection.receive(), 1.0)
                if not message:
                    continue

                # Process message
                await self._process_message(connection, message)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message from {connection.id}: {e}")
                break

    async def _handle_connect(self, connection: ClientConnection,
                            connect_msg: ConnectMessage):
        """Handle client connection"""
        # Create agent entity
        entity = self.world_server.create_agent_entity(
            connection.id,
            connect_msg.agent_name,
            connect_msg.agent_class
        )

        # Store client info
        connection.info = ClientInfo(
            id=connection.id,
            name=connect_msg.agent_name,
            agent_class=connect_msg.agent_class,
            connection_time=time.time(),
            last_heartbeat=time.time(),
            position=entity.position.to_tuple(),
            vision_range=entity.vision_range
        )
        self.client_info[connection.id] = connection.info

        # Send welcome message
        welcome = WelcomeMessage(
            agent_id=entity.id,
            server_version="1.0.0",
            world_info={
                'width': self.world_server.game_state.spatial_grid.width,
                'height': self.world_server.game_state.spatial_grid.height,
                'tick_rate': 60
            },
            initial_position=entity.position.to_tuple(),
            vision_range=entity.vision_range
        )

        await connection.send(welcome)
        logger.info(f"Client {connection.id} authenticated as {connect_msg.agent_name}")

    async def _process_message(self, connection: ClientConnection, message: Message):
        """Process a message from client"""
        # Rate limiting for actions
        if message.type == MessageType.ACTION:
            if not connection.check_rate_limit():
                await connection.send(ErrorMessage("Rate limit exceeded"))
                return

        # Handle different message types
        if message.type == MessageType.HEARTBEAT:
            # Update heartbeat time and touch player activity
            entity_id = self.world_server.game_state.agents.get(connection.id)
            if entity_id:
                self.world_server.game_state.touch_player(entity_id)

        elif message.type == MessageType.ACTION:
            if isinstance(message, ActionMessage):
                result = await self.world_server.action_handler.handle_action(
                    connection.id, message
                )
                await connection.send(result)

        elif message.type == MessageType.QUERY:
            if isinstance(message, QueryMessage):
                result = await self.world_server.query_handler.handle_query(
                    connection.id, message
                )
                await connection.send(result)

        elif message.type == MessageType.DISCONNECT:
            connection.connected = False

        else:
            await connection.send(ErrorMessage(f"Unknown message type: {message.type}"))

    async def _disconnect_client(self, client_id: str):
        """Disconnect a client but preserve player data"""
        if client_id not in self.clients:
            return

        connection = self.clients[client_id]

        # Mark player as inactive but DON'T remove entity
        entity_id = self.world_server.game_state.agents.get(client_id)
        if entity_id:
            entity = self.world_server.game_state.get_entity(entity_id)
            if entity:
                entity.is_active = False
                entity.velocity = Vector2(0, 0)  # Stop movement
                entity.state = "disconnected"
                logger.info(f"Player {entity.name} marked as disconnected (data preserved)")

        # Close connection
        await connection.disconnect()

        # Clean up connection references only
        del self.clients[client_id]
        if client_id in self.client_info:
            del self.client_info[client_id]

        logger.info(f"Client {client_id} disconnected (player data preserved)")

    async def send_to_client(self, client_id: str, message: Message):
        """Send message to specific client"""
        if client_id in self.clients:
            await self.clients[client_id].send(message)

    async def broadcast(self, message: Message, exclude: Optional[str] = None):
        """Broadcast message to all clients"""
        tasks = []
        for client_id, connection in self.clients.items():
            if client_id != exclude:
                tasks.append(connection.send(message))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def disconnect_all(self):
        """Disconnect all clients"""
        tasks = []
        for client_id in list(self.clients.keys()):
            tasks.append(self._disconnect_client(client_id))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)