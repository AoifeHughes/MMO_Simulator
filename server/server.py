import asyncio
import json
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Set

from server.agent_ai import ServerAI
from server.agent_state import AgentRegistry
from server.attack_system import AttackSystem
from server.game_loop import GameLoop
from server.world import ServerWorld
from shared.constants import MAX_CLIENTS, SERVER_PORT, UDP_PORT
from shared.messages import AgentData, Message, MessageType, WorldState
from world.terrain_generator import TerrainType
from shared.position_authority import should_broadcast_positions, create_position_broadcast

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GameServer:
    def __init__(
        self,
        world_width: int = 100,
        world_height: int = 100,
        terrain_type: Optional[TerrainType] = None,
        seed: int = 42,
    ):
        self.world = ServerWorld(
            world_width, world_height, terrain_type=terrain_type, seed=seed
        )
        self.game_loop = GameLoop(self.world, self)
        self.agent_registry = AgentRegistry()
        self.attack_system = AttackSystem()
        self.ai_system = ServerAI()

        # Initialize new action processing system
        from server.action_processor import ActionProcessor
        self.action_processor = ActionProcessor(
            world=self.world,
            agent_registry=self.agent_registry,
            attack_system=self.attack_system,
        )
        self.clients: Dict[str, "ClientConnection"] = {}
        self.udp_endpoints: Dict[str, tuple] = {}
        self.tcp_server = None
        self.udp_socket = None
        self.running = False

        # Database system
        from server.database import DatabaseManager, PeriodicDataCollector
        self.database_manager = DatabaseManager()
        self.data_collector: Optional[PeriodicDataCollector] = None

        # Set world dimensions for exploration tracking
        self.agent_registry.set_world_dimensions(world_width, world_height)

    async def start(self):
        self.running = True

        self.tcp_server = await asyncio.start_server(
            self.handle_tcp_client, "127.0.0.1", SERVER_PORT
        )

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setblocking(False)
        self.udp_socket.bind(("127.0.0.1", UDP_PORT))

        # Start action processor
        await self.action_processor.start()

        logger.info(f"Server started on TCP:{SERVER_PORT}, UDP:{UDP_PORT}")

        await asyncio.gather(
            self.tcp_server.serve_forever(),
            self.handle_udp_messages(),
            self.game_loop.run(),
            self.respawn_monitor(),
        )

    async def handle_tcp_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
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
        # Ensure logger is available in this async context
        import logging
        udp_logger = logging.getLogger(__name__)

        loop = asyncio.get_event_loop()
        while self.running:
            try:
                data, addr = await loop.sock_recvfrom(self.udp_socket, 1024)
                message = json.loads(data.decode())

                client_id = message.get("client_id")
                if client_id and client_id in self.clients:
                    self.udp_endpoints[client_id] = addr
                    await self.process_udp_message(client_id, message)
            except Exception as e:
                # Use the locally defined logger to avoid scope issues
                udp_logger.error(f"UDP error: {e}")

            await asyncio.sleep(0.001)

    async def process_udp_message(self, client_id: str, message: dict):
        msg_type = message.get("type")

        if msg_type == "move":
            agent_id = self.clients[client_id].agent_id
            if agent_id:
                x = message.get("x", 0)
                y = message.get("y", 0)
                rotation = message.get("rotation", 0)
                self.world.move_agent(agent_id, x, y, rotation)

    def find_uncontrolled_agent(self, agent_type: str) -> Optional[str]:
        """Find an uncontrolled agent of the specified type"""
        uncontrolled = self.agent_registry.get_uncontrolled_agents(agent_type)
        return uncontrolled[0] if uncontrolled else None

    async def process_agent_action(self, agent_id: str, action_data: Dict[str, Any]):
        """Process actions from agents (damage, abilities, etc.)"""
        action_type = action_data.get("type")

        if action_type == "damage":
            await self.process_damage_action(agent_id, action_data)
        elif action_type == "exploration_report":
            # Handle exploration reports - update agent statistics
            agent_state = self.agent_registry.get_agent(agent_id)
            if agent_state:
                explored_tiles = action_data.get("explored_tiles", 0)
                total_tiles = action_data.get("total_tiles", 1)
                exploration_percent = action_data.get("exploration_percent", 0.0)

                agent_state.stats["exploration_percent"] = exploration_percent
                agent_state.stats["explored_tiles_count"] = explored_tiles
                logger.debug(f"Updated exploration stats for {agent_id[:8]}: {exploration_percent:.1f}%")
        else:
            logger.warning(
                f"Unknown action type from agent {agent_id[:8]}: {action_type}"
            )

    async def process_damage_action(
        self, attacker_id: str, action_data: Dict[str, Any]
    ):
        """Process damage dealt by one agent to another"""
        target_id = action_data.get("target_id")
        attack_name = action_data.get("attack_name", "punch")  # Default to basic attack

        if not target_id:
            return

        # Verify attacker exists and is alive
        attacker = self.world.get_agent(attacker_id)
        if not attacker or not attacker.is_alive:
            return

        # Verify target exists and is alive
        target = self.world.get_agent(target_id)
        if not target or not target.is_alive:
            return

        # Get attacker's last attack time from agent registry
        attacker_state = self.agent_registry.get_agent(attacker_id)
        last_attack_time = (
            getattr(attacker_state, "last_attack_time", 0) if attacker_state else 0
        )

        # Validate attack using attack system
        is_valid, reason = self.attack_system.validate_attack(
            attacker_id,
            attack_name,
            target_id,
            (attacker.x, attacker.y),
            (target.x, target.y),
            attacker.agent_type,
            last_attack_time,
        )

        if not is_valid:
            logger.warning(
                f"Attack from {attacker_id[:8]} to {target_id[:8]} rejected: {reason}"
            )
            return

        # Get attack definition for damage calculation
        attack_def = self.attack_system.get_attack_definition(attack_name)
        if not attack_def:
            logger.warning(f"Unknown attack: {attack_name}")
            return

        # Apply damage
        old_health = target.health
        target.health = max(0, target.health - attack_def.damage)
        target.last_damage_time = time.time()

        # Update attacker's last attack time
        if attacker_state:
            attacker_state.last_attack_time = time.time()

        logger.info(
            f"[DAMAGE] {attacker.agent_type} {attacker_id[:8]} used {attack_name} on {target.agent_type} {target_id[:8]} for {attack_def.damage} damage (health: {old_health:.0f} → {target.health:.0f})"
        )

        # Check for death and process immediately
        if target.health <= 0 and target.is_alive:
            target.is_alive = False  # Mark as dead immediately
            await self.process_agent_death(target_id, attacker_id)

        # Broadcast damage event to all clients
        await self.broadcast_damage_event(
            attacker_id, target_id, attack_def.damage, target.health
        )

    async def schedule_immediate_death(self, dead_agent_id: str):
        """Immediately process agent death without a killer"""
        await self.process_agent_death(dead_agent_id, None)

    async def process_agent_death(
        self, dead_agent_id: str, killer_id: Optional[str] = None
    ):
        """Handle agent death and setup respawn"""
        dead_agent = self.world.get_agent(dead_agent_id)
        if not dead_agent:
            return  # Agent doesn't exist

        # Ensure agent is marked as dead immediately
        if dead_agent.is_alive:
            dead_agent.is_alive = False

        dead_agent.health = 0  # Ensure health is 0
        import time

        dead_agent.respawn_time = time.time() + 5.0  # 5 second respawn timer

        killer_info = ""
        if killer_id:
            killer = self.world.get_agent(killer_id)
            if killer:
                killer_info = f" by {killer.agent_type} {killer_id[:8]}"

        logger.info(
            f"[DEATH] {dead_agent.agent_type} {dead_agent_id[:8]} has died{killer_info} - respawning in 5s"
        )

        # Broadcast death event immediately
        await self.broadcast_death_event(dead_agent_id, killer_id)

        # Send immediate client updates to reflect the death state
        # This ensures dead agents disappear from all clients immediately
        await self.send_client_updates()

        # Schedule respawn - ensure it happens even if other systems fail
        asyncio.create_task(self.schedule_respawn(dead_agent_id))

    async def schedule_respawn(self, agent_id: str):
        """Schedule agent respawn after delay"""
        agent = self.world.get_agent(agent_id)
        if not agent:
            return

        import time

        # Check if respawn_time is set
        if agent.respawn_time is None or agent.respawn_time <= 0:
            logger.debug(f"Agent {agent_id[:8]} has no respawn time set, skipping respawn scheduling")
            return

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

        # Find safe respawn position on walkable terrain
        existing_positions = [
            (a.x, a.y)
            for a in self.world.get_all_agents()
            if a.id != agent_id and a.is_alive
        ]
        spawn_x, spawn_y = self.world.collision_detector.get_safe_spawn_position(
            existing_positions, world_map=self.world.world_map
        )

        # Reset agent state
        agent.x = spawn_x
        agent.y = spawn_y
        agent.health = agent.max_health
        agent.is_alive = True
        agent.velocity_x = 0
        agent.velocity_y = 0
        agent.respawn_time = 0

        logger.info(
            f"[RESPAWN] {agent.agent_type} {agent_id[:8]} respawned at ({spawn_x:.1f}, {spawn_y:.1f})"
        )

        # Broadcast respawn event
        await self.broadcast_respawn_event(agent_id, spawn_x, spawn_y)

    async def broadcast_damage_event(
        self, attacker_id: str, target_id: str, damage: float, new_health: float
    ):
        """Broadcast damage event to all clients"""
        message = Message(
            type=MessageType.DAMAGE_DEALT,
            payload={
                "attacker_id": attacker_id,
                "target_id": target_id,
                "damage": damage,
                "new_health": new_health,
            },
            timestamp=time.time(),
        )

        for client_id, client in self.clients.items():
            try:
                await client.send_message(message)
            except Exception as e:
                logger.error(f"Failed to send damage event to {client_id}: {e}")

    async def broadcast_death_event(
        self, dead_agent_id: str, killer_id: Optional[str] = None
    ):
        """Broadcast death event to all clients"""
        message = Message(
            type=MessageType.AGENT_DEATH,
            payload={"dead_agent_id": dead_agent_id, "killer_id": killer_id},
            timestamp=time.time(),
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
            payload={"agent_id": agent_id, "x": x, "y": y},
            timestamp=time.time(),
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
                    if (
                        not agent.is_alive
                        and agent.respawn_time > 0
                        and current_time >= agent.respawn_time
                    ):
                        logger.info(
                            f"[RESPAWN_MONITOR] Triggering respawn for {agent.agent_type} {agent.id[:8]}"
                        )
                        await self.respawn_agent(agent.id)

            except Exception as e:
                logger.error(f"Error in respawn monitor: {e}")

            await asyncio.sleep(1.0)  # Check every second

    async def disconnect_client(self, client_id: str):
        if client_id in self.clients:
            client = self.clients[client_id]
            if client.agent_id:
                # Remove from controlled agents instead of despawning
                self.agent_registry.unassign_agent(client.agent_id)
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
            timestamp=time.time(),
        )

        for client_id, client in self.clients.items():
            try:
                await client.send_message(message)
            except Exception as e:
                logger.error(f"Failed to send world state to {client_id}: {e}")

    async def send_client_updates(self):
        """Send standardized 500ms update packets to all clients"""

        # Send position broadcasts if it's time (100ms intervals)
        if should_broadcast_positions():
            logger.debug("Broadcasting positions - 100ms interval reached")
            await self.broadcast_positions()
        else:
            logger.debug("Skipping position broadcast - interval not reached")

        for client_id, client in self.clients.items():
            try:
                await self.send_client_update(client_id)
            except Exception as e:
                logger.error(f"Failed to send client update to {client_id}: {e}")

    async def broadcast_positions(self):
        """Broadcast authoritative positions to all clients"""
        try:
            position_message = create_position_broadcast()

            # Enhanced logging: check what positions are being broadcast
            if position_message.payload and "positions" in position_message.payload:
                positions_data = position_message.payload["positions"]
                logger.debug(f"Broadcasting {len(positions_data)} agent positions to {len(self.clients)} clients")

                # Log a sample position for debugging
                if positions_data:
                    sample_agent_id = next(iter(positions_data))
                    sample_pos = positions_data[sample_agent_id]
                    logger.debug(f"Sample position - Agent {sample_agent_id[:8]}: ({sample_pos['x']:.2f}, {sample_pos['y']:.2f})")
            else:
                logger.warning("Position broadcast message has no position data")

            for client_id, client in self.clients.items():
                if client.agent_id:  # Only send to clients with agents
                    await client.send_message(position_message)

            logger.debug(f"Broadcasted positions to {len(self.clients)} clients")
        except Exception as e:
            logger.error(f"Failed to broadcast positions: {e}")

    async def send_client_update(self, client_id: str):
        """Send comprehensive update packet to a specific client"""
        if client_id not in self.clients:
            return

        client = self.clients[client_id]
        if not client.agent_id:
            return

        # Get visible agents for this client
        visible_agents = self.world.get_visible_agents(client.agent_id)

        # Debug: Log visibility data being sent to client (reduced verbosity)
        logger.debug(f"[VISIBILITY] Client {client_id} (agent {client.agent_id[:8]}) can see {len(visible_agents)} entities")
        if len(visible_agents) > 0:
            enemy_count = sum(1 for a in visible_agents if a.agent_type != getattr(self.world.get_agent(client.agent_id), 'agent_type', ''))
            logger.debug(f"[VISIBILITY] - Including {enemy_count} potential targets")

        # Get terrain data within vision range
        terrain_data = self.world.get_terrain_in_vision(client.agent_id)

        # Convert terrain data to serializable format
        terrain_dict = {}
        for (x, y), tile_type in terrain_data.items():
            terrain_dict[f"{x},{y}"] = tile_type.value

        # Create comprehensive update packet (maintain compatibility with client)
        update_payload = {
            "entities": [
                agent.to_dict() for agent in visible_agents
            ],  # Client expects "entities"
            "terrain": terrain_dict,  # Client expects "terrain"
            "world_bounds": {
                "width": self.world.world_map.width,
                "height": self.world.world_map.height,
            },
            "events": [],  # TODO: Add combat/damage events in future
            "timestamp": time.time(),
        }

        message = Message(
            type=MessageType.VISIBLE_ENTITIES_UPDATE,
            payload=update_payload,
            timestamp=time.time(),
        )

        try:
            await client.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send client update to {client_id}: {e}")

    async def send_visible_entities(self, client_id: str):
        """Legacy method - replaced by send_client_update"""
        await self.send_client_update(client_id)

    async def stop(self):
        self.running = False
        logger.info("Stopping server...")

        # Stop data collection and save final snapshot
        if self.data_collector:
            await self.data_collector.stop()

        # End scenario and close database
        await self.database_manager.end_scenario()
        await self.database_manager.close()

        # Stop action processor
        await self.action_processor.stop()

        if self.tcp_server:
            self.tcp_server.close()
        if self.udp_socket:
            self.udp_socket.close()
        logger.info("Server stopped")

    async def start_scenario_tracking(self, scenario_name: str):
        """Initialize database tracking for a scenario"""
        from server.database import PeriodicDataCollector

        # Initialize database and start scenario
        await self.database_manager.initialize()
        await self.database_manager.start_scenario(
            scenario_name,
            self.world.world_map.width,
            self.world.world_map.height
        )

        # Start periodic data collection
        self.data_collector = PeriodicDataCollector(
            self.database_manager,
            self.agent_registry
        )
        await self.data_collector.start()

        logger.info(f"Started database tracking for scenario: {scenario_name}")

    def process_agent_vision_update(self, agent_id: str, discovered_tiles: List[tuple]):
        """Process vision updates from agents for exploration tracking"""
        self.agent_registry.process_agent_vision_update(agent_id, discovered_tiles)


