import asyncio
import json
import logging
import socket
import time
from typing import Any, Dict, Optional

from client.agent import BaseAgent
from client.agent_types.enemy import EnemyAgent
from client.agent_types.explorer import ExplorerAgent
from client.agent_types.npc import NPCAgent
from client.agent_types.pathfinding_test import PathfindingTestAgent
from client.agent_types.personality_agent import PersonalityAgent
from client.agent_types.player import PlayerAgent
from client.thin_agent import ThinBaseAgent, create_thin_agent
from shared.constants import SERVER_PORT, UDP_PORT
from shared.messages import Message, MessageType
from shared.position_authority import client_position_interpolator

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

        # Server game data (received from server)
        self.server_game_data = None

        # Behavior tree provider for dependency injection
        self.behavior_tree_provider: Optional["BehaviorTreeProvider"] = None

        # Query callback management
        self._position_query_callbacks = {}
        self._environment_query_callbacks = {}
        self._query_sequence = 0

    def set_behavior_tree_provider(self, provider: Optional["BehaviorTreeProvider"]):
        """Set behavior tree provider for agent dependency injection."""
        self.behavior_tree_provider = provider

    async def connect(self, host: str = "127.0.0.1", agent_type: str = "player"):
        try:
            self.tcp_reader, self.tcp_writer = await asyncio.open_connection(
                host, SERVER_PORT
            )

            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setblocking(False)

            connect_msg = Message(
                type=MessageType.CONNECT,
                payload={"agent_type": agent_type},
                timestamp=time.time(),
            )
            await self.send_tcp_message(connect_msg)

            response = await self.receive_tcp_message()
            if response and response.type == MessageType.SPAWN_AGENT:
                self.agent_id = response.payload["agent_id"]
                self.client_id = response.payload.get(
                    "client_id", self.agent_id
                )  # Get client_id from server
                spawn_x = response.payload.get("x", 50)
                spawn_y = response.payload.get("y", 50)
                spawn_rotation = response.payload.get("rotation", 0)

                # Store server game data for agent decision-making
                self.server_game_data = response.payload.get("attack_data", {})
                self.exploration_mode = response.payload.get(
                    "exploration_mode", "frontier"
                )

                # Store personality configuration if provided by scenario
                self.personality_config = response.payload.get("personality_config")
                if self.personality_config:
                    logger.info(
                        f"[CLIENT] Received personality config for {self.personality_config.get('archetype', 'custom')} agent"
                    )

                logger.info(
                    f"[CLIENT] Received game data: {len(self.server_game_data.get('attacks', {}))} attacks"
                )

                self.connected = True
                logger.info(f"Connected as agent {self.agent_id}")

                self.create_agent(agent_type, spawn_x, spawn_y, spawn_rotation)

                return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def create_agent(
        self, agent_type: str, x: float = 50, y: float = 50, rotation: float = 0
    ):
        # Check if we have personality data from scenario
        personality_config = getattr(self, "personality_config", None)

        if personality_config and "personality" in personality_config:
            # Create personality agent with scenario-provided personality
            # Deserialize personality from dict
            from shared.personality import Personality

            personality_dict = personality_config["personality"]
            personality = Personality.from_dict(personality_dict)

            logger.info(
                f"Creating PersonalityAgent with {personality_config.get('archetype', 'custom')} personality"
            )
            self.agent = PersonalityAgent(self.agent_id, x, y, personality)
        else:
            # Fallback to legacy agents for backward compatibility
            logger.info(f"Creating legacy {agent_type} agent (no personality data)")
            if agent_type == "player":
                self.agent = PlayerAgent(self.agent_id, x, y)
            elif agent_type == "npc":
                self.agent = NPCAgent(self.agent_id, x, y)
            elif agent_type == "enemy":
                self.agent = EnemyAgent(self.agent_id, x, y)
            elif agent_type == "explorer":
                self.agent = ExplorerAgent(self.agent_id, x, y)
                # Pass exploration mode if available
                if hasattr(self, "exploration_mode"):
                    self.agent.exploration_mode = self.exploration_mode
            elif agent_type == "pathfinding_test":
                # For pathfinding test, use the test agent with predefined waypoints
                test_waypoints = [
                    (10, 10),
                    (90, 10),
                    (90, 90),
                    (10, 90),
                    (50, 50),
                    (10, 10),
                ]
                self.agent = PathfindingTestAgent(self.agent_id, x, y, test_waypoints)
                # Ensure agent uses the actual spawn position
                self.agent.x = x
                self.agent.y = y

        logger.info(
            f"[CLIENT] Created {agent_type} agent {self.agent_id[:8]} with behavior tree"
        )

        if self.agent:
            self.agent.rotation = rotation

            # Give agent a reference to its client for server queries
            self.agent.client = self

            # Inject behavior tree provider before anything else
            if self.behavior_tree_provider:
                self.agent.set_behavior_tree_provider(self.behavior_tree_provider)
                logger.info(
                    f"[CLIENT] Injected behavior tree provider into agent {self.agent_id[:8]}"
                )

            # Provide server game data to agent
            if self.server_game_data:
                if hasattr(self.agent, "set_server_game_data"):
                    self.agent.set_server_game_data(self.server_game_data)
                    logger.info(
                        f"[CLIENT] Provided server game data to agent {self.agent_id[:8]}"
                    )

            # Initialize behavior tree now that provider is injected (for agents that deferred initialization)
            if (
                hasattr(self.agent, "behavior_tree_initialized")
                and not self.agent.behavior_tree_initialized
            ):
                if hasattr(self.agent, "_initialize_behavior_tree"):
                    self.agent._initialize_behavior_tree()
                    logger.info(
                        f"[CLIENT] Manually initialized behavior tree for agent {self.agent_id[:8]} after provider injection"
                    )

            # Set default world bounds immediately so pathfinding can work
            # These will be updated with actual bounds when world state arrives
            self.agent.set_world_bounds(100, 100)

            # Initialize action manager for new request-response system
            from client.action_manager import ActionManager

            self.agent.action_manager = ActionManager(
                agent_id=self.agent_id,
                send_message_callback=self.send_tcp_message,
            )
            logger.info(
                f"[CLIENT] Initialized action manager for agent {self.agent_id[:8]}"
            )

            # Initialize position reconciliation system to fix sync issues
            self.agent._initialize_position_reconciler()
            logger.info(
                f"[CLIENT] Initialized position reconciler for agent {self.agent_id[:8]}"
            )

            # Initialize movement validation system to prevent conflicts
            self.agent._initialize_movement_validator()
            logger.info(
                f"[CLIENT] Initialized movement validator for agent {self.agent_id[:8]}"
            )

    async def send_tcp_message(self, message: Message):
        if self.tcp_writer:
            data = message.to_json() + "\n"
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

    def send_udp_message(self, data: dict, host: str = "127.0.0.1"):
        if self.udp_socket and self.client_id:
            data["client_id"] = self.client_id
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
                self.visible_entities = message.payload.get("entities", [])
                terrain_dict = message.payload.get("terrain", {})

                # Debug: Log received visibility data (reduced verbosity)
                logger.debug(
                    f"[VISIBILITY] Agent {self.agent_id[:8]} received {len(self.visible_entities)} visible entities"
                )
                if len(self.visible_entities) > 0:
                    enemy_count = sum(
                        1
                        for e in self.visible_entities
                        if e.get("agent_type") != getattr(self.agent, "agent_type", "")
                    )
                    logger.debug(
                        f"[VISIBILITY] - Including {enemy_count} potential targets"
                    )

                # Convert terrain data back to usable format
                terrain_data = {}
                for coord_str, tile_value in terrain_dict.items():
                    x_str, y_str = coord_str.split(",")
                    x, y = int(x_str), int(y_str)
                    # Import TileType here to avoid circular imports
                    from world.tiles import TileType

                    tile_type = TileType(tile_value)
                    terrain_data[(x, y)] = tile_type

                if self.agent:
                    # Update agent's personal map with discovered terrain
                    self.agent.discover_terrain_from_vision(terrain_data)
                    self.agent.perceive(self.visible_entities)

            elif message.type == MessageType.DAMAGE_DEALT:
                target_id = message.payload.get("target_id")
                damage = message.payload.get("damage")
                new_health = message.payload.get("new_health")

                if self.agent and target_id == self.agent_id:
                    self.agent.health = new_health
                    logger.info(
                        f"[DAMAGE RECEIVED] Agent {self.agent_id[:8]} took "
                        f"{damage} damage, health now {new_health}"
                    )

            elif message.type == MessageType.AGENT_DEATH:
                dead_agent_id = message.payload.get("dead_agent_id")

                if self.agent and dead_agent_id == self.agent_id:
                    self.agent.health = 0
                    self.agent.is_alive = False
                    logger.info(f"[DEATH] Agent {self.agent_id[:8]} has died")

            elif message.type == MessageType.ACTION_RESPONSE:
                # Handle action response from new action system
                if self.agent and self.agent.action_manager:
                    from shared.actions import ActionResponse

                    response = ActionResponse.from_dict(message.payload)
                    await self.agent.action_manager.handle_response(response)
                    logger.debug(
                        f"[ACTION] Processed response for action {response.action_id}: {response.result.value}"
                    )

            elif message.type == MessageType.ACTION_BATCH_RESPONSE:
                # Handle batch action response from new action system
                if self.agent and self.agent.action_manager:
                    from shared.actions import ActionResponse

                    responses = [
                        ActionResponse.from_dict(r)
                        for r in message.payload.get("responses", [])
                    ]
                    await self.agent.action_manager.handle_batch_response(responses)
                    logger.debug(
                        f"[ACTION] Processed batch response with {len(responses)} actions"
                    )

            elif message.type == MessageType.AGENT_RESPAWN:
                agent_id = message.payload.get("agent_id")
                respawn_x = message.payload.get("x")
                respawn_y = message.payload.get("y")

                if self.agent and agent_id == self.agent_id:
                    self.agent.x = respawn_x
                    self.agent.y = respawn_y
                    self.agent.health = getattr(self.agent, "max_health", 100)
                    self.agent.is_alive = True

                    # Reset behavior tree to clear any stuck states
                    if (
                        hasattr(self.agent, "behavior_tree")
                        and self.agent.behavior_tree
                    ):
                        self.agent.behavior_tree.reset()
                        logger.debug(
                            f"[RESPAWN] Reset behavior tree for agent {self.agent_id[:8]}"
                        )

                    # Reset movement state
                    self.agent.velocity_x = 0
                    self.agent.velocity_y = 0

                    logger.info(
                        f"[RESPAWN] Agent {self.agent_id[:8]} respawned at "
                        f"({respawn_x:.1f}, {respawn_y:.1f})"
                    )

            elif message.type == MessageType.POSITION_SYNC:
                # Handle server position synchronization
                positions_data = message.payload.get("positions", {})
                server_timestamp = message.payload.get("server_timestamp", time.time())

                logger.debug(
                    f"[POSITION_SYNC] Received sync for {len(positions_data)} agents"
                )

                # Update position interpolator with server data
                for agent_id, pos_data in positions_data.items():
                    client_position_interpolator.update_server_position(
                        agent_id, pos_data
                    )

                # Update our own agent's server position if included
                if self.agent and self.agent_id in positions_data:
                    server_pos = client_position_interpolator.get_server_position(
                        self.agent_id
                    )
                    if server_pos:
                        # Store server position for action validation
                        (
                            self.agent.server_x,
                            self.agent.server_y,
                            self.agent.server_rotation,
                        ) = server_pos

                        # Update logical position used by behavior tree (non-interpolated)
                        self.agent.x, self.agent.y, self.agent.rotation = server_pos

                        logger.debug(
                            f"[POSITION_SYNC] Updated server position for {self.agent_id[:8]}: "
                            f"({server_pos[0]:.2f}, {server_pos[1]:.2f})"
                        )

            elif message.type == MessageType.POSITION_RESPONSE:
                # Handle position query response
                if hasattr(self, "_position_query_callbacks"):
                    query_id = message.payload.get("query_id")
                    if query_id in self._position_query_callbacks:
                        callback = self._position_query_callbacks.pop(query_id)
                        try:
                            callback(message.payload)
                        except Exception as e:
                            logger.error(f"Error in position query callback: {e}")

            elif message.type == MessageType.ENVIRONMENT_RESPONSE:
                # Handle environment query response
                if hasattr(self, "_environment_query_callbacks"):
                    query_id = message.payload.get("query_id")
                    if query_id in self._environment_query_callbacks:
                        callback = self._environment_query_callbacks.pop(query_id)
                        try:
                            callback(message.payload)
                        except Exception as e:
                            logger.error(f"Error in environment query callback: {e}")

    def update_agent_from_world_state(self):
        if not self.agent or not self.agent_id:
            return

        # Set world bounds if available
        map_info = self.world_state.get("map_info")
        if map_info and not self.agent.world_bounds:
            width = map_info.get("width")
            height = map_info.get("height")
            if width and height:
                self.agent.set_world_bounds(width, height)

        agents = self.world_state.get("agents", [])
        for agent_data in agents:
            if agent_data.get("id") == self.agent_id:
                # Update non-position data from world state
                # Position is managed by position sync system
                position_backup = (self.agent.x, self.agent.y, self.agent.rotation)
                self.agent.update_from_state(agent_data)

                # Restore server authoritative position if we have it
                if hasattr(self.agent, "server_x") and self.agent.server_x is not None:
                    self.agent.x, self.agent.y, self.agent.rotation = position_backup
                    logger.debug(
                        f"[WORLD_STATE] Preserved server position over world state for {self.agent_id[:8]}"
                    )
                break

    async def update_agent(self):
        if not self.agent:
            return

        # Ensure agent has latest visibility data before each update
        # Initialize empty list if not yet received
        if not hasattr(self, "visible_entities"):
            self.visible_entities = []

        self.agent.perceive(self.visible_entities)

        delta_time = 0.016

        # Update position interpolation
        client_position_interpolator.interpolate_positions(delta_time)

        # Update display position for our agent if server data is available
        if self.agent_id:
            display_pos = client_position_interpolator.get_display_position(
                self.agent_id
            )
            if display_pos:
                # Use interpolated position for smooth visual display
                (
                    self.agent.display_x,
                    self.agent.display_y,
                    self.agent.display_rotation,
                ) = display_pos

        self.agent.update(delta_time)

        action = self.agent.decide()
        if action:
            await self.send_action(action)

        # Send any pending actions (like damage)
        if hasattr(self.agent, "pending_actions") and self.agent.pending_actions:
            for pending_action in self.agent.pending_actions:
                await self.send_action(pending_action)
            self.agent.pending_actions.clear()

        if abs(self.agent.velocity_x) > 0.01 or abs(self.agent.velocity_y) > 0.01:
            self.send_udp_message(
                {
                    "type": "move",
                    "x": self.agent.x,
                    "y": self.agent.y,
                    "rotation": self.agent.rotation,
                }
            )

    async def send_action(self, action: Dict[str, Any]):
        message = Message(
            type=MessageType.AGENT_ACTION, payload=action, timestamp=time.time()
        )
        await self.send_tcp_message(message)

    async def query_position(self, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Query the server for fresh position data.

        Args:
            timeout: Maximum time to wait for response

        Returns:
            Position data dict or None if query failed
        """
        if not self.connected or not self.agent_id:
            return None

        # Generate unique query ID
        self._query_sequence += 1
        query_id = f"pos_{self.agent_id[:8]}_{self._query_sequence}"

        # Set up response callback
        response_future = asyncio.Future()

        def callback(response_data):
            if not response_future.done():
                response_future.set_result(response_data)

        self._position_query_callbacks[query_id] = callback

        # Send query
        message = Message(
            type=MessageType.POSITION_QUERY,
            payload={
                "agent_id": self.agent_id,
                "query_id": query_id,
                "timestamp": time.time(),
            },
            timestamp=time.time(),
        )

        try:
            await self.send_tcp_message(message)

            # Wait for response
            response_data = await asyncio.wait_for(response_future, timeout=timeout)

            if response_data.get("success"):
                logger.debug(
                    f"Received position query response for {self.agent_id[:8]}"
                )
                return response_data
            else:
                logger.warning(
                    f"Position query failed for {self.agent_id[:8]}: {response_data.get('error')}"
                )
                return None

        except asyncio.TimeoutError:
            logger.warning(f"Position query timeout for {self.agent_id[:8]}")
            # Clean up callback
            self._position_query_callbacks.pop(query_id, None)
            return None
        except Exception as e:
            logger.error(f"Position query error for {self.agent_id[:8]}: {e}")
            # Clean up callback
            self._position_query_callbacks.pop(query_id, None)
            return None

    async def query_environment(
        self, scan_radius: float = 5.0, timeout: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """
        Query the server for environment data around the agent.

        Args:
            scan_radius: Radius to scan around agent
            timeout: Maximum time to wait for response

        Returns:
            Environment data dict or None if query failed
        """
        if not self.connected or not self.agent_id:
            return None

        # Generate unique query ID
        self._query_sequence += 1
        query_id = f"env_{self.agent_id[:8]}_{self._query_sequence}"

        # Set up response callback
        response_future = asyncio.Future()

        def callback(response_data):
            if not response_future.done():
                response_future.set_result(response_data)

        self._environment_query_callbacks[query_id] = callback

        # Send query
        message = Message(
            type=MessageType.ENVIRONMENT_QUERY,
            payload={
                "agent_id": self.agent_id,
                "scan_radius": scan_radius,
                "query_id": query_id,
                "timestamp": time.time(),
            },
            timestamp=time.time(),
        )

        try:
            await self.send_tcp_message(message)

            # Wait for response
            response_data = await asyncio.wait_for(response_future, timeout=timeout)

            if response_data.get("success"):
                logger.debug(
                    f"Received environment query response for {self.agent_id[:8]}: "
                    f"{len(response_data.get('resources', []))} resources found"
                )
                return response_data
            else:
                logger.warning(
                    f"Environment query failed for {self.agent_id[:8]}: {response_data.get('error')}"
                )
                return None

        except asyncio.TimeoutError:
            logger.warning(f"Environment query timeout for {self.agent_id[:8]}")
            # Clean up callback
            self._environment_query_callbacks.pop(query_id, None)
            return None
        except Exception as e:
            logger.error(f"Environment query error for {self.agent_id[:8]}: {e}")
            # Clean up callback
            self._environment_query_callbacks.pop(query_id, None)
            return None

    async def move_to(self, x: float, y: float):
        if self.agent and isinstance(self.agent, PlayerAgent):
            # Validate movement through position reconciler
            if self.agent.position_reconciler:
                is_valid, reason = self.agent.position_reconciler.validate_movement(
                    x, y
                )
                if not is_valid:
                    logger.warning(
                        f"[CLIENT] Movement validation failed for agent {self.agent_id[:8]}: {reason}"
                    )
                    return

            self.agent.handle_input("move_to", {"x": x, "y": y})

            message = Message(
                type=MessageType.MOVE_COMMAND,
                payload={"x": x, "y": y, "rotation": self.agent.rotation},
                timestamp=time.time(),
            )
            await self.send_tcp_message(message)

    async def disconnect(self):
        if self.connected:
            disconnect_msg = Message(
                type=MessageType.DISCONNECT, payload={}, timestamp=time.time()
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
