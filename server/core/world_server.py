"""
Main world server that runs the game loop and manages everything
"""

import asyncio
import time
import logging
import random
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
import json

from server.core.game_state import GameState, ServerEntity
from server.network.client_manager import ClientManager
from server.persistence.player_persistence import PlayerPersistence
from server.validation.bounds_checker import BoundsChecker
from server.validation.movement_validator import MovementValidator
from server.validation.action_validator import ActionValidator
from server.agents.agent_manager import AgentManager
from config.config_loader import config_loader
from shared.constants import (
    SERVER_TICK_RATE, WORLD_UPDATE_RATE, DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT, WORLD_WIDTH, WORLD_HEIGHT
)
from shared.messages import (
    MessageType, EventMessage, EventType, WorldUpdateMessage,
    EntityView, Protocol
)
from shared.math_utils import Vector2

logger = logging.getLogger(__name__)


class WorldServer:
    """Main game server"""

    def __init__(self, host: str = DEFAULT_SERVER_HOST, port: int = DEFAULT_SERVER_PORT, config_dir: str = "config"):
        self.host = host
        self.port = port
        self.running = False

        # Load configurations
        config_loader.config_dir = config_dir
        if not config_loader.load_all_configs():
            logger.warning("Failed to load some configurations, using defaults")

        self.world_config = config_loader.world_config
        self.agent_config = config_loader.agent_config
        self.server_config = config_loader.server_config

        # Override server settings from config
        if self.server_config:
            server_settings = self.server_config.server_settings
            self.host = server_settings.get('host', host)
            self.port = server_settings.get('port', port)

        # Core systems
        self.game_state = GameState()
        self.client_manager = ClientManager(self)
        self.persistence = PlayerPersistence()

        # Validation systems
        self.bounds_checker = BoundsChecker(self.world_config)
        self.movement_validator = MovementValidator(self.bounds_checker, self.server_config)
        self.action_validator = ActionValidator(self.server_config)

        # Agent management system
        self.agent_manager = AgentManager(self)

        # Lazy import to avoid circular imports
        self.action_handler = None
        self.query_handler = None

        # Timing (from config)
        game_settings = self.server_config.game_settings if self.server_config else {}
        self.tick_interval = 1.0 / game_settings.get('tick_rate', SERVER_TICK_RATE)
        self.update_interval = 1.0 / game_settings.get('world_update_rate', WORLD_UPDATE_RATE)
        self.last_update_time = 0

        # Server socket
        self.server = None

        # Load existing player data if available
        self._load_player_data()

        # Initialize world from config
        self._initialize_world_from_config()

        # Initialize monitor API variables
        self.monitor_api = None
        self.monitor_api_runner = None

        # Initialize handlers after everything else
        self._initialize_handlers()

        # Auto-save setup (from config)
        persistence_settings = self.server_config.persistence if self.server_config else {}
        self.last_save_time = 0
        self.save_interval = persistence_settings.get('auto_save_interval', 30.0)

        logger.info(f"WorldServer initialized on {self.host}:{self.port}")
        logger.info(f"Configuration loaded: World={bool(self.world_config)}, Agent={bool(self.agent_config)}, Server={bool(self.server_config)}")

    def _initialize_handlers(self):
        """Initialize handlers with lazy imports"""
        from server.api.action_handler import ActionHandler
        from server.api.query_handler import QueryHandler
        from server.api.monitor_api import MonitorAPI

        self.action_handler = ActionHandler(self.game_state)
        self.query_handler = QueryHandler(self.game_state)
        self.monitor_api = MonitorAPI(self.game_state, port=8080)
        logger.info("MonitorAPI initialized successfully")

    def _load_player_data(self):
        """Load existing player data if available"""
        if self.persistence.has_saved_data():
            save_info = self.persistence.get_save_info()
            if save_info:
                logger.info(f"Found saved player data from {save_info['save_time_str']}")
                logger.info(f"Players: {save_info['total_players']} total, {save_info['active_players']} active, {save_info['inactive_players']} inactive")

                if self.persistence.load_player_data(self.game_state):
                    logger.info("Successfully loaded player data")
                else:
                    logger.warning("Failed to load player data")
            else:
                logger.info("No valid saved player data found")
        else:
            logger.info("No saved player data found - starting fresh")

    def _initialize_world_from_config(self):
        """Set up initial world state from configuration"""
        if not self.world_config:
            # Fallback to basic world setup
            self._initialize_basic_world()
            return

        # Create NPCs from config
        for npc_config in self.world_config.npcs:
            entity = self.game_state.create_entity(
                name=npc_config.name,
                entity_type="npc",
                position=npc_config.position,
                level=npc_config.level,
                health=npc_config.health,
                max_health=npc_config.health,
                data={
                    'npc_type': npc_config.type,
                    'behavior': npc_config.behavior,
                    'services': npc_config.services,
                    'dialogue': npc_config.dialogue,
                    'patrol_radius': npc_config.patrol_radius,
                    'specialization': npc_config.specialization
                }
            )
            logger.info(f"Created NPC: {npc_config.name} ({npc_config.type})")

        # Create enemies from config
        for template_name, spawn_areas in self.world_config.enemies.items():
            enemy_template = self.world_config.enemy_templates.get(template_name)
            if not enemy_template:
                logger.warning(f"Enemy template '{template_name}' not found")
                continue

            for spawn_area in spawn_areas:
                for i in range(spawn_area.count):
                    # Random position within spawn area
                    import math
                    angle = random.uniform(0, 2 * 3.14159)
                    distance = random.uniform(0, spawn_area.radius)
                    position = Vector2(
                        spawn_area.center.x + distance * math.cos(angle),
                        spawn_area.center.y + distance * math.sin(angle)
                    )

                    # Ensure position is valid
                    position = self.bounds_checker.clamp_to_bounds(position)

                    # Random level within range
                    level = random.randint(*spawn_area.level_range)

                    # Create enemy
                    entity = self.game_state.create_entity(
                        name=f"{enemy_template.name_prefix}_{i}",
                        entity_type=enemy_template.entity_type,
                        position=position,
                        level=level,
                        health=enemy_template.base_health + (level - 1) * 10,
                        max_health=enemy_template.base_health + (level - 1) * 10,
                        data={
                            'template': template_name,
                            'base_damage': enemy_template.base_damage,
                            'move_speed': enemy_template.move_speed,
                            'aggro_range': enemy_template.aggro_range,
                            'ai_behavior': enemy_template.ai_behavior,
                            'loot_table': enemy_template.loot_table,
                            'spawn_area': spawn_area.center.to_tuple(),
                            'respawn_time': spawn_area.respawn_time
                        }
                    )

            logger.info(f"Created {sum(area.count for area in spawn_areas)} {template_name} enemies")

        # Create world objects from config
        for obj_config in self.world_config.objects:
            obj_type = obj_config.get('type', 'object')
            template_name = obj_config.get('template')

            if template_name and template_name in self.world_config.object_templates:
                template = self.world_config.object_templates[template_name]

                # Handle multiple positions for template objects
                positions = obj_config.get('positions', [obj_config.get('position', [0, 0])])

                for pos in positions:
                    entity = self.game_state.create_entity(
                        name=template.get('name', f"{template_name}_{len(positions)}"),
                        entity_type=obj_type,
                        position=Vector2.from_tuple(pos),
                        data={**template, 'template': template_name}
                    )
            else:
                # Create object directly from config
                entity = self.game_state.create_entity(
                    name=obj_config.get('name', 'Object'),
                    entity_type=obj_type,
                    position=Vector2.from_tuple(obj_config.get('position', [0, 0])),
                    data=obj_config
                )

        logger.info("World initialized from configuration")
        logger.info(f"Created {len(self.world_config.npcs)} NPCs, "
                   f"{sum(sum(area.count for area in areas) for areas in self.world_config.enemies.values())} enemies, "
                   f"{len(self.world_config.objects)} objects")

    def _initialize_basic_world(self):
        """Fallback world initialization without config"""
        # Create basic NPCs
        npcs = [
            {"name": "Merchant Bob", "position": Vector2(500, 500), "entity_type": "npc"},
            {"name": "Guard Tom", "position": Vector2(400, 400), "entity_type": "npc"},
            {"name": "Trainer Jane", "position": Vector2(600, 500), "entity_type": "npc"},
        ]

        for npc_data in npcs:
            self.game_state.create_entity(**npc_data)

        # Create basic enemies
        for i in range(20):
            self.game_state.create_entity(
                name=f"Goblin_{i}",
                entity_type="enemy",
                position=Vector2(
                    random.uniform(100, WORLD_WIDTH - 100),
                    random.uniform(100, WORLD_HEIGHT - 100)
                ),
                level=random.randint(1, 5),
                health=50,
                max_health=50
            )

        logger.info("Basic world initialized (no config)")

    async def start(self):
        """Start the server"""
        self.running = True

        # Start monitor API
        if self.monitor_api:
            logger.info("Starting Monitor API...")
            try:
                self.monitor_api_runner = await self.monitor_api.start()
                logger.info("Monitor API started on port 8080")
            except Exception as e:
                logger.error(f"Failed to start Monitor API: {e}")
        else:
            logger.warning("Monitor API is None - not starting")

        # Start agent management system
        await self.agent_manager.start()

        # Start network server
        self.server = await asyncio.start_server(
            self.client_manager.handle_client,
            self.host,
            self.port
        )

        logger.info(f"Server listening on {self.host}:{self.port}")

        # Run game loop
        asyncio.create_task(self._game_loop())

        # Keep server running
        async with self.server:
            await self.server.serve_forever()

    async def stop(self):
        """Stop the server"""
        self.running = False

        # Save player data before stopping
        try:
            self.persistence.save_player_data(self.game_state)
            logger.info("Player data saved on shutdown")
        except Exception as e:
            logger.error(f"Failed to save player data on shutdown: {e}")

        # Stop agent management
        self.agent_manager.stop()

        # Disconnect all clients
        await self.client_manager.disconnect_all()

        # Stop monitor API
        if self.monitor_api_runner:
            await self.monitor_api.stop(self.monitor_api_runner)

        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        logger.info("Server stopped")

    async def _game_loop(self):
        """Main game loop"""
        last_tick = time.perf_counter()

        while self.running:
            current_time = time.perf_counter()
            delta_time = current_time - last_tick

            if delta_time >= self.tick_interval:
                # Update game state
                self.game_state.update(delta_time)

                # Process NPC/Enemy AI
                await self._update_ai(delta_time)

                # Send world updates to clients
                if current_time - self.last_update_time >= self.update_interval:
                    await self._send_world_updates()

                    # Broadcast to monitor API clients
                    if self.monitor_api:
                        await self.monitor_api.broadcast_world_update()

                    self.last_update_time = current_time

                # Auto-save player data
                if current_time - self.last_save_time >= self.save_interval:
                    await self._auto_save()
                    self.last_save_time = current_time

                last_tick = current_time

            # Small sleep to prevent CPU spinning
            await asyncio.sleep(0.001)

    async def _update_ai(self, delta_time: float):
        """Update server-controlled entities"""
        for entity in self.game_state.entities.values():
            if entity.entity_type in ['npc', 'enemy']:
                # Simple AI behavior
                if entity.entity_type == 'enemy' and entity.alive:
                    # Find nearby agents to attack
                    nearby = self.game_state.get_entities_in_range(entity.position, 50)
                    for target in nearby:
                        if target.entity_type == 'agent' and target.alive:
                            # Move towards target
                            direction = (target.position - entity.position).normalize()
                            entity.velocity = direction * 30  # Move at 30 units/sec
                            entity.state = 'combat'
                            break
                    else:
                        # Random wandering
                        if entity.state != 'moving':
                            if random.random() < 0.01:  # 1% chance to start moving
                                entity.velocity = Vector2(
                                    random.uniform(-1, 1),
                                    random.uniform(-1, 1)
                                ).normalize() * 20
                                entity.state = 'moving'
                        elif random.random() < 0.02:  # 2% chance to stop
                            entity.velocity = Vector2(0, 0)
                            entity.state = 'idle'

    async def _send_world_updates(self):
        """Send world state updates to all clients"""
        for client_id, client_info in self.client_manager.clients.items():
            # Get agent's entity
            entity_id = self.game_state.agents.get(client_id)
            if not entity_id:
                continue

            entity = self.game_state.get_entity(entity_id)
            if not entity:
                continue

            # Get visible entities for this client
            visible_entities = self.game_state.get_visible_entities(entity_id)

            # Convert to client view format
            entity_views = []
            for e in visible_entities:
                view = EntityView(
                    id=e.id,
                    name=e.name,
                    entity_type=e.entity_type,
                    position=e.position.to_tuple(),
                    health_percentage=(e.health / e.max_health) * 100 if e.max_health > 0 else 0,
                    level=e.level,
                    state=e.state,
                    velocity=e.velocity.to_tuple() if e.velocity.magnitude() > 0 else None
                )
                entity_views.append(view.to_dict())

            # Create update message
            update = WorldUpdateMessage(
                tick=self.game_state.tick,
                visible_entities=entity_views
            )

            # Send to client
            await self.client_manager.send_to_client(client_id, update)

    async def broadcast_event(self, event: EventMessage, position: Optional[Vector2] = None):
        """Broadcast an event to relevant clients"""
        if position:
            # Send to clients near the event
            for client_id, client_info in self.client_manager.clients.items():
                entity_id = self.game_state.agents.get(client_id)
                if entity_id:
                    entity = self.game_state.get_entity(entity_id)
                    if entity and entity.position.distance_to(position) <= entity.vision_range * 2:
                        await self.client_manager.send_to_client(client_id, event)
        else:
            # Broadcast to all clients
            await self.client_manager.broadcast(event)

    def create_agent_entity(self, client_id: str, name: str, agent_class: str) -> ServerEntity:
        """Create a new agent entity for a client"""
        import random

        # Get spawn position from bounds checker
        spawn_pos = self.bounds_checker.get_nearest_safe_position(
            Vector2(random.uniform(400, 600), random.uniform(400, 600))
        )

        # Create entity
        entity = self.game_state.create_entity(
            name=name,
            entity_type="agent",
            position=spawn_pos,
            health=100,
            max_health=100,
            level=1,
            owner_id=client_id,
            data={'class': agent_class}
        )

        # Map to client
        self.game_state.agents[client_id] = entity.id

        # Notify agent manager
        self.agent_manager.on_agent_connected(client_id, entity.id)

        # Broadcast spawn event
        spawn_event = EventMessage(
            event=EventType.ENTITY_SPAWNED,
            data={
                'entity_id': entity.id,
                'name': name,
                'entity_type': 'agent',
                'position': entity.position.to_tuple()
            },
            position=entity.position.to_tuple()
        )
        asyncio.create_task(self.broadcast_event(spawn_event, entity.position))

        logger.info(f"Created agent entity {entity.id} for client {client_id}")
        return entity

    def remove_agent_entity(self, client_id: str):
        """Mark agent as inactive when client disconnects (don't destroy)"""
        entity_id = self.game_state.agents.get(client_id)
        if entity_id:
            entity = self.game_state.get_entity(entity_id)
            if entity:
                # Mark as inactive instead of destroying
                entity.is_active = False
                entity.velocity = Vector2(0, 0)  # Stop movement
                entity.state = "disconnected"

                # Broadcast disconnect event
                disconnect_event = EventMessage(
                    event=EventType.ENTITY_DESPAWNED,  # Use despawn for visual feedback
                    data={'entity_id': entity_id, 'disconnected': True},
                    position=entity.position.to_tuple()
                )
                asyncio.create_task(self.broadcast_event(disconnect_event, entity.position))

                # Notify agent manager
                self.agent_manager.on_agent_disconnected(client_id)

                logger.info(f"Marked agent entity {entity_id} for client {client_id} as inactive")

    async def _auto_save(self):
        """Auto-save player data"""
        try:
            if self.persistence.save_player_data(self.game_state):
                logger.debug("Auto-saved player data")
            else:
                logger.warning("Auto-save failed")
        except Exception as e:
            logger.error(f"Auto-save error: {e}")

    async def save_and_shutdown(self):
        """Save data before shutdown"""
        logger.info("Saving player data before shutdown...")
        if self.persistence.save_player_data(self.game_state):
            logger.info("Player data saved successfully")
        else:
            logger.warning("Failed to save player data")
        await self.stop()