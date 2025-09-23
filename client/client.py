import asyncio
import json
import socket
import time
from typing import Optional, Dict, Any
from shared.messages import Message, MessageType
from shared.constants import SERVER_PORT, UDP_PORT
from client.agent import BaseAgent
from client.agent_types.player import PlayerAgent
from client.agent_types.npc import NPCAgent
from client.agent_types.enemy import EnemyAgent
from client.agent_types.explorer import ExplorerAgent
from client.agent_types.pathfinding_test import PathfindingTestAgent
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameClient:
    def __init__(self):
        self.tcp_reader: Optional[asyncio.StreamReader] = None
        self.tcp_writer: Optional[asyncio.StreamWriter] = None
        self.udp_socket: Optional[socket.socket] = None
        self.agent: Optional[BaseAgent] = None
        self.agent_id: Optional[str] = None
        self.client_id: Optional[str] = None
        self.connected = False
        self.world_state = {}
        self.visible_entities = []

    async def connect(self, host: str = '127.0.0.1', agent_type: str = 'player'):
        try:
            self.tcp_reader, self.tcp_writer = await asyncio.open_connection(
                host, SERVER_PORT
            )

            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setblocking(False)

            connect_msg = Message(
                type=MessageType.CONNECT,
                payload={'agent_type': agent_type},
                timestamp=time.time()
            )
            await self.send_tcp_message(connect_msg)

            response = await self.receive_tcp_message()
            if response and response.type == MessageType.SPAWN_AGENT:
                self.agent_id = response.payload['agent_id']
                self.client_id = response.payload.get('client_id', self.agent_id)  # Get client_id from server
                spawn_x = response.payload.get('x', 50)
                spawn_y = response.payload.get('y', 50)
                spawn_rotation = response.payload.get('rotation', 0)
                self.connected = True
                logger.info(f"Connected as agent {self.agent_id}")

                self.create_agent(agent_type, spawn_x, spawn_y, spawn_rotation)

                return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def create_agent(self, agent_type: str, x: float = 50, y: float = 50, rotation: float = 0):
        if agent_type == 'player':
            self.agent = PlayerAgent(self.agent_id, x, y)
        elif agent_type == 'npc':
            self.agent = NPCAgent(self.agent_id, x, y)
        elif agent_type == 'enemy':
            self.agent = EnemyAgent(self.agent_id, x, y)
        elif agent_type == 'explorer':
            self.agent = ExplorerAgent(self.agent_id, x, y)
        elif agent_type == 'pathfinding_test':
            # For pathfinding test, use the test agent with predefined waypoints
            test_waypoints = [(10, 10), (90, 10), (90, 90), (10, 90), (50, 50), (10, 10)]
            self.agent = PathfindingTestAgent(self.agent_id, x, y, test_waypoints)
            # Ensure agent uses the actual spawn position
            self.agent.x = x
            self.agent.y = y

        if self.agent:
            self.agent.rotation = rotation
            # Set default world bounds immediately so pathfinding can work
            # These will be updated with actual bounds when world state arrives
            self.agent.set_world_bounds(100, 100)

    async def send_tcp_message(self, message: Message):
        if self.tcp_writer:
            data = message.to_json() + '\n'
            self.tcp_writer.write(data.encode())
            await self.tcp_writer.drain()

    async def receive_tcp_message(self) -> Optional[Message]:
        if self.tcp_reader:
            try:
                data = await self.tcp_reader.readline()
                if data:
                    return Message.from_json(data.decode())
            except Exception as e:
                logger.error(f"Failed to receive message: {e}")
        return None

    def send_udp_message(self, data: dict, host: str = '127.0.0.1'):
        if self.udp_socket and self.client_id:
            data['client_id'] = self.client_id
            message = json.dumps(data).encode()
            self.udp_socket.sendto(message, (host, UDP_PORT))

    async def update(self):
        if not self.connected or not self.agent:
            return

        tasks = []

        tcp_task = asyncio.create_task(self.handle_tcp_messages())
        tasks.append(tcp_task)

        update_task = asyncio.create_task(self.update_agent())
        tasks.append(update_task)

        await asyncio.gather(*tasks)

    async def handle_tcp_messages(self):
        message = await self.receive_tcp_message()
        if message:
            if message.type == MessageType.WORLD_STATE_UPDATE:
                self.world_state = message.payload
                self.update_agent_from_world_state()

            elif message.type == MessageType.VISIBLE_ENTITIES_UPDATE:
                self.visible_entities = message.payload.get('entities', [])
                terrain_dict = message.payload.get('terrain', {})

                # Convert terrain data back to usable format
                terrain_data = {}
                for coord_str, tile_value in terrain_dict.items():
                    x_str, y_str = coord_str.split(',')
                    x, y = int(x_str), int(y_str)
                    # Import TileType here to avoid circular imports
                    from world.tiles import TileType
                    tile_type = TileType(tile_value)
                    terrain_data[(x, y)] = tile_type

                if self.agent:
                    # Update agent's personal map with discovered terrain
                    self.agent.discover_terrain_from_vision(terrain_data)
                    self.agent.perceive(self.visible_entities)

    def update_agent_from_world_state(self):
        if not self.agent or not self.agent_id:
            return

        # Set world bounds if available
        map_info = self.world_state.get('map_info')
        if map_info and not self.agent.world_bounds:
            width = map_info.get('width')
            height = map_info.get('height')
            if width and height:
                self.agent.set_world_bounds(width, height)

        agents = self.world_state.get('agents', [])
        for agent_data in agents:
            if agent_data.get('id') == self.agent_id:
                self.agent.update_from_state(agent_data)
                break

    async def update_agent(self):
        if not self.agent:
            return

        delta_time = 0.016
        self.agent.update(delta_time)

        action = self.agent.decide()
        if action:
            await self.send_action(action)

        if abs(self.agent.velocity_x) > 0.01 or abs(self.agent.velocity_y) > 0.01:
            self.send_udp_message({
                'type': 'move',
                'x': self.agent.x,
                'y': self.agent.y,
                'rotation': self.agent.rotation
            })

    async def send_action(self, action: Dict[str, Any]):
        message = Message(
            type=MessageType.AGENT_ACTION,
            payload=action,
            timestamp=time.time()
        )
        await self.send_tcp_message(message)

    async def move_to(self, x: float, y: float):
        if self.agent and isinstance(self.agent, PlayerAgent):
            self.agent.handle_input('move_to', {'x': x, 'y': y})

            message = Message(
                type=MessageType.MOVE_COMMAND,
                payload={'x': x, 'y': y, 'rotation': self.agent.rotation},
                timestamp=time.time()
            )
            await self.send_tcp_message(message)

    async def disconnect(self):
        if self.connected:
            disconnect_msg = Message(
                type=MessageType.DISCONNECT,
                payload={},
                timestamp=time.time()
            )
            await self.send_tcp_message(disconnect_msg)

            if self.tcp_writer:
                self.tcp_writer.close()
                await self.tcp_writer.wait_closed()

            if self.udp_socket:
                self.udp_socket.close()

            self.connected = False
            logger.info("Disconnected from server")

    async def run_update_loop(self):
        """Run the main client update loop"""
        try:
            while self.connected:
                await self.update()
                await asyncio.sleep(0.033)  # ~30 FPS
        except asyncio.CancelledError:
            pass

    def get_world_state(self) -> dict:
        return self.world_state

    def get_agent_state(self) -> Optional[Dict[str, Any]]:
        if self.agent:
            return self.agent.get_state()
        return None