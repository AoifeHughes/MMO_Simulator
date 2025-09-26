"""
Simplified Game Server

This replaces the complex server system with a streamlined version that:
- Uses single TCP protocol (no UDP complexity)
- Simplified message handling (6 core message types)
- Clear position authority (server owns positions)
- Simple action validation and processing
- Preserves client-side decision making

Key improvements:
- Eliminates position sync conflicts
- Reduces communication overhead
- Maintains server authority for validation
- Simpler debugging and error tracking
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from server.world import ServerWorld
from shared.constants import SERVER_PORT
from shared.simple_messages import (
    SimpleMessage, SimpleMessageType, SimpleActionType, SimpleEventType,
    create_world_update_message, create_action_response_message, create_game_event_message
)
from world.terrain_generator import TerrainType

logger = logging.getLogger(__name__)


class SimpleGameServer:
    """Simplified game server with streamlined communication"""

    def __init__(self, world_width: int = 100, world_height: int = 100,
                 terrain_type: Optional[TerrainType] = None, seed: int = 42):
        self.world = ServerWorld(world_width, world_height, terrain_type=terrain_type, seed=seed)

        # Connection management
        self.clients: Dict[str, "SimpleClientConnection"] = {}
        self.tcp_server = None
        self.running = False

        # Simple action processing (no complex pipeline)
        self.pending_actions: List[Dict[str, Any]] = []

        # Update timing
        self.last_world_update = 0.0
        self.world_update_interval = 0.1  # 100ms = 10 FPS updates

        # Statistics
        self.stats = {
            "clients_connected": 0,
            "actions_processed": 0,
            "world_updates_sent": 0,
            "errors": 0
        }

    async def start(self):
        """Start the simplified server"""
        self.running = True

        # Start TCP server (no UDP complexity)
        self.tcp_server = await asyncio.start_server(
            self.handle_client_connection, "127.0.0.1", SERVER_PORT
        )

        logger.info(f"Simplified server started on TCP:{SERVER_PORT}")

        # Start server loops
        await asyncio.gather(
            self.tcp_server.serve_forever(),
            self.world_update_loop(),
            self.action_processing_loop()
        )

    async def stop(self):
        """Stop the server"""
        self.running = False
        logger.info("Stopping simplified server...")

        # Close all client connections
        for client in list(self.clients.values()):
            await client.disconnect()

        if self.tcp_server:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()

        logger.info("Simplified server stopped")

    async def handle_client_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle new client connection"""
        client_id = str(len(self.clients))
        client = SimpleClientConnection(client_id, reader, writer, self)
        self.clients[client_id] = client

        logger.info(f"Client {client_id} connected")
        self.stats["clients_connected"] += 1

        try:
            await client.handle_messages()
        except Exception as e:
            logger.error(f"Client {client_id} error: {e}")
            self.stats["errors"] += 1
        finally:
            await self.disconnect_client(client_id)

    async def disconnect_client(self, client_id: str):
        """Disconnect and cleanup client"""
        if client_id in self.clients:
            client = self.clients[client_id]
            if client.agent_id:
                # Remove agent from world (simplified - just mark as disconnected)
                agent = self.world.get_agent(client.agent_id)
                if agent:
                    # Don't despawn, just mark as uncontrolled
                    logger.info(f"Agent {client.agent_id[:8]} is now uncontrolled")

            del self.clients[client_id]
            logger.info(f"Client {client_id} disconnected")

    async def world_update_loop(self):
        """Send periodic world updates to all clients"""
        while self.running:
            current_time = time.time()

            if (current_time - self.last_world_update) >= self.world_update_interval:
                await self.broadcast_world_update()
                self.last_world_update = current_time

            await asyncio.sleep(0.01)  # 10ms check interval

    async def action_processing_loop(self):
        """Process queued actions"""
        while self.running:
            if self.pending_actions:
                action_data = self.pending_actions.pop(0)
                await self.process_action(action_data)
                self.stats["actions_processed"] += 1

            await asyncio.sleep(0.01)  # 10ms check interval

    async def broadcast_world_update(self):
        """Send world state to all connected clients"""
        if not self.clients:
            return

        # Get all agents for world update
        agents_data = []
        for agent in self.world.get_all_agents():
            agents_data.append({
                "id": agent.id,
                "x": agent.x,
                "y": agent.y,
                "rotation": agent.rotation,
                "agent_type": agent.agent_type,
                "health": agent.health,
                "max_health": agent.max_health,
                "is_alive": agent.is_alive,
                "velocity_x": getattr(agent, 'velocity_x', 0),
                "velocity_y": getattr(agent, 'velocity_y', 0)
            })

        # World info
        world_info = {
            "width": self.world.world_map.width,
            "height": self.world.world_map.height,
            "timestamp": time.time()
        }

        # Create and send update message
        update_message = create_world_update_message(agents_data, world_info)

        # Send to all clients
        for client in self.clients.values():
            try:
                await client.send_message(update_message)
            except Exception as e:
                logger.error(f"Failed to send world update to {client.client_id}: {e}")

        self.stats["world_updates_sent"] += 1
        logger.debug(f"Sent world update to {len(self.clients)} clients with {len(agents_data)} agents")

    async def queue_action(self, client_id: str, agent_id: str, action_type: str,
                          parameters: Dict[str, Any], request_id: str):
        """Queue an action for processing"""
        action_data = {
            "client_id": client_id,
            "agent_id": agent_id,
            "action_type": action_type,
            "parameters": parameters,
            "request_id": request_id,
            "timestamp": time.time()
        }
        self.pending_actions.append(action_data)

    async def process_action(self, action_data: Dict[str, Any]):
        """Process a single action with simplified validation"""
        client_id = action_data["client_id"]
        agent_id = action_data["agent_id"]
        action_type = action_data["action_type"]
        parameters = action_data["parameters"]
        request_id = action_data["request_id"]

        # Get client for response
        client = self.clients.get(client_id)
        if not client:
            return

        # Basic validation
        agent = self.world.get_agent(agent_id)
        if not agent:
            await client.send_action_response(request_id, False, "Agent not found")
            return

        if not agent.is_alive:
            await client.send_action_response(request_id, False, "Agent is dead")
            return

        # Process action based on type
        try:
            if action_type == SimpleActionType.MOVE_TO:
                await self.process_move_action(agent, parameters, client, request_id)
            elif action_type == SimpleActionType.ATTACK:
                await self.process_attack_action(agent, parameters, client, request_id)
            elif action_type == SimpleActionType.FISH:
                await self.process_fish_action(agent, parameters, client, request_id)
            elif action_type == SimpleActionType.HARVEST_WOOD:
                await self.process_harvest_wood_action(agent, parameters, client, request_id)
            elif action_type == SimpleActionType.STOP:
                await self.process_stop_action(agent, parameters, client, request_id)
            else:
                await client.send_action_response(request_id, False, f"Unknown action type: {action_type}")

        except Exception as e:
            logger.error(f"Error processing action {action_type}: {e}")
            await client.send_action_response(request_id, False, f"Action processing error: {e}")

    async def process_move_action(self, agent, parameters: Dict, client, request_id: str):
        """Process movement action"""
        target_x = parameters.get("target_x")
        target_y = parameters.get("target_y")

        if target_x is None or target_y is None:
            await client.send_action_response(request_id, False, "Missing target coordinates")
            return

        # Simple validation - check bounds
        if not (0 <= target_x < self.world.world_map.width and 0 <= target_y < self.world.world_map.height):
            await client.send_action_response(request_id, False, "Target out of bounds")
            return

        # Check if target is walkable
        if not self.world.world_map.is_walkable(int(target_x), int(target_y)):
            await client.send_action_response(request_id, False, "Target location not walkable")
            return

        # Move agent (simplified - direct movement)
        success = self.world.move_agent(agent.id, target_x, target_y, agent.rotation)

        if success:
            await client.send_action_response(request_id, True, "Movement successful",
                                            {"new_x": target_x, "new_y": target_y})
        else:
            await client.send_action_response(request_id, False, "Movement failed")

    async def process_attack_action(self, agent, parameters: Dict, client, request_id: str):
        """Process attack action"""
        target_id = parameters.get("target_id")
        if not target_id:
            await client.send_action_response(request_id, False, "Missing target_id")
            return

        target = self.world.get_agent(target_id)
        if not target or not target.is_alive:
            await client.send_action_response(request_id, False, "Target not found or dead")
            return

        # Simple range check
        distance = ((agent.x - target.x) ** 2 + (agent.y - target.y) ** 2) ** 0.5
        if distance > 3.0:  # Attack range
            await client.send_action_response(request_id, False, "Target too far away")
            return

        # Deal damage
        damage = 25.0
        target.health = max(0, target.health - damage)

        # Check for death
        if target.health <= 0:
            target.is_alive = False
            # Broadcast death event
            death_event = create_game_event_message(SimpleEventType.AGENT_DEATH, {
                "dead_agent_id": target_id,
                "killer_id": agent.id
            })
            await self.broadcast_event(death_event)

        await client.send_action_response(request_id, True, f"Attack successful, dealt {damage} damage",
                                        {"damage": damage, "target_health": target.health})

    async def process_fish_action(self, agent, parameters: Dict, client, request_id: str):
        """Process fishing action"""
        # Simple fishing - check if near water
        agent_x, agent_y = int(agent.x), int(agent.y)

        # Check surrounding tiles for water
        found_water = False
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                check_x, check_y = agent_x + dx, agent_y + dy
                if (0 <= check_x < self.world.world_map.width and
                    0 <= check_y < self.world.world_map.height):
                    tile_type = self.world.world_map.get_tile(check_x, check_y)
                    if tile_type.name == "WATER":
                        found_water = True
                        break

        if not found_water:
            await client.send_action_response(request_id, False, "No water nearby for fishing")
            return

        # Simulate fishing time and success
        import random
        fishing_time = random.uniform(1.0, 3.0)
        await asyncio.sleep(fishing_time)

        if random.random() < 0.7:  # 70% success rate
            await client.send_action_response(request_id, True, f"Caught a fish! (took {fishing_time:.1f}s)",
                                            {"success": True, "item": "fish", "fishing_time": fishing_time})
        else:
            await client.send_action_response(request_id, True, f"No luck fishing (took {fishing_time:.1f}s)",
                                            {"success": False, "fishing_time": fishing_time})

    async def process_harvest_wood_action(self, agent, parameters: Dict, client, request_id: str):
        """Process wood harvesting action"""
        # Check if near wood
        agent_x, agent_y = int(agent.x), int(agent.y)

        found_wood = False
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                check_x, check_y = agent_x + dx, agent_y + dy
                if (0 <= check_x < self.world.world_map.width and
                    0 <= check_y < self.world.world_map.height):
                    tile_type = self.world.world_map.get_tile(check_x, check_y)
                    if tile_type.name == "WOOD":
                        found_wood = True
                        break

        if not found_wood:
            await client.send_action_response(request_id, False, "No wood nearby for harvesting")
            return

        # Simulate harvesting
        import random
        harvest_time = random.uniform(1.5, 2.5)
        await asyncio.sleep(harvest_time)

        await client.send_action_response(request_id, True, f"Harvested wood! (took {harvest_time:.1f}s)",
                                        {"success": True, "item": "wood", "harvest_time": harvest_time})

    async def process_stop_action(self, agent, parameters: Dict, client, request_id: str):
        """Process stop movement action"""
        agent.velocity_x = 0
        agent.velocity_y = 0
        await client.send_action_response(request_id, True, "Movement stopped")

    async def broadcast_event(self, event_message: SimpleMessage):
        """Broadcast game event to all clients"""
        for client in self.clients.values():
            try:
                await client.send_message(event_message)
            except Exception as e:
                logger.error(f"Failed to send event to {client.client_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
        return {
            **self.stats,
            "connected_clients": len(self.clients),
            "total_agents": len(self.world.get_all_agents()),
            "pending_actions": len(self.pending_actions)
        }


class SimpleClientConnection:
    """Simplified client connection handler"""

    def __init__(self, client_id: str, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, server: SimpleGameServer):
        self.client_id = client_id
        self.reader = reader
        self.writer = writer
        self.server = server
        self.agent_id: Optional[str] = None

    async def handle_messages(self):
        """Handle incoming messages from client"""
        while True:
            try:
                data = await self.reader.readline()
                if not data:
                    break

                message = SimpleMessage.from_json(data.decode())
                await self.process_message(message)

            except Exception as e:
                logger.error(f"Error handling message from {self.client_id}: {e}")
                break

    async def process_message(self, message: SimpleMessage):
        """Process a single message from client"""
        if message.type == SimpleMessageType.CONNECT:
            await self.handle_connect(message)
        elif message.type == SimpleMessageType.ACTION_REQUEST:
            await self.handle_action_request(message)
        elif message.type == SimpleMessageType.DISCONNECT:
            await self.disconnect()

    async def handle_connect(self, message: SimpleMessage):
        """Handle client connection request"""
        agent_type = message.payload.get("agent_type", "player")

        # Spawn agent in world
        self.agent_id = self.server.world.spawn_agent(agent_type)
        agent = self.server.world.get_agent(self.agent_id)

        # Send connection response
        response = SimpleMessage(
            type=SimpleMessageType.WORLD_UPDATE,  # Use world update as connection response
            payload={
                "connection_success": True,
                "agent_id": self.agent_id,
                "client_id": self.client_id,
                "agent_data": {
                    "id": self.agent_id,
                    "x": agent.x,
                    "y": agent.y,
                    "rotation": agent.rotation,
                    "agent_type": agent_type,
                    "health": agent.health
                }
            }
        )
        await self.send_message(response)
        logger.info(f"Client {self.client_id} spawned {agent_type} agent {self.agent_id[:8]}")

    async def handle_action_request(self, message: SimpleMessage):
        """Handle action request from client"""
        if not self.agent_id:
            return

        payload = message.payload
        action_type = payload.get("action_type")
        parameters = payload.get("parameters", {})
        request_id = payload.get("request_id", "unknown")

        # Queue action for processing
        await self.server.queue_action(
            self.client_id, self.agent_id, action_type, parameters, request_id
        )

    async def send_message(self, message: SimpleMessage):
        """Send message to client"""
        try:
            data = message.to_json() + "\n"
            self.writer.write(data.encode())
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Failed to send message to {self.client_id}: {e}")

    async def send_action_response(self, request_id: str, success: bool,
                                  message: str, result_data: Dict = None):
        """Send action response to client"""
        response = create_action_response_message(request_id, success, message, result_data)
        await self.send_message(response)

    async def disconnect(self):
        """Disconnect client"""
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except:
                pass