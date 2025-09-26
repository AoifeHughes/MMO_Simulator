"""
MMO-Style Game Server

This module implements the main MMO server with:
- 60Hz server ticks with delta updates
- Authoritative world state management
- Unified action command processing
- Transactional inventory system
- High-frequency position updates

This replaces the legacy server.py with proper MMO architecture.
"""

import asyncio
import json
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import asdict

from server.mmo_core import (
    AuthoritativeGameState, ServerTickScheduler, UpdateChannel,
    PositionComponent, HealthComponent
)
from server.action_commands import ActionCommandProcessor
from server.inventory_system import InventoryManager
from server.agent_state import AgentRegistry
from server.attack_system import AttackSystem
from server.world import ServerWorld
from shared.constants import MAX_CLIENTS, SERVER_PORT, UDP_PORT
from shared.messages import Message, MessageType, WorldState
from shared.actions import ActionType, ActionRequest, ActionResponse, ActionResult
from world.terrain_generator import TerrainType

logger = logging.getLogger(__name__)


class ClientConnection:
    """Represents a connected client with MMO-style state synchronization"""

    def __init__(self, client_id: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, server: 'MMOGameServer'):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.server = server
        self.connected = True
        self.agent_id: Optional[str] = None
        self.last_update_time = time.time()
        self.update_channels: Dict[UpdateChannel, float] = {
            UpdateChannel.HIGH_FREQ: 0.0,
            UpdateChannel.MEDIUM_FREQ: 0.0,
            UpdateChannel.LOW_FREQ: 0.0
        }

    async def handle(self):
        """Handle client connection with MMO-style communication"""
        try:
            while self.connected:
                # Read message
                data = await self.reader.read(8192)
                if not data:
                    break

                try:
                    message = Message.from_json(data.decode())
                    await self.handle_message(message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client {self.client_id}")
                except Exception as e:
                    logger.error(f"Error handling message from client {self.client_id}: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Client {self.client_id} connection error: {e}")
        finally:
            self.connected = False

    async def handle_message(self, message: Message):
        """Handle incoming message from client"""
        if message.type == MessageType.CONNECT:
            await self.handle_connect(message)
        elif message.type == MessageType.ACTION:
            await self.handle_action(message)
        elif message.type == MessageType.MOVEMENT:
            await self.handle_movement(message)
        elif message.type == MessageType.HEARTBEAT:
            await self.send_message(Message(MessageType.HEARTBEAT, {}))

    async def handle_connect(self, message: Message):
        """Handle client connection request"""
        agent_type = message.data.get("agent_type", "player")

        # Create agent in world
        spawn_x, spawn_y = 50.0, 50.0  # Default spawn
        if hasattr(self.server.world, 'get_spawn_position'):
            spawn_x, spawn_y = self.server.world.get_spawn_position()

        agent_id = self.server.world.spawn_agent(agent_type, spawn_x, spawn_y)
        if not agent_id:
            await self.send_message(Message(MessageType.CONNECT_RESPONSE, {
                "success": False,
                "message": "Failed to spawn agent"
            }))
            return

        # Register agent in systems
        agent_state = self.server.agent_registry.register_agent(agent_id, agent_type, spawn_x, spawn_y)

        # Create entity in authoritative game state
        self.server.game_state.create_entity(agent_id, "agent")

        # Set initial position
        self.server.game_state.teleport_entity(agent_id, spawn_x, spawn_y)

        # Set up transactional inventory
        self.server.inventory_manager.get_or_create_inventory(agent_id, agent_state.inventory)

        # Assign to client
        self.agent_id = agent_id
        self.server.client_agents[agent_id] = self.client_id

        logger.info(f"Client {self.client_id} connected as agent {agent_id} ({agent_type}) at ({spawn_x}, {spawn_y})")

        await self.send_message(Message(MessageType.CONNECT_RESPONSE, {
            "success": True,
            "agent_id": agent_id,
            "spawn_position": {"x": spawn_x, "y": spawn_y}
        }))

        # Send initial world state
        await self.send_world_state()

    async def handle_action(self, message: Message):
        """Handle action request from client"""
        if not self.agent_id:
            return

        try:
            action_type_str = message.data.get("action_type")
            parameters = message.data.get("parameters", {})

            action_type = ActionType(action_type_str)

            # Process through command system
            result = await self.server.command_processor.submit_command(
                action_type, self.agent_id, parameters
            )

            # Send response to client
            response = ActionResponse(
                action_id=message.data.get("action_id", "unknown"),
                agent_id=self.agent_id,
                action_type=action_type,
                result=result.result_type,
                message=result.message,
                approved_parameters=result.data if result.success else None
            )

            await self.send_message(Message(MessageType.ACTION_RESPONSE, response.to_dict()))

            # Send events to all clients if any were generated
            if result.events:
                for event in result.events:
                    await self.server.broadcast_event(event)

        except Exception as e:
            logger.error(f"Error handling action from client {self.client_id}: {e}")

    async def handle_movement(self, message: Message):
        """Handle movement request (high frequency)"""
        if not self.agent_id:
            return

        try:
            target_x = message.data.get("target_x")
            target_y = message.data.get("target_y")

            if target_x is not None and target_y is not None:
                # Use action command system for movement validation
                result = await self.server.command_processor.submit_command(
                    ActionType.MOVE_TO, self.agent_id, {
                        "target_x": target_x,
                        "target_y": target_y,
                        "speed_multiplier": message.data.get("speed_multiplier", 1.0)
                    }
                )

                # Movement is handled through regular state updates, no immediate response needed
                # unless there was an error
                if not result.success:
                    await self.send_message(Message(MessageType.MOVEMENT_RESPONSE, {
                        "success": False,
                        "message": result.message
                    }))

        except Exception as e:
            logger.error(f"Error handling movement from client {self.client_id}: {e}")

    async def send_message(self, message: Message):
        """Send message to client"""
        if not self.connected:
            return

        try:
            data = message.to_json().encode()
            self.writer.write(len(data).to_bytes(4, 'big') + data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending message to client {self.client_id}: {e}")
            self.connected = False

    async def send_world_state(self):
        """Send complete world state to client"""
        try:
            world_state = self.server.get_world_state_for_client(self.agent_id)
            await self.send_message(Message(MessageType.WORLD_STATE, world_state))
        except Exception as e:
            logger.error(f"Error sending world state to client {self.client_id}: {e}")

    def should_send_update(self, channel: UpdateChannel, current_time: float) -> bool:
        """Check if we should send an update for this channel"""
        last_update = self.update_channels.get(channel, 0.0)

        if channel == UpdateChannel.HIGH_FREQ:
            return current_time - last_update >= 1.0 / 60.0  # 60 FPS
        elif channel == UpdateChannel.MEDIUM_FREQ:
            return current_time - last_update >= 1.0 / 20.0  # 20 FPS
        elif channel == UpdateChannel.LOW_FREQ:
            return current_time - last_update >= 1.0 / 5.0   # 5 FPS
        else:
            return True  # Event-driven, always send


class MMOGameServer:
    """
    MMO-style game server with high-frequency updates and authoritative state.

    This replaces the legacy GameServer with proper MMO architecture.
    """

    def __init__(self, world_width: int = 100, world_height: int = 100,
                 terrain_type: Optional[TerrainType] = None, seed: int = 42):

        # Core MMO systems
        self.game_state = AuthoritativeGameState()
        self.tick_scheduler = ServerTickScheduler(target_fps=60.0)
        self.inventory_manager = InventoryManager()

        # Legacy systems (adapted to work with MMO core)
        self.world = ServerWorld(world_width, world_height, terrain_type=terrain_type, seed=seed)
        self.agent_registry = AgentRegistry()
        self.attack_system = AttackSystem()

        # Command processing
        self.command_processor = ActionCommandProcessor(
            self.game_state, self.world, self.agent_registry
        )

        # Network
        self.clients: Dict[str, ClientConnection] = {}
        self.client_agents: Dict[str, str] = {}  # agent_id -> client_id
        self.tcp_server = None
        self.running = False

        # Database (if needed)
        try:
            from server.database import DatabaseManager
            self.database_manager = DatabaseManager()
        except ImportError:
            self.database_manager = None

        # Subscribe to game state events
        self.game_state.subscribe_to_event("entity_died", self.handle_entity_death)

        # Subscribe to server ticks
        self.tick_scheduler.subscribe_to_ticks(self.handle_server_tick)

        logger.info(f"MMO Server initialized with {world_width}x{world_height} world")

    async def start(self):
        """Start the MMO server"""
        self.running = True

        # Start TCP server
        self.tcp_server = await asyncio.start_server(
            self.handle_tcp_client, "127.0.0.1", SERVER_PORT
        )

        logger.info(f"MMO Server started on TCP:{SERVER_PORT}")

        # Start all systems concurrently
        await asyncio.gather(
            self.tcp_server.serve_forever(),
            self.tick_scheduler.start(),
            self.command_processor.start_processing(),
            self.client_update_loop(),
            self.respawn_monitor(),
            return_exceptions=True
        )

    async def stop(self):
        """Stop the MMO server"""
        self.running = False

        if self.tcp_server:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()

        self.tick_scheduler.stop()
        self.command_processor.stop_processing()

        # Disconnect all clients
        for client in list(self.clients.values()):
            client.connected = False

        logger.info("MMO Server stopped")

    async def handle_tcp_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle new TCP client connection"""
        client_id = f"client_{len(self.clients)}"
        client = ClientConnection(client_id, reader, writer, self)
        self.clients[client_id] = client

        logger.info(f"New client connected: {client_id}")

        try:
            await client.handle()
        finally:
            await self.disconnect_client(client_id)

    async def disconnect_client(self, client_id: str):
        """Handle client disconnection"""
        if client_id not in self.clients:
            return

        client = self.clients[client_id]

        if client.agent_id:
            # Remove from game state
            self.game_state.destroy_entity(client.agent_id)

            # Remove from world
            if hasattr(self.world, 'remove_agent'):
                self.world.remove_agent(client.agent_id)

            # Clean up mappings
            if client.agent_id in self.client_agents:
                del self.client_agents[client.agent_id]

            logger.info(f"Agent {client.agent_id} disconnected")

        del self.clients[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def handle_server_tick(self, tick):
        """Handle server tick - update game state"""
        # Update authoritative game state
        await self.game_state.tick_update(tick.delta_time)

        # Update legacy world (for compatibility) - it doesn't take delta time
        if hasattr(self.world, 'update'):
            self.world.update()

        # Sync positions between game state and world
        await self.sync_positions_with_legacy()

    async def sync_positions_with_legacy(self):
        """Sync positions between new game state and legacy world"""
        for entity_id in list(self.game_state.entities.keys()):
            pos_component = self.game_state.get_component(entity_id, "PositionComponent")
            if pos_component:
                # Update legacy world agent position
                agent = self.world.get_agent(entity_id)
                if agent:
                    agent.x = pos_component.x
                    agent.y = pos_component.y
                    agent.rotation = pos_component.rotation

                # Update agent registry position
                agent_state = self.agent_registry.get_agent(entity_id)
                if agent_state:
                    agent_state.update_position(pos_component.x, pos_component.y, pos_component.rotation)

    async def client_update_loop(self):
        """Send updates to clients at appropriate frequencies"""
        while self.running:
            try:
                current_time = time.time()

                # Send updates for each channel
                for channel in UpdateChannel:
                    entities_to_update = self.game_state.get_entities_by_channel(channel)

                    if entities_to_update:
                        # Send to clients that need this update frequency
                        for client in self.clients.values():
                            if client.connected and client.agent_id and client.should_send_update(channel, current_time):
                                await self.send_partial_world_state(client, entities_to_update)
                                client.update_channels[channel] = current_time

                # Sleep until next update cycle
                await asyncio.sleep(1.0 / 120.0)  # 120Hz update check (faster than any send frequency)

            except Exception as e:
                logger.error(f"Error in client update loop: {e}")
                await asyncio.sleep(1.0)

    async def send_partial_world_state(self, client: ClientConnection, entities: Dict[str, Dict[str, Any]]):
        """Send partial world state update to client"""
        try:
            update_data = {
                "type": "partial_update",
                "entities": entities,
                "timestamp": time.time()
            }

            await client.send_message(Message(MessageType.WORLD_STATE, update_data))
        except Exception as e:
            logger.error(f"Error sending partial state to client {client.client_id}: {e}")

    async def broadcast_event(self, event: Dict[str, Any]):
        """Broadcast event to all connected clients"""
        event_message = Message(MessageType.EVENT, event)

        for client in self.clients.values():
            if client.connected:
                await client.send_message(event_message)

    async def respawn_monitor(self):
        """Monitor for agents that need respawning"""
        while self.running:
            try:
                current_time = time.time()

                for agent_id, client_id in list(self.client_agents.items()):
                    health_component = self.game_state.get_component(agent_id, "HealthComponent")
                    if health_component and not health_component.is_alive:
                        agent_state = self.agent_registry.get_agent(agent_id)

                        if agent_state and agent_state.respawn_time <= current_time:
                            # Respawn agent
                            spawn_x, spawn_y = 50.0, 50.0
                            if hasattr(self.world, 'get_spawn_position'):
                                spawn_x, spawn_y = self.world.get_spawn_position()

                            # Respawn in game state
                            health_component.respawn()
                            self.game_state.teleport_entity(agent_id, spawn_x, spawn_y)

                            # Update agent state
                            agent_state.respawn(spawn_x, spawn_y)

                            logger.info(f"Respawned agent {agent_id} at ({spawn_x}, {spawn_y})")

                            # Notify client
                            if client_id in self.clients:
                                client = self.clients[client_id]
                                await client.send_message(Message(MessageType.RESPAWN, {
                                    "agent_id": agent_id,
                                    "position": {"x": spawn_x, "y": spawn_y}
                                }))

                await asyncio.sleep(1.0)  # Check every second

            except Exception as e:
                logger.error(f"Error in respawn monitor: {e}")
                await asyncio.sleep(5.0)

    def handle_entity_death(self, event_name: str, data: Dict[str, Any]):
        """Handle entity death event"""
        entity_id = data.get("entity_id")
        if entity_id:
            agent_state = self.agent_registry.get_agent(entity_id)
            if agent_state:
                agent_state.respawn_time = time.time() + 5.0  # 5 second respawn delay

    def get_world_state_for_client(self, agent_id: str) -> Dict[str, Any]:
        """Get complete world state for a specific client"""
        world_state = {
            "agents": [],
            "world_objects": [],
            "timestamp": time.time()
        }

        # Add all entities from game state
        for entity_id, components in self.game_state.entities.items():
            entity_data = {"entity_id": entity_id}

            for component_type, component in components.items():
                component_key = component_type.lower().replace("component", "")
                entity_data[component_key] = component.to_dict()

            # Add inventory data from agent registry
            agent_state = self.agent_registry.get_agent(entity_id)
            if agent_state:
                entity_data["inventory"] = agent_state.inventory.to_dict()
                entity_data["stats"] = agent_state.stats

            world_state["agents"].append(entity_data)

        # Add world objects if available
        if hasattr(self.world, 'world_objects'):
            world_state["world_objects"] = [obj.to_dict() for obj in self.world.world_objects.get_all_objects()]

        return world_state

    def get_server_stats(self) -> Dict[str, Any]:
        """Get comprehensive server statistics"""
        return {
            "connected_clients": len(self.clients),
            "active_agents": len(self.client_agents),
            "game_entities": len(self.game_state.entities),
            "command_processor": self.command_processor.get_stats(),
            "inventory_manager": self.inventory_manager.get_all_stats(),
            "tick_scheduler": self.tick_scheduler.get_performance_stats(),
            "uptime": time.time() - getattr(self, 'start_time', time.time())
        }

    async def start_scenario_tracking(self, scenario_name: str):
        """Start database tracking for a scenario (compatibility)"""
        if self.database_manager:
            try:
                await self.database_manager.initialize_scenario(scenario_name)
                logger.info(f"Started database tracking for scenario: {scenario_name}")
            except Exception as e:
                logger.error(f"Failed to start scenario tracking: {e}")