class ClientConnection:
    def __init__(
        self,
        client_id: str,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        server: GameServer,
    ):
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
            agent_type = message.payload.get("agent_type", "player")

            # First try to find an uncontrolled agent of the requested type
            self.agent_id = self.server.find_uncontrolled_agent(agent_type)

            if self.agent_id:
                # Take control of existing agent
                self.server.agent_registry.assign_agent_to_client(
                    self.agent_id, self.client_id
                )
                logger.info(
                    f"Client {self.client_id} taking control of existing {agent_type} agent {self.agent_id[:8]}"
                )
            else:
                # No uncontrolled agent available, spawn a new one
                self.agent_id = self.server.world.spawn_agent(agent_type)

                # Register the new agent in the registry
                agent = self.server.world.get_agent(self.agent_id)
                if agent:
                    self.server.agent_registry.register_agent(
                        self.agent_id, agent_type, agent.x, agent.y
                    )
                    # Register with AI system
                    self.server.ai_system.register_agent(
                        self.agent_id, agent_type, agent.x, agent.y
                    )

                self.server.agent_registry.assign_agent_to_client(
                    self.agent_id, self.client_id
                )
                logger.info(
                    f"Client {self.client_id} spawned new {agent_type} agent {self.agent_id[:8]}"
                )

            # Get the agent's position
            agent = self.server.world.get_agent(self.agent_id)

            # Get attack system data for this character type
            attack_data = self.server.attack_system.get_all_attacks_for_client()

            # Get agent state for additional data
            agent_state = self.server.agent_registry.get_agent(self.agent_id)

            # Check if agent has personality configuration from scenario
            personality_config = None
            if agent_state and hasattr(agent_state, 'personality_config'):
                personality_config = agent_state.personality_config

            response_payload = {
                "agent_id": self.agent_id,
                "client_id": self.client_id,
                "x": agent.x,
                "y": agent.y,
                "rotation": agent.rotation,
                "attack_data": attack_data,
                "exploration_mode": agent_state.exploration_mode if agent_state else "frontier",
            }

            # Add personality configuration if available
            if personality_config:
                response_payload["personality_config"] = personality_config

            response = Message(
                type=MessageType.SPAWN_AGENT,
                payload=response_payload,
                timestamp=time.time(),
            )
            await self.send_message(response)

        elif message.type == MessageType.MOVE_COMMAND:
            if self.agent_id:
                # Check if agent is alive before processing movement
                agent = self.server.world.get_agent(self.agent_id)
                if agent and not agent.is_alive:
                    # Ignore movement commands from dead agents
                    return

                x = message.payload.get("x")
                y = message.payload.get("y")
                rotation = message.payload.get("rotation", 0)
                velocity_x = message.payload.get("velocity_x", 0)
                velocity_y = message.payload.get("velocity_y", 0)
                self.server.world.move_agent(
                    self.agent_id, x, y, rotation, velocity_x, velocity_y
                )

        elif message.type == MessageType.AGENT_ACTION:
            if self.agent_id:
                # Check if agent is alive before processing actions
                agent = self.server.world.get_agent(self.agent_id)
                if agent and not agent.is_alive:
                    # Ignore actions from dead agents
                    return

                await self.server.process_agent_action(self.agent_id, message.payload)

        elif message.type == MessageType.ACTION_REQUEST:
            # Handle new unified action request
            if self.agent_id:
                # Check if agent is alive before processing action requests
                agent = self.server.world.get_agent(self.agent_id)
                if agent and not agent.is_alive:
                    # Send error response to dead agents
                    error_response = Message(
                        type=MessageType.ACTION_RESPONSE,
                        payload={
                            "success": False,
                            "error": "Agent is dead and cannot perform actions",
                            "request_id": message.payload.get("request_id")
                        },
                        timestamp=time.time()
                    )
                    await self.send_message(error_response)
                    return

                from shared.actions import ActionRequest
                request = ActionRequest.from_dict(message.payload)
                response = await self.server.action_processor.submit_action(request)

                # Send response back to client
                response_message = Message(
                    type=MessageType.ACTION_RESPONSE,
                    payload=response.to_dict(),
                    timestamp=time.time(),
                )
                await self.send_message(response_message)

        elif message.type == MessageType.ACTION_BATCH:
            # Handle batch action request
            if self.agent_id:
                from shared.actions import ActionBatch
                batch = ActionBatch.from_dict(message.payload)
                responses = await self.server.action_processor.submit_batch(batch)

                # Send batch response back to client
                batch_response_message = Message(
                    type=MessageType.ACTION_BATCH_RESPONSE,
                    payload={"responses": [r.to_dict() for r in responses]},
                    timestamp=time.time(),
                )
                await self.send_message(batch_response_message)

        elif message.type == MessageType.POSITION_QUERY:
            # Handle position query request
            if self.agent_id:
                await self._handle_position_query(message)

        elif message.type == MessageType.ENVIRONMENT_QUERY:
            # Handle environment query request
            if self.agent_id:
                await self._handle_environment_query(message)

        elif message.type == MessageType.DISCONNECT:
            await self.server.disconnect_client(self.client_id)

    async def _handle_position_query(self, message: Message):
        """Handle client request for fresh position data"""
        try:
            # Get the agent's current position from server authority
            agent = self.server.world.get_agent(self.agent_id)
            if not agent:
                error_response = Message(
                    type=MessageType.POSITION_RESPONSE,
                    payload={
                        "success": False,
                        "error": "Agent not found",
                        "query_id": message.payload.get("query_id")
                    },
                    timestamp=time.time()
                )
                await self.send_message(error_response)
                return

            # Get server position authority data if available
            from shared.position_authority import server_position_authority
            server_pos = server_position_authority.get_agent_position(self.agent_id)

            if server_pos:
                position_data = {
                    "x": server_pos.x,
                    "y": server_pos.y,
                    "rotation": server_pos.rotation,
                    "velocity_x": server_pos.velocity_x,
                    "velocity_y": server_pos.velocity_y,
                    "timestamp": server_pos.timestamp
                }
            else:
                # Fallback to agent object data
                position_data = {
                    "x": agent.x,
                    "y": agent.y,
                    "rotation": agent.rotation,
                    "velocity_x": getattr(agent, 'velocity_x', 0.0),
                    "velocity_y": getattr(agent, 'velocity_y', 0.0),
                    "timestamp": time.time()
                }

            # Send position response
            response = Message(
                type=MessageType.POSITION_RESPONSE,
                payload={
                    "success": True,
                    "agent_id": self.agent_id,
                    "position": position_data,
                    "query_id": message.payload.get("query_id"),
                    "server_timestamp": time.time()
                },
                timestamp=time.time()
            )
            await self.send_message(response)

            logger.debug(f"Sent position data to client {self.client_id} for agent {self.agent_id[:8]}: "
                        f"({position_data['x']:.2f}, {position_data['y']:.2f})")

        except Exception as e:
            logger.error(f"Error handling position query for {self.client_id}: {e}")
            error_response = Message(
                type=MessageType.POSITION_RESPONSE,
                payload={
                    "success": False,
                    "error": str(e),
                    "query_id": message.payload.get("query_id")
                },
                timestamp=time.time()
            )
            await self.send_message(error_response)

    async def _handle_environment_query(self, message: Message):
        """Handle client request for environment scan"""
        try:
            agent = self.server.world.get_agent(self.agent_id)
            if not agent:
                error_response = Message(
                    type=MessageType.ENVIRONMENT_RESPONSE,
                    payload={
                        "success": False,
                        "error": "Agent not found",
                        "query_id": message.payload.get("query_id")
                    },
                    timestamp=time.time()
                )
                await self.send_message(error_response)
                return

            # Get scan parameters
            scan_radius = message.payload.get("scan_radius", 5.0)
            scan_radius = min(scan_radius, 10.0)  # Limit scan radius for performance

            # Get agent position
            from shared.position_authority import server_position_authority
            server_pos = server_position_authority.get_agent_position(self.agent_id)
            if server_pos:
                agent_x, agent_y = server_pos.x, server_pos.y
            else:
                agent_x, agent_y = agent.x, agent.y

            # Scan for resources around agent
            resources = []
            search_radius = int(scan_radius) + 1

            for dy in range(-search_radius, search_radius + 1):
                for dx in range(-search_radius, search_radius + 1):
                    check_x = int(agent_x) + dx
                    check_y = int(agent_y) + dy

                    # Check bounds
                    if (0 <= check_x < self.server.world.world_map.width and
                        0 <= check_y < self.server.world.world_map.height):

                        tile_type = self.server.world.world_map.get_tile(check_x, check_y)

                        # Map tile types to resource types
                        resource_type = self._tile_to_resource_type(tile_type)
                        if resource_type:
                            tile_center_x = check_x + 0.5
                            tile_center_y = check_y + 0.5
                            distance = ((tile_center_x - agent_x) ** 2 + (tile_center_y - agent_y) ** 2) ** 0.5

                            if distance <= scan_radius:
                                resources.append({
                                    'type': resource_type,
                                    'tile_type': tile_type.value,
                                    'position': [tile_center_x, tile_center_y],
                                    'tile_coordinates': [check_x, check_y],
                                    'distance': distance
                                })

            # Sort by distance
            resources.sort(key=lambda r: r['distance'])

            # Send environment response
            response = Message(
                type=MessageType.ENVIRONMENT_RESPONSE,
                payload={
                    "success": True,
                    "agent_id": self.agent_id,
                    "agent_position": [agent_x, agent_y],
                    "scan_radius": scan_radius,
                    "resources": resources,
                    "query_id": message.payload.get("query_id"),
                    "server_timestamp": time.time()
                },
                timestamp=time.time()
            )
            await self.send_message(response)

            logger.debug(f"Sent environment data to client {self.client_id} for agent {self.agent_id[:8]}: "
                        f"{len(resources)} resources within {scan_radius} units")

        except Exception as e:
            logger.error(f"Error handling environment query for {self.client_id}: {e}")
            error_response = Message(
                type=MessageType.ENVIRONMENT_RESPONSE,
                payload={
                    "success": False,
                    "error": str(e),
                    "query_id": message.payload.get("query_id")
                },
                timestamp=time.time()
            )
            await self.send_message(error_response)

    def _tile_to_resource_type(self, tile_type):
        """Convert tile type to resource type string"""
        from world.tiles import TileType
        mapping = {
            TileType.WATER: "water",
            TileType.WOOD: "wood",
            TileType.STONE: "stone",
        }
        return mapping.get(tile_type)

    async def send_message(self, message: Message):
        try:
            data = message.to_json() + "\n"
            self.writer.write(data.encode())
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Failed to send message to {self.client_id}: {e}")
