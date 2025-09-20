"""
HTTP API for server monitoring
"""

import asyncio
import json
import time
from typing import Dict, Any, List
from aiohttp import web, WSMsgType
import logging

from server.core.game_state import GameState

logger = logging.getLogger(__name__)

class MonitorAPI:
    """HTTP/WebSocket API for server monitoring"""

    def __init__(self, game_state: GameState, port: int = 8080):
        self.game_state = game_state
        self.port = port
        self.app = web.Application()
        self.setup_routes()
        self.websocket_clients = set()

    def setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get('/status', self.get_status)
        self.app.router.add_get('/entities', self.get_entities)
        self.app.router.add_get('/stats', self.get_stats)
        self.app.router.add_get('/world', self.get_world_state)
        self.app.router.add_get('/ws', self.websocket_handler)

    async def get_status(self, request):
        """Get basic server status"""
        snapshot = self.game_state.get_state_snapshot()
        return web.json_response({
            'status': 'running',
            'tick': snapshot['tick'],
            'timestamp': time.time(),
            'entity_count': snapshot['entity_count'],
            'active_players': snapshot['active_players'],
            'inactive_players': snapshot['inactive_players']
        })

    async def get_entities(self, request):
        """Get all entities"""
        entities = []

        for entity in self.game_state.entities.values():
            entities.append({
                'id': entity.id,
                'name': entity.name,
                'entity_type': entity.entity_type,
                'position': entity.position.to_tuple(),
                'health_percentage': (entity.health / entity.max_health) * 100 if entity.max_health > 0 else 0,
                'level': entity.level,
                'state': entity.state,
                'is_active': getattr(entity, 'is_active', True),
                'velocity': entity.velocity.to_tuple() if entity.velocity.magnitude() > 0 else None,
                'last_update_time': getattr(entity, 'last_update_time', time.time())
            })

        return web.json_response({'entities': entities})

    async def get_stats(self, request):
        """Get server statistics"""
        snapshot = self.game_state.get_state_snapshot()
        return web.json_response(snapshot['stats'])

    async def get_world_state(self, request):
        """Get complete world state"""
        snapshot = self.game_state.get_state_snapshot()

        # Get all entities
        entities = {}
        for entity in self.game_state.entities.values():
            entities[entity.id] = {
                'id': entity.id,
                'name': entity.name,
                'entity_type': entity.entity_type,
                'position': entity.position.to_tuple(),
                'health_percentage': (entity.health / entity.max_health) * 100 if entity.max_health > 0 else 0,
                'level': entity.level,
                'state': entity.state,
                'is_active': getattr(entity, 'is_active', True),
                'velocity': entity.velocity.to_tuple() if entity.velocity.magnitude() > 0 else None,
                'alive': entity.alive,
                'in_combat': entity.in_combat
            }

        return web.json_response({
            'tick': snapshot['tick'],
            'timestamp': snapshot['time'],
            'entities': entities,
            'active_players': snapshot['active_players'],
            'inactive_players': snapshot['inactive_players'],
            'server_stats': snapshot['stats']
        })

    async def websocket_handler(self, request):
        """WebSocket handler for real-time updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.websocket_clients.add(ws)
        logger.info(f"WebSocket client connected. Total: {len(self.websocket_clients)}")

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self.handle_websocket_message(ws, data)
                    except json.JSONDecodeError:
                        await ws.send_str(json.dumps({'error': 'Invalid JSON'}))
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.websocket_clients.discard(ws)
            logger.info(f"WebSocket client disconnected. Total: {len(self.websocket_clients)}")

        return ws

    async def handle_websocket_message(self, ws, data):
        """Handle WebSocket message from client"""
        msg_type = data.get('type', '')

        if msg_type == 'subscribe':
            # Client wants to subscribe to updates
            await ws.send_str(json.dumps({
                'type': 'subscribed',
                'message': 'Subscribed to world updates'
            }))

        elif msg_type == 'get_world':
            # Client requests current world state
            world_data = await self._get_world_data()
            await ws.send_str(json.dumps({
                'type': 'world_state',
                'data': world_data
            }))

    async def _get_world_data(self) -> Dict[str, Any]:
        """Get world data for WebSocket clients"""
        snapshot = self.game_state.get_state_snapshot()

        entities = {}
        for entity in self.game_state.entities.values():
            entities[entity.id] = {
                'id': entity.id,
                'name': entity.name,
                'entity_type': entity.entity_type,
                'position': entity.position.to_tuple(),
                'health_percentage': (entity.health / entity.max_health) * 100 if entity.max_health > 0 else 0,
                'level': entity.level,
                'state': entity.state,
                'is_active': getattr(entity, 'is_active', True),
                'velocity': entity.velocity.to_tuple() if entity.velocity.magnitude() > 0 else None
            }

        return {
            'tick': snapshot['tick'],
            'timestamp': snapshot['time'],
            'entities': entities,
            'active_players': snapshot['active_players'],
            'inactive_players': snapshot['inactive_players'],
            'server_stats': snapshot['stats']
        }

    async def broadcast_world_update(self):
        """Broadcast world update to all WebSocket clients"""
        if not self.websocket_clients:
            return

        try:
            world_data = await self._get_world_data()
            message = json.dumps({
                'type': 'world_update',
                'data': world_data
            })

            # Send to all connected clients
            disconnected = set()
            for ws in self.websocket_clients:
                try:
                    await ws.send_str(message)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket client: {e}")
                    disconnected.add(ws)

            # Remove disconnected clients
            self.websocket_clients -= disconnected

        except Exception as e:
            logger.error(f"Error broadcasting world update: {e}")

    async def start(self):
        """Start the monitor API server"""
        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, '0.0.0.0', self.port)
        await site.start()

        logger.info(f"Monitor API server started on port {self.port}")
        return runner

    async def stop(self, runner):
        """Stop the monitor API server"""
        await runner.cleanup()
        logger.info("Monitor API server stopped")