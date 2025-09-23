import asyncio
import json
import socket
import time
from typing import Dict, Set, Optional, Any
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
        self.controlled_agents: Set[str] = set()  # Track which agents are controlled by clients

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
            self.game_loop.run(),
            self.respawn_monitor()
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

    def find_uncontrolled_agent(self, agent_type: str) -> Optional[str]:
        """Find an uncontrolled agent of the specified type"""
        all_agents = self.world.get_all_agents()
        for agent in all_agents:
            if agent.agent_type == agent_type and agent.id not in self.controlled_agents:
                return agent.id
        return None

    async def process_agent_action(self, agent_id: str, action_data: Dict[str, Any]):
        """Process actions from agents (damage, abilities, etc.)"""
        action_type = action_data.get('type')

        if action_type == 'damage':
            await self.process_damage_action(agent_id, action_data)
        else:
            logger.warning(f"Unknown action type from agent {agent_id[:8]}: {action_type}")

    async def process_damage_action(self, attacker_id: str, action_data: Dict[str, Any]):
        """Process damage dealt by one agent to another"""
        target_id = action_data.get('target_id')
        damage = action_data.get('damage', 0)

        if not target_id or damage <= 0:
            return

        # Verify attacker exists and is alive
        attacker = self.world.get_agent(attacker_id)
        if not attacker or not attacker.is_alive:
            return

        # Verify target exists and is alive
        target = self.world.get_agent(target_id)
        if not target or not target.is_alive:
            return

        # Calculate distance to verify attack is valid (prevent cheating)
        dx = target.x - attacker.x
        dy = target.y - attacker.y
        distance = (dx**2 + dy**2)**0.5

        max_attack_range = 5.0  # Maximum allowed attack range
        if distance > max_attack_range:
            logger.warning(f"Attack from {attacker_id[:8]} to {target_id[:8]} rejected: too far ({distance:.1f} > {max_attack_range})")
            return

        # Apply damage
        import time
        old_health = target.health
        target.health = max(0, target.health - damage)
        target.last_damage_time = time.time()

        logger.info(f"[DAMAGE] {attacker.agent_type} {attacker_id[:8]} dealt {damage} damage to {target.agent_type} {target_id[:8]} (health: {old_health:.0f} → {target.health:.0f})")

        # Check for death
        if target.health <= 0 and target.is_alive:
            await self.process_agent_death(target_id, attacker_id)

        # Broadcast damage event to all clients
        await self.broadcast_damage_event(attacker_id, target_id, damage, target.health)

    async def process_agent_death(self, dead_agent_id: str, killer_id: Optional[str] = None):
        """Handle agent death and setup respawn"""
        dead_agent = self.world.get_agent(dead_agent_id)
        if not dead_agent or not dead_agent.is_alive:
            return  # Already dead or doesn't exist

        dead_agent.is_alive = False
        dead_agent.health = 0  # Ensure health is 0
        import time
        dead_agent.respawn_time = time.time() + 5.0  # 5 second respawn timer

        killer_info = ""
        if killer_id:
            killer = self.world.get_agent(killer_id)
            if killer:
                killer_info = f" by {killer.agent_type} {killer_id[:8]}"

        logger.info(f"[DEATH] {dead_agent.agent_type} {dead_agent_id[:8]} has died{killer_info} - respawning in 5s")

        # Broadcast death event
        await self.broadcast_death_event(dead_agent_id, killer_id)

        # Schedule respawn - ensure it happens even if other systems fail
        asyncio.create_task(self.schedule_respawn(dead_agent_id))

    async def schedule_respawn(self, agent_id: str):
        """Schedule agent respawn after delay"""
        agent = self.world.get_agent(agent_id)
        if not agent:
            return

        import time
        respawn_delay = agent.respawn_time - time.time()
        if respawn_delay > 0:
            await asyncio.sleep(respawn_delay)

        # Check if agent still exists and needs respawn
        agent = self.world.get_agent(agent_id)
        if agent and not agent.is_alive:
            await self.respawn_agent(agent_id)

    async def respawn_agent(self, agent_id: str):
        """Respawn a dead agent"""
        agent = self.world.get_agent(agent_id)
        if not agent:
            return

        # Find safe respawn position
        existing_positions = [(a.x, a.y) for a in self.world.get_all_agents() if a.id != agent_id and a.is_alive]
        spawn_x, spawn_y = self.world.collision_detector.get_safe_spawn_position(existing_positions)

        # Reset agent state
        agent.x = spawn_x
        agent.y = spawn_y
        agent.health = agent.max_health
        agent.is_alive = True
        agent.velocity_x = 0
        agent.velocity_y = 0
        agent.respawn_time = 0

        logger.info(f"[RESPAWN] {agent.agent_type} {agent_id[:8]} respawned at ({spawn_x:.1f}, {spawn_y:.1f})")

        # Broadcast respawn event
        await self.broadcast_respawn_event(agent_id, spawn_x, spawn_y)

    async def broadcast_damage_event(self, attacker_id: str, target_id: str, damage: float, new_health: float):
        """Broadcast damage event to all clients"""
        message = Message(
            type=MessageType.DAMAGE_DEALT,
            payload={
                'attacker_id': attacker_id,
                'target_id': target_id,
                'damage': damage,
                'new_health': new_health
            },
            timestamp=time.time()
        )

        for client_id, client in self.clients.items():
            try:
                await client.send_message(message)
            except Exception as e:
                logger.error(f"Failed to send damage event to {client_id}: {e}")

    async def broadcast_death_event(self, dead_agent_id: str, killer_id: Optional[str] = None):
        """Broadcast death event to all clients"""
        message = Message(
            type=MessageType.AGENT_DEATH,
            payload={
                'dead_agent_id': dead_agent_id,
                'killer_id': killer_id
            },
            timestamp=time.time()
        )

        for client_id, client in self.clients.items():
            try:
                await client.send_message(message)
            except Exception as e:
                logger.error(f"Failed to send death event to {client_id}: {e}")

    async def broadcast_respawn_event(self, agent_id: str, x: float, y: float):
        """Broadcast respawn event to all clients"""
        message = Message(
            type=MessageType.AGENT_RESPAWN,
            payload={
                'agent_id': agent_id,
                'x': x,
                'y': y
            },
            timestamp=time.time()
        )

        for client_id, client in self.clients.items():
            try:
                await client.send_message(message)
            except Exception as e:
                logger.error(f"Failed to send respawn event to {client_id}: {e}")

    async def respawn_monitor(self):
        """Monitor for dead agents that need respawning"""
        while self.running:
            try:
                current_time = time.time()
                all_agents = self.world.get_all_agents()

                for agent in all_agents:
                    # Check if agent is dead and ready for respawn
                    if (not agent.is_alive and
                        agent.respawn_time > 0 and
                        current_time >= agent.respawn_time):

                        logger.info(f"[RESPAWN_MONITOR] Triggering respawn for {agent.agent_type} {agent.id[:8]}")
                        await self.respawn_agent(agent.id)

            except Exception as e:
                logger.error(f"Error in respawn monitor: {e}")

            await asyncio.sleep(1.0)  # Check every second

    async def disconnect_client(self, client_id: str):
        if client_id in self.clients:
            client = self.clients[client_id]
            if client.agent_id:
                # Remove from controlled agents instead of despawning
                if client.agent_id in self.controlled_agents:
                    self.controlled_agents.remove(client.agent_id)
                    logger.info(f"Agent {client.agent_id[:8]} is now uncontrolled")

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
        terrain_data = self.world.get_terrain_in_vision(client.agent_id)

        # Convert terrain data to serializable format
        terrain_dict = {}
        for (x, y), tile_type in terrain_data.items():
            terrain_dict[f"{x},{y}"] = tile_type.value

        message = Message(
            type=MessageType.VISIBLE_ENTITIES_UPDATE,
            payload={
                'entities': [agent.to_dict() for agent in visible_agents],
                'terrain': terrain_dict
            },
            timestamp=time.time()
        )

        try:
            await client.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send visible entities to {client_id}: {e}")

    def stop(self):
        self.running = False
        logger.info("Stopping server...")
        if self.tcp_server:
            self.tcp_server.close()
        if self.udp_socket:
            self.udp_socket.close()
        logger.info("Server stopped")

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

            # First try to find an uncontrolled agent of the requested type
            self.agent_id = self.server.find_uncontrolled_agent(agent_type)

            if self.agent_id:
                # Take control of existing agent
                self.server.controlled_agents.add(self.agent_id)
                logger.info(f"Client {self.client_id} taking control of existing {agent_type} agent {self.agent_id[:8]}")
            else:
                # No uncontrolled agent available, spawn a new one
                self.agent_id = self.server.world.spawn_agent(agent_type)
                self.server.controlled_agents.add(self.agent_id)
                logger.info(f"Client {self.client_id} spawned new {agent_type} agent {self.agent_id[:8]}")

            # Get the agent's position
            agent = self.server.world.get_agent(self.agent_id)

            response = Message(
                type=MessageType.SPAWN_AGENT,
                payload={
                    'agent_id': self.agent_id,
                    'client_id': self.client_id,
                    'x': agent.x,
                    'y': agent.y,
                    'rotation': agent.rotation
                },
                timestamp=time.time()
            )
            await self.send_message(response)

        elif message.type == MessageType.MOVE_COMMAND:
            if self.agent_id:
                x = message.payload.get('x')
                y = message.payload.get('y')
                rotation = message.payload.get('rotation', 0)
                velocity_x = message.payload.get('velocity_x', 0)
                velocity_y = message.payload.get('velocity_y', 0)
                self.server.world.move_agent(self.agent_id, x, y, rotation, velocity_x, velocity_y)

        elif message.type == MessageType.AGENT_ACTION:
            if self.agent_id:
                await self.server.process_agent_action(self.agent_id, message.payload)

        elif message.type == MessageType.DISCONNECT:
            await self.server.disconnect_client(self.client_id)

    async def send_message(self, message: Message):
        try:
            data = message.to_json() + '\n'
            self.writer.write(data.encode())
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Failed to send message to {self.client_id}: {e}")