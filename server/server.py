import asyncio
import json
import socket
import time
from typing import Dict, Set, Optional
from server.world import ServerWorld
from server.game_loop import GameLoop
from shared.messages import Message, MessageType, WorldState, AgentData
from shared.constants import SERVER_PORT, UDP_PORT, MAX_CLIENTS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameServer:
    def __init__(self, world_width: int = 100, world_height: int = 100):
        self.world = ServerWorld(world_width, world_height)
        self.game_loop = GameLoop(self.world, self)
        self.clients: Dict[str, 'ClientConnection'] = {}
        self.udp_endpoints: Dict[str, tuple] = {}
        self.tcp_server = None
        self.udp_socket = None
        self.running = False

    async def start(self):
        self.running = True

        self.tcp_server = await asyncio.start_server(
            self.handle_tcp_client,
            '127.0.0.1',
            SERVER_PORT
        )

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setblocking(False)
        self.udp_socket.bind(('127.0.0.1', UDP_PORT))

        logger.info(f"Server started on TCP:{SERVER_PORT}, UDP:{UDP_PORT}")

        await asyncio.gather(
            self.tcp_server.serve_forever(),
            self.handle_udp_messages(),
            self.game_loop.run()
        )

    async def handle_tcp_client(self, reader: asyncio.StreamReader,
                                writer: asyncio.StreamWriter):
        client_id = str(len(self.clients))
        client = ClientConnection(client_id, reader, writer, self)
        self.clients[client_id] = client

        logger.info(f"Client {client_id} connected")

        try:
            await client.handle()
        except Exception as e:
            logger.error(f"Client {client_id} error: {e}")
        finally:
            await self.disconnect_client(client_id)

    async def handle_udp_messages(self):
        loop = asyncio.get_event_loop()
        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self.udp_socket, 1024)
                message = json.loads(data.decode())

                client_id = message.get('client_id')
                if client_id and client_id in self.clients:
                    self.udp_endpoints[client_id] = addr
                    await self.process_udp_message(client_id, message)
            except Exception as e:
                logger.error(f"UDP error: {e}")

            await asyncio.sleep(0.001)

    async def process_udp_message(self, client_id: str, message: dict):
        msg_type = message.get('type')

        if msg_type == 'move':
            agent_id = self.clients[client_id].agent_id
            if agent_id:
                x = message.get('x', 0)
                y = message.get('y', 0)
                rotation = message.get('rotation', 0)
                self.world.move_agent(agent_id, x, y, rotation)

    async def disconnect_client(self, client_id: str):
        if client_id in self.clients:
            client = self.clients[client_id]
            if client.agent_id:
                self.world.despawn_agent(client.agent_id)

            del self.clients[client_id]
            if client_id in self.udp_endpoints:
                del self.udp_endpoints[client_id]

            logger.info(f"Client {client_id} disconnected")

    async def broadcast_world_state(self):
        world_state = self.world.get_world_state()
        message = Message(
            type=MessageType.WORLD_STATE_UPDATE,
            payload=world_state,
            timestamp=time.time()
        )

        for client_id, client in self.clients.items():
            try:
                await client.send_message(message)
            except Exception as e:
                logger.error(f"Failed to send world state to {client_id}: {e}")

    async def send_visible_entities(self, client_id: str):
        if client_id not in self.clients:
            return

        client = self.clients[client_id]
        if not client.agent_id:
            return

        visible_agents = self.world.get_visible_agents(client.agent_id)
        message = Message(
            type=MessageType.VISIBLE_ENTITIES_UPDATE,
            payload={
                'entities': [agent.to_dict() for agent in visible_agents]
            },
            timestamp=time.time()
        )

        try:
            await client.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send visible entities to {client_id}: {e}")

    def stop(self):
        self.running = False
        if self.tcp_server:
            self.tcp_server.close()
        if self.udp_socket:
            self.udp_socket.close()

class ClientConnection:
    def __init__(self, client_id: str, reader: asyncio.StreamReader,
                writer: asyncio.StreamWriter, server: GameServer):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.server = server
        self.agent_id: Optional[str] = None

    async def handle(self):
        while True:
            try:
                data = await self.reader.readline()
                if not data:
                    break

                message = Message.from_json(data.decode())
                await self.process_message(message)
            except Exception as e:
                logger.error(f"Error handling client {self.client_id}: {e}")
                break

    async def process_message(self, message: Message):
        if message.type == MessageType.CONNECT:
            agent_type = message.payload.get('agent_type', 'player')
            self.agent_id = self.server.world.spawn_agent(agent_type)

            response = Message(
                type=MessageType.SPAWN_AGENT,
                payload={'agent_id': self.agent_id},
                timestamp=time.time()
            )
            await self.send_message(response)

        elif message.type == MessageType.MOVE_COMMAND:
            if self.agent_id:
                x = message.payload.get('x')
                y = message.payload.get('y')
                rotation = message.payload.get('rotation', 0)
                self.server.world.move_agent(self.agent_id, x, y, rotation)

        elif message.type == MessageType.AGENT_ACTION:
            pass

        elif message.type == MessageType.DISCONNECT:
            await self.server.disconnect_client(self.client_id)

    async def send_message(self, message: Message):
        try:
            data = message.to_json() + '\n'
            self.writer.write(data.encode())
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Failed to send message to {self.client_id}: {e}")