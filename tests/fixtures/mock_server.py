"""
Lightweight mock server components for fast unit testing.

These mocks provide the minimal interface needed for testing without
the overhead of full server startup.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from unittest.mock import MagicMock

from shared.messages import AgentData, Message, MessageType
from shared.actions import ActionResponse, ActionResult, ActionType
from world.tiles import TileType


class MockWorld:
    """Lightweight mock world for testing"""

    def __init__(self, width: int = 20, height: int = 20):
        self.width = width
        self.height = height
        self.agents: Dict[str, AgentData] = {}
        self.terrain = {}

        # Default terrain - all grass for simplicity
        for y in range(height):
            for x in range(width):
                self.terrain[(x, y)] = TileType.GRASS

        # Mock world_map for compatibility
        self.world_map = MagicMock()
        self.world_map.width = width
        self.world_map.height = height
        self.world_map.is_walkable.return_value = True
        self.world_map.get_bounds.return_value = (width, height)

    def spawn_agent(self, agent_type: str, x: float = 10, y: float = 10) -> str:
        """Spawn agent at specified position"""
        import uuid
        agent_id = str(uuid.uuid4())

        agent = AgentData(
            id=agent_id,
            x=x, y=y,
            rotation=0.0,
            agent_type=agent_type,
            health=100.0,
            vision_range=10.0
        )

        self.agents[agent_id] = agent
        return agent_id

    def get_agent(self, agent_id: str) -> Optional[AgentData]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> List[AgentData]:
        return list(self.agents.values())

    def move_agent(self, agent_id: str, x: float, y: float, rotation: float = 0, **kwargs) -> bool:
        """Move agent to new position"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            # Check if position is valid and walkable
            if self.validate_position(x, y):
                agent.x = x
                agent.y = y
                agent.rotation = rotation
                return True
        return False

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if position is walkable"""
        tile_type = self.terrain.get((x, y), TileType.GRASS)
        # Import here to avoid circular imports
        from world.tiles import TILE_PROPERTIES
        return TILE_PROPERTIES[tile_type].walkable

    def find_nearest_walkable_position(self, x: float, y: float) -> tuple:
        """Find nearest walkable position - just return the input for mocking"""
        return (x, y)

    def get_visible_agents(self, agent_id: str, vision_range: float = 10.0) -> List[AgentData]:
        """Get agents visible to specified agent"""
        if agent_id not in self.agents:
            return []

        observer = self.agents[agent_id]
        visible = []

        for other_id, other_agent in self.agents.items():
            if other_id == agent_id or not other_agent.is_alive:
                continue

            # Simple distance check
            dist = ((other_agent.x - observer.x) ** 2 + (other_agent.y - observer.y) ** 2) ** 0.5
            if dist <= vision_range:
                visible.append(other_agent)

        return visible

    def validate_position(self, x: float, y: float) -> bool:
        """Validate that a position is on walkable terrain"""
        # Check bounds first
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False

        # Check tile walkability
        tile_x, tile_y = int(x), int(y)
        return self.is_walkable(tile_x, tile_y)


class MockActionProcessor:
    """Mock action processor for testing"""

    def __init__(self):
        self.processed_actions = []
        self.responses = {}

    async def submit_action(self, request):
        """Mock action submission - always succeeds quickly"""
        from shared.actions import ActionResponse, ActionResult

        self.processed_actions.append(request)

        # Simulate fast processing
        await asyncio.sleep(0.01)

        response = ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message="Mock action approved",
            processing_time_ms=10.0
        )

        return response

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_processed": len(self.processed_actions),
            "total_approved": len(self.processed_actions),
            "total_rejected": 0
        }


class MockAgentRegistry:
    """Mock agent registry for testing"""

    def __init__(self):
        self.agents = {}

    def register_agent(self, agent_id: str, agent_type: str, x: float, y: float):
        from server.agent_state import ServerAgentState
        self.agents[agent_id] = ServerAgentState(agent_id, agent_type, position=(x, y))

    def get_agent(self, agent_id: str):
        return self.agents.get(agent_id)

    def assign_agent_to_client(self, agent_id: str, client_id: str):
        if agent_id in self.agents:
            self.agents[agent_id].client_id = client_id


class MockGameServer:
    """Lightweight mock server for testing"""

    def __init__(self, width: int = 20, height: int = 20):
        self.world = MockWorld(width, height)
        self.action_processor = MockActionProcessor()
        self.agent_registry = MockAgentRegistry()
        self.attack_system = MagicMock()  # Mock attack system
        self.clients = {}

        # Track messages for testing
        self.sent_messages = []

    async def process_agent_action(self, agent_id: str, action_data: Dict[str, Any]):
        """Mock action processing"""
        # Just track that action was processed
        self.sent_messages.append({
            'type': 'agent_action',
            'agent_id': agent_id,
            'data': action_data
        })

    async def broadcast_damage_event(self, attacker_id: str, target_id: str, damage: float, new_health: float):
        """Mock damage broadcast"""
        self.sent_messages.append({
            'type': 'damage_event',
            'attacker_id': attacker_id,
            'target_id': target_id,
            'damage': damage,
            'new_health': new_health
        })

    def get_message_count(self, message_type: str) -> int:
        """Get count of messages of specific type"""
        return len([m for m in self.sent_messages if m['type'] == message_type])


class MockActionManager:
    """Mock action manager for testing"""

    def __init__(self, client):
        self.client = client
        self.pending_actions = {}
        self.callbacks = {}

    async def request_action(self, action_type: ActionType, parameters: Dict[str, Any],
                           priority=None, predict: bool = True) -> str:
        """Mock action request - simulates successful movement"""
        import uuid
        action_id = str(uuid.uuid4())

        # For MOVE_TO actions, simulate the movement in the mock world
        if action_type == ActionType.MOVE_TO:
            target_x = parameters.get("target_x", self.client.agent.x)
            target_y = parameters.get("target_y", self.client.agent.y)

            # Simulate successful movement for test purposes
            self.client.agent.x = target_x
            self.client.agent.y = target_y

            # Create success response
            response = ActionResponse(
                action_id=action_id,
                agent_id=self.client.agent_id,
                action_type=action_type,
                result=ActionResult.APPROVED,
                message="Movement successful"
            )
        else:
            # Default successful response for other actions
            response = ActionResponse(
                action_id=action_id,
                agent_id=self.client.agent_id,
                action_type=action_type,
                result=ActionResult.APPROVED,
                message="Action successful"
            )

        # Simulate callback
        if action_type in self.callbacks:
            # Create mock request
            from shared.actions import ActionRequest
            request = ActionRequest(
                action_id=action_id,
                agent_id=self.client.agent_id,
                action_type=action_type,
                parameters=parameters
            )

            # Call registered callback
            self.callbacks[action_type](request, response, None)

        return action_id

    def register_action_callback(self, action_type: ActionType, callback):
        """Register callback for action responses"""
        self.callbacks[action_type] = callback


class MockClient:
    """Mock client for testing"""

    def __init__(self, agent_type: str = "player"):
        self.agent_id = None
        self.client_id = None
        self.agent_type = agent_type
        self.connected = False
        self.sent_messages = []
        self.received_messages = []

    def create_agent(self, agent_id: str, x: float = 10, y: float = 10):
        """Create mock agent"""
        from client.agent_types.player import PlayerAgent
        from client.agent_types.explorer import ExplorerAgent
        from client.agent_types.enemy import EnemyAgent

        self.agent_id = agent_id

        if self.agent_type == "player":
            self.agent = PlayerAgent(agent_id, x, y)
        elif self.agent_type == "explorer":
            self.agent = ExplorerAgent(agent_id, x, y)
            # Initialize explorer behavior tree
            self.agent.set_exploration_mode("frontier")
        elif self.agent_type == "enemy":
            self.agent = EnemyAgent(agent_id, x, y)
        else:
            # Generic agent
            from client.agent_types.player import PlayerAgent
            self.agent = PlayerAgent(agent_id, x, y)

        # Set up basic world bounds
        self.agent.set_world_bounds(20, 20)

        # Set up collision detection for water avoidance
        from shared.collision import CollisionDetector
        self.agent.collision_detector = CollisionDetector(20, 20)

        # Set up mock action manager for the new action system
        self.agent.action_manager = MockActionManager(self)

        # Ensure behavior trees are initialized for all agent types
        if hasattr(self.agent, '_initialize_behavior_tree'):
            if not getattr(self.agent, 'behavior_tree_initialized', True):
                self.agent._initialize_behavior_tree()

        # Set up agent for behavior tree execution
        self.agent.has_initial_map_data = True  # Allow behavior tree to run in tests
        self.agent.use_behavior_tree = True     # Ensure behavior tree is enabled

        # Override agent's move method to actually update position based on velocity
        original_move = self.agent.move
        def mock_move(delta_time: float):
            # Apply velocity to position
            if hasattr(self.agent, 'velocity_x') and hasattr(self.agent, 'velocity_y'):
                self.agent.x += self.agent.velocity_x * delta_time
                self.agent.y += self.agent.velocity_y * delta_time
            # Call original move for other processing
            return original_move(delta_time)
        self.agent.move = mock_move

    async def send_tcp_message(self, message: Message):
        """Mock message sending"""
        self.sent_messages.append(message)

    async def send_action(self, action: Dict[str, Any]):
        """Mock action sending"""
        message = Message(
            type=MessageType.AGENT_ACTION,
            payload=action,
            timestamp=time.time()
        )
        await self.send_tcp_message(message)


class FastTestFixture:
    """Complete fast test fixture with all components"""

    def __init__(self, world_width: int = 20, world_height: int = 20):
        self.server = MockGameServer(world_width, world_height)
        self.clients = {}

    async def add_client(self, agent_type: str = "player", spawn_x: float = 10, spawn_y: float = 10) -> MockClient:
        """Add a client with agent to the test"""
        client = MockClient(agent_type)

        # Spawn agent on server
        agent_id = self.server.world.spawn_agent(agent_type, spawn_x, spawn_y)

        # Create client agent
        client.create_agent(agent_id, spawn_x, spawn_y)
        client.connected = True

        # Register with server
        self.server.agent_registry.register_agent(agent_id, agent_type, spawn_x, spawn_y)

        self.clients[agent_id] = client
        return client

    def get_agent_positions(self) -> Dict[str, tuple]:
        """Get all agent positions for assertions"""
        positions = {}
        for agent_id, agent in self.server.world.agents.items():
            positions[agent_id] = (agent.x, agent.y)
        return positions

    def set_terrain(self, terrain_dict: Dict[tuple, TileType]):
        """Set custom terrain for the test world"""
        self.server.world.terrain.update(terrain_dict)