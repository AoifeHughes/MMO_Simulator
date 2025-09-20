"""
Client-side agent that connects to the server
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from client.core.world_view import WorldView
from client.network.server_connection import ServerConnection
from shared.messages import (
    ActionMessage, QueryMessage, ActionType, QueryType,
    ConnectMessage, WorldUpdateMessage
)
from shared.math_utils import Vector2
from shared.constants import DEFAULT_SERVER_HOST, DEFAULT_SERVER_PORT

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent configuration"""
    name: str
    agent_class: str = "Adventurer"
    personality: Dict[str, float] = field(default_factory=dict)
    behavior_params: Dict[str, Any] = field(default_factory=dict)


class AgentClient:
    """Base class for client-side agents"""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.agent_id: Optional[str] = None
        self.connected = False

        # Client systems
        self.world_view = WorldView()
        self.connection: Optional[ServerConnection] = None

        # Agent state
        self.position = Vector2(0, 0)
        self.health = 100
        self.max_health = 100
        self.level = 1
        self.state = "idle"

        # Decision-making
        self.current_goal = None
        self.action_queue: List[Dict[str, Any]] = []
        self.last_decision_time = 0
        self.decision_interval = 0.5  # Make decisions every 0.5 seconds

        logger.info(f"AgentClient '{config.name}' initialized")

    async def connect(self, host: str = DEFAULT_SERVER_HOST,
                     port: int = DEFAULT_SERVER_PORT):
        """Connect to the server"""
        try:
            # Create connection
            self.connection = ServerConnection()
            await self.connection.connect(host, port)

            # Send connect message
            connect_msg = ConnectMessage(
                agent_name=self.config.name,
                agent_class=self.config.agent_class
            )
            await self.connection.send(connect_msg)

            # Wait for welcome
            welcome = await self.connection.receive()
            if welcome and welcome.type.value == 'WELCOME':
                self.agent_id = welcome.agent_id
                self.position = Vector2.from_tuple(welcome.initial_position)
                self.world_view.set_vision_range(welcome.vision_range)
                self.connected = True

                logger.info(f"Connected as agent {self.agent_id}")
                return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

        return False

    async def disconnect(self):
        """Disconnect from server"""
        if self.connection:
            await self.connection.disconnect()
        self.connected = False
        logger.info("Disconnected from server")

    async def run(self):
        """Main agent loop"""
        if not self.connected:
            logger.error("Not connected to server")
            return

        # Start receiving updates
        receive_task = asyncio.create_task(self._receive_loop())

        # Start heartbeat
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Main decision loop
        try:
            await self._decision_loop()
        except KeyboardInterrupt:
            logger.info("Agent interrupted")
        finally:
            receive_task.cancel()
            heartbeat_task.cancel()
            await self.disconnect()

    async def _receive_loop(self):
        """Receive and process server messages"""
        while self.connected:
            try:
                message = await self.connection.receive()
                if not message:
                    continue

                # Process different message types
                if message.type.value == 'WORLD_UPDATE':
                    await self._handle_world_update(message)
                elif message.type.value == 'ACTION_RESULT':
                    await self._handle_action_result(message)
                elif message.type.value == 'EVENT':
                    await self._handle_event(message)
                elif message.type.value == 'ERROR':
                    logger.error(f"Server error: {message.error}")

            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                await asyncio.sleep(0.1)

    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.connected:
            await asyncio.sleep(5.0)
            # Heartbeat is handled by last_heartbeat in connection

    async def _decision_loop(self):
        """Main decision-making loop"""
        while self.connected:
            current_time = time.time()

            # Make decisions at intervals
            if current_time - self.last_decision_time >= self.decision_interval:
                await self.make_decision()
                self.last_decision_time = current_time

            # Process action queue
            if self.action_queue:
                action = self.action_queue.pop(0)
                await self.execute_action(action)

            await asyncio.sleep(0.1)

    async def make_decision(self):
        """Make a decision based on world state - Override in subclasses"""
        # Base implementation - random wandering
        if self.state == "idle":
            # Query surroundings
            surroundings = await self.query_surroundings()

            # Simple decision: move randomly
            import random
            if random.random() < 0.3:  # 30% chance to move
                target = Vector2(
                    self.position.x + random.uniform(-100, 100),
                    self.position.y + random.uniform(-100, 100)
                )
                self.action_queue.append({
                    'type': 'move',
                    'target': target
                })

    async def execute_action(self, action: Dict[str, Any]):
        """Execute an action"""
        if action['type'] == 'move':
            await self.move_to(action['target'])
        elif action['type'] == 'attack':
            await self.attack(action['target_id'])
        elif action['type'] == 'interact':
            await self.interact(action['target_id'])

    async def move_to(self, target: Vector2):
        """Send move command to server"""
        msg = ActionMessage(
            action=ActionType.MOVE,
            data={'target': target.to_tuple(), 'speed': 'walk'},
            agent_id=self.agent_id
        )
        await self.connection.send(msg)
        self.state = "moving"

    async def attack(self, target_id: str):
        """Send attack command to server"""
        msg = ActionMessage(
            action=ActionType.ATTACK,
            data={'target_id': target_id},
            agent_id=self.agent_id
        )
        await self.connection.send(msg)
        self.state = "combat"

    async def interact(self, target_id: str):
        """Send interact command to server"""
        msg = ActionMessage(
            action=ActionType.INTERACT,
            data={'target_id': target_id},
            agent_id=self.agent_id
        )
        await self.connection.send(msg)
        self.state = "interacting"

    async def query_stats(self) -> Dict[str, Any]:
        """Query own stats from server"""
        msg = QueryMessage(
            query=QueryType.GET_STATS,
            agent_id=self.agent_id
        )
        await self.connection.send(msg)
        # In real implementation, would wait for response
        return {}

    async def query_surroundings(self) -> Dict[str, Any]:
        """Query surroundings from server"""
        msg = QueryMessage(
            query=QueryType.GET_SURROUNDINGS,
            params={'radius': 100},
            agent_id=self.agent_id
        )
        await self.connection.send(msg)
        # In real implementation, would wait for response
        return {}

    async def _handle_world_update(self, message: WorldUpdateMessage):
        """Handle world update from server"""
        self.world_view.update(message)

    async def _handle_action_result(self, message):
        """Handle action result from server"""
        if message.success:
            logger.debug(f"Action {message.action.value} succeeded")
        else:
            logger.warning(f"Action {message.action.value} failed: {message.error_message}")

        # Update state based on result
        if message.action == ActionType.MOVE and not message.success:
            self.state = "idle"

    async def _handle_event(self, message):
        """Handle event from server"""
        event_type = message.event.value
        logger.info(f"Event: {event_type} - {message.data}")