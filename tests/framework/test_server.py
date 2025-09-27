"""
Lightweight In-Process Test Server

Provides a real game server that runs in-process for integration tests.
Uses real physics, pathfinding, and collision detection while being
optimized for fast test execution.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from server.server import GameServer
from server.world import ServerWorld
from server.action_processor import ActionProcessor
from server.agent_state import AgentRegistry
from server.attack_system import AttackSystem
from client.client import GameClient
from world.map import WorldMap
from world.tiles import TileType
from shared.collision import CollisionDetector


@dataclass
class ServerConfig:
    """Configuration for test server"""
    world_width: int = 20
    world_height: int = 20
    tick_rate: float = 20.0  # Server ticks per second
    time_acceleration: float = 1.0  # How fast time runs (1.0 = real time)
    log_level: str = "WARNING"  # Reduce logging noise in tests
    enable_database: bool = False  # Disable DB for faster tests
    max_agents: int = 50


class GameServer:
    """
    Lightweight game server optimized for integration testing.

    Features:
    - Runs in-process (no network setup required)
    - Real game physics and validation
    - Accelerated time for fast test execution
    - Minimal logging to reduce test noise
    - Optional database integration
    """

    def __init__(self, config: ServerConfig = None):
        self.config = config or ServerConfig()
        self.server: Optional[GameServer] = None
        self.world: Optional[ServerWorld] = None
        self.action_processor: Optional[ActionProcessor] = None
        self.agent_registry: Optional[AgentRegistry] = None
        self.attack_system: Optional[AttackSystem] = None
        self.running = False

        # Set up test logging
        logging.getLogger("server").setLevel(getattr(logging, self.config.log_level))
        logging.getLogger("client").setLevel(getattr(logging, self.config.log_level))

    async def start(self, world_map: Optional[WorldMap] = None) -> None:
        """Start the test server with optional custom world map"""
        if self.running:
            return

        # Create world map if not provided
        if world_map is None:
            world_map = self._create_default_world_map()

        # Create collision detector
        collision_detector = CollisionDetector(
            self.config.world_width,
            self.config.world_height
        )

        # Create server world
        self.world = ServerWorld(
            width=world_map.width,
            height=world_map.height,
            use_perlin=False
        )
        # Replace the generated world_map with our custom one
        self.world.world_map = world_map

        # Create subsystems
        self.agent_registry = AgentRegistry()
        self.attack_system = AttackSystem()

        # Create action processor
        self.action_processor = ActionProcessor(self.world, self.agent_registry, self.attack_system)

        # Create and configure server
        self.server = GameServer(
            self.config.world_width,
            self.config.world_height
        )

        # Override server components with our test versions
        self.server.world = self.world
        self.server.agent_registry = self.agent_registry
        self.server.action_processor = self.action_processor
        self.server.attack_system = self.attack_system

        # Start server (without network binding for tests)
        await self._start_test_server()
        self.running = True

    async def stop(self) -> None:
        """Stop the test server"""
        if not self.running:
            return

        if self.server:
            await self.server.stop()

        self.running = False

    def _create_default_world_map(self) -> WorldMap:
        """Create default world map for testing"""
        world_map = WorldMap(self.config.world_width, self.config.world_height)

        # Fill with grass
        for x in range(self.config.world_width):
            for y in range(self.config.world_height):
                world_map.set_tile(x, y, TileType.GRASS)

        return world_map

    async def _start_test_server(self):
        """Start server without network components for testing"""
        # Initialize server components without network setup
        if hasattr(self.server, '_initialize_subsystems'):
            await self.server._initialize_subsystems()

        # Start update loop with accelerated time
        self._update_task = asyncio.create_task(self._test_update_loop())

    async def _test_update_loop(self):
        """Test-optimized update loop with time acceleration"""
        dt = 1.0 / self.config.tick_rate
        accelerated_dt = dt * self.config.time_acceleration

        while self.running:
            try:
                # Update server with accelerated time
                if self.world:
                    # Update agent positions and behaviors
                    for agent in self.world.get_all_agents():
                        if hasattr(agent, 'update'):
                            agent.update(accelerated_dt)

                # Process any pending actions
                if self.action_processor:
                    await self.action_processor.process_pending_actions()

                # Sleep for real time to maintain tick rate
                await asyncio.sleep(dt / self.config.time_acceleration)

            except Exception as e:
                logging.error(f"Test server update error: {e}")
                break

    def create_test_client(self, agent_type: str = "player") -> 'GameClient':
        """Create a test client connected to this server"""
        return GameClient(self, agent_type)

    def spawn_agent(self, agent_type: str, x: float, y: float, agent_id: str = None) -> str:
        """Spawn agent directly in the server world"""
        if not self.world:
            raise RuntimeError("Server not started")

        agent_id = self.world.spawn_agent(agent_type, x, y, agent_id)
        if self.agent_registry:
            self.agent_registry.register_agent(agent_id, agent_type, x, y)

        return agent_id

    def get_agent_position(self, agent_id: str) -> Optional[tuple]:
        """Get agent position from server"""
        if not self.world:
            return None

        agent = self.world.get_agent(agent_id)
        if agent:
            return (agent.x, agent.y)
        return None

    def move_agent(self, agent_id: str, x: float, y: float) -> bool:
        """Move agent to specific position (for test setup)"""
        if not self.world:
            return False

        return self.world.move_agent(agent_id, x, y, 0)

    async def process_action(self, action_request) -> Any:
        """Process action request directly"""
        if not self.action_processor:
            raise RuntimeError("Server not started")

        return await self.action_processor.submit_action(action_request)

    def set_world_map(self, world_map: WorldMap):
        """Update the world map (for dynamic test scenarios)"""
        if self.world:
            self.world.world_map = world_map


class GameClient:
    """
    Test client that connects to GameServer in-process.
    Provides real client behavior without network overhead.
    """

    def __init__(self, test_server: GameServer, agent_type: str = "player"):
        self.test_server = test_server
        self.agent_type = agent_type
        self.agent_id: Optional[str] = None
        self.agent = None
        self.connected = False

    async def connect(self, spawn_x: float = 10.0, spawn_y: float = 10.0) -> bool:
        """Connect to test server and spawn agent"""
        if not self.test_server.running:
            return False

        try:
            # Spawn agent on server
            self.agent_id = self.test_server.spawn_agent(
                self.agent_type, spawn_x, spawn_y
            )

            # Create client-side agent
            self._create_client_agent(spawn_x, spawn_y)

            self.connected = True
            return True

        except Exception as e:
            logging.error(f"Test client connection failed: {e}")
            return False

    def _create_client_agent(self, x: float, y: float):
        """Create client-side agent instance"""
        from client.agent_types.player import PlayerAgent
        from client.agent_types.explorer import ExplorerAgent
        from client.agent_types.enemy import EnemyAgent

        if self.agent_type == "player":
            self.agent = PlayerAgent(self.agent_id, x, y)
        elif self.agent_type == "explorer":
            self.agent = ExplorerAgent(self.agent_id, x, y)
        elif self.agent_type == "enemy":
            self.agent = EnemyAgent(self.agent_id, x, y)
        else:
            self.agent = PlayerAgent(self.agent_id, x, y)

        # Set up agent for test environment
        self.agent.set_world_bounds(
            self.test_server.config.world_width,
            self.test_server.config.world_height
        )
        self.agent.has_initial_map_data = True
        self.agent.use_behavior_tree = True

        # Create action manager that communicates with test server
        self.agent.action_manager = ClientActionManager(
            self.test_server, self.agent_id
        )

        # Initialize behavior tree
        if hasattr(self.agent, '_initialize_behavior_tree'):
            if not getattr(self.agent, 'behavior_tree_initialized', True):
                self.agent._initialize_behavior_tree()

    async def disconnect(self):
        """Disconnect from test server"""
        self.connected = False
        # Agent will be cleaned up by server

    def update(self, delta_time: float):
        """Update client-side agent"""
        if self.agent and self.connected:
            self.agent.update(delta_time)

            # Sync position with server
            server_pos = self.test_server.get_agent_position(self.agent_id)
            if server_pos:
                self.agent.x, self.agent.y = server_pos


class ClientActionManager:
    """Action manager for test clients that communicates with GameServer"""

    def __init__(self, test_server: GameServer, agent_id: str):
        self.test_server = test_server
        self.agent_id = agent_id
        self.callbacks = {}

    async def request_action(self, action_type, parameters: Dict[str, Any],
                           priority=None, predict: bool = True) -> str:
        """Send action request to test server"""
        from shared.actions import ActionRequest
        import uuid

        action_id = str(uuid.uuid4())

        request = ActionRequest(
            action_id=action_id,
            agent_id=self.agent_id,
            action_type=action_type,
            parameters=parameters
        )

        # Process action on server
        response = await self.test_server.process_action(request)

        # Call registered callback if any
        if action_type in self.callbacks:
            self.callbacks[action_type](request, response, None)

        return action_id

    def register_action_callback(self, action_type, callback):
        """Register callback for action responses"""
        self.callbacks[action_type] = callback


# Convenience functions for integration testing

async def create_test_environment(config: ServerConfig = None,
                                world_builder=None) -> GameServer:
    """Create complete test environment with server and world"""
    server = GameServer(config)

    if world_builder:
        # Use custom world from builder (no terrain generation)
        world_map = WorldMap(world_builder.width, world_builder.height, use_perlin=False)
        for (x, y), tile_type in world_builder.terrain.items():
            world_map.set_tile(x, y, tile_type)
        await server.start(world_map)

        # Spawn agents from builder
        for agent_type, x, y in world_builder.agent_spawns:
            server.spawn_agent(agent_type, x, y)
    else:
        await server.start()

    return server


async def create_client_server_test(agent_types: List[str],
                                   world_builder=None) -> tuple[GameServer, List[GameClient]]:
    """Create server with multiple test clients"""
    server = await create_test_environment(world_builder=world_builder)

    clients = []
    for i, agent_type in enumerate(agent_types):
        client = server.create_test_client(agent_type)
        # Spread agents across the world
        spawn_x = 5.0 + (i * 3.0)
        spawn_y = 5.0 + (i * 2.0)
        await client.connect(spawn_x, spawn_y)
        clients.append(client)

    return server, clients


class IntegrationTestContext:
    """Context manager for integration tests with automatic cleanup"""

    def __init__(self, config: ServerConfig = None, world_builder=None):
        self.config = config
        self.world_builder = world_builder
        self.server: Optional[GameServer] = None
        self.clients: List[GameClient] = []

    async def __aenter__(self):
        self.server = await create_test_environment(self.config, self.world_builder)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Disconnect all clients
        for client in self.clients:
            await client.disconnect()

        # Stop server
        if self.server:
            await self.server.stop()

    async def add_client(self, agent_type: str, x: float = 10.0, y: float = 10.0) -> GameClient:
        """Add client to test environment"""
        if not self.server:
            raise RuntimeError("Server not started")

        client = self.server.create_test_client(agent_type)
        await client.connect(x, y)
        self.clients.append(client)
        return client