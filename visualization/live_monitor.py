"""
Live server monitor with real-time visualization
"""

import pygame
import asyncio
import aiohttp
import json
import time
import math
import subprocess
import sys
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class EntityData:
    """Entity data for visualization"""
    id: str
    name: str
    entity_type: str
    position: tuple
    health_percentage: float
    level: int
    state: str
    is_active: bool = True
    velocity: Optional[tuple] = None

@dataclass
class AgentStats:
    """Agent management statistics"""
    total_agents: int
    connected_agents: int
    disconnected_agents: int
    queued_spawns: int
    template_distribution: Dict[str, int]
    max_agents: int

@dataclass
class WorldState:
    """Complete world state for visualization"""
    tick: int
    entities: Dict[str, EntityData]
    active_players: int
    inactive_players: int
    server_stats: Dict[str, Any]
    agent_stats: Optional[AgentStats]
    performance_metrics: Dict[str, Any]
    timestamp: float

class LiveServerMonitor:
    """Real-time server monitor with pygame visualization"""

    def __init__(self, server_host: str = "127.0.0.1", server_port: int = 5555, auto_start: bool = True):
        self.server_host = server_host
        self.server_port = server_port
        self.auto_start = auto_start

        # Server management
        self.server_process = None
        self.simulation_process = None
        self.simulation_task = None

        # Pygame setup
        pygame.init()
        self.width = 1200
        self.height = 800
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("MMO Server Live Monitor")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)

        # Colors
        self.colors = {
            'background': (20, 20, 30),
            'world_bg': (40, 40, 50),
            'grid': (60, 60, 70),
            'agent_active': (0, 255, 0),
            'agent_inactive': (128, 128, 128),
            'npc': (0, 150, 255),
            'enemy': (255, 50, 50),
            'object': (200, 200, 100),
            'text': (255, 255, 255),
            'ui_bg': (50, 50, 60),
            'border': (100, 100, 120)
        }

        # Layout areas
        self.world_area = pygame.Rect(10, 10, 700, 500)
        self.info_area = pygame.Rect(720, 10, 470, 380)
        self.agent_dashboard_area = pygame.Rect(10, 520, 700, 270)
        self.performance_area = pygame.Rect(720, 400, 470, 390)

        # Dashboard state
        self.selected_entity = None
        self.dashboard_scroll = 0
        self.show_trails = True
        self.show_agent_names = True
        self.performance_history = []
        self.max_history_length = 100

        # Calculate scale to fit 10000x10000 world into new world area
        self.world_scale = min(700.0 / 10000.0, 500.0 / 10000.0)  # Scale to fit entire world
        self.world_offset_x = 0
        self.world_offset_y = 0

        # Zoom and pan controls - start zoomed in on spawn area
        self.zoom_factor = 8.0  # Start zoomed in
        self.pan_x = -4500  # Center on spawn area (around 500, 500)
        self.pan_y = -4500
        self.dragging = False
        self.last_mouse_pos = None

        # Data
        self.world_state: Optional[WorldState] = None
        self.entity_history: Dict[str, List[tuple]] = {}  # Position history for trails
        self.running = True
        self.last_update = 0
        self.update_interval = 0.1  # Update 10 times per second
        self.using_mock_data = True  # Flag to track data source

        # HTTP session for server communication
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Start the monitor with auto-startup capabilities"""
        self.session = aiohttp.ClientSession()

        # Auto-start server and simulation if requested
        if self.auto_start:
            await self._auto_start_system()

        # Start update loop
        update_task = asyncio.create_task(self._update_loop())

        # Main display loop
        try:
            await self._display_loop()
        finally:
            update_task.cancel()
            await self._cleanup_processes()
            if self.session:
                await self.session.close()
            pygame.quit()

    async def _update_loop(self):
        """Continuously fetch world state from server"""
        while self.running:
            try:
                current_time = time.time()
                if current_time - self.last_update >= self.update_interval:
                    await self._fetch_world_state()
                    self.last_update = current_time

                await asyncio.sleep(0.05)  # Small sleep to prevent CPU spinning

            except Exception as e:
                logger.error(f"Error in update loop: {e}")
                await asyncio.sleep(1.0)

    async def _fetch_world_state(self):
        """Fetch current world state from server via HTTP API"""
        try:
            if self.session:
                # Try to fetch from real server first
                try:
                    url = f"http://{self.server_host}:8080/world"
                    async with self.session.get(url, timeout=1.0) as response:
                        if response.status == 200:
                            data = await response.json()
                            self.world_state = self._parse_server_data(data)
                            self.using_mock_data = False
                            return
                except Exception as e:
                    # If server is not available, fall back to mock data
                    logger.debug(f"Server not available, using mock data: {e}")

            # Fall back to mock world state for demonstration
            self.world_state = await self._create_mock_world_state()
            self.using_mock_data = True

        except Exception as e:
            logger.error(f"Failed to fetch world state: {e}")
            self.using_mock_data = True

    def _parse_server_data(self, data: dict) -> WorldState:
        """Parse server data into WorldState format"""
        entities = {}
        for entity_id, entity_data in data['entities'].items():
            entities[entity_id] = EntityData(
                id=entity_data['id'],
                name=entity_data['name'],
                entity_type=entity_data['entity_type'],
                position=tuple(entity_data['position']),
                health_percentage=entity_data['health_percentage'],
                level=entity_data['level'],
                state=entity_data['state'],
                is_active=entity_data.get('is_active', True),
                velocity=tuple(entity_data['velocity']) if entity_data.get('velocity') else None
            )

        # Parse agent stats if available
        agent_stats = None
        if 'agent_stats' in data:
            agent_data = data['agent_stats']
            agent_stats = AgentStats(
                total_agents=agent_data.get('total_agents', 0),
                connected_agents=agent_data.get('connected_agents', 0),
                disconnected_agents=agent_data.get('disconnected_agents', 0),
                queued_spawns=agent_data.get('queued_spawns', 0),
                template_distribution=agent_data.get('template_distribution', {}),
                max_agents=agent_data.get('max_agents', 50)
            )

        return WorldState(
            tick=data['tick'],
            entities=entities,
            active_players=data['active_players'],
            inactive_players=data['inactive_players'],
            server_stats=data['server_stats'],
            agent_stats=agent_stats,
            performance_metrics=data.get('performance_metrics', {}),
            timestamp=data['timestamp']
        )

    async def _create_mock_world_state(self) -> WorldState:
        """Create mock world state for demonstration - REALISTIC version"""
        current_time = time.time()

        # Create some mock entities
        entities = {}

        # Mock agents - FIXED to respect persistence rules
        for i in range(6):
            agent_id = f"mock_agent_{i}"
            is_active = i < 4  # First 4 are active

            if is_active:
                # Active agents move slowly and realistically
                t = current_time * 0.1 + i  # Slow movement
                base_x = 500 + i * 50  # Spread them out
                base_y = 500 + (i % 2) * 100

                # Small wandering movement for active agents
                x = base_x + 30 * math.cos(t)
                y = base_y + 30 * math.sin(t)
                velocity = (3 * math.cos(t), 3 * math.sin(t))  # Realistic speed
                state = "moving"
            else:
                # Inactive agents are STATIONARY
                x = 400 + i * 100
                y = 600
                velocity = None
                state = "disconnected"

            entities[agent_id] = EntityData(
                id=agent_id,
                name=f"MockPlayer_{i}",
                entity_type="agent",
                position=(x, y),
                health_percentage=100.0,  # No artificial health changes
                level=random_level(),
                state=state,
                is_active=is_active,
                velocity=velocity
            )

        # Mock NPCs - stationary
        npc_positions = [(400, 400), (600, 600), (300, 700)]
        for i, pos in enumerate(npc_positions):
            npc_id = f"mock_npc_{i}"
            entities[npc_id] = EntityData(
                id=npc_id,
                name=f"MockNPC_{i}",
                entity_type="npc",
                position=pos,
                health_percentage=100.0,
                level=10,
                state="idle"
            )

        # Mock agent stats
        agent_stats = AgentStats(
            total_agents=6,
            connected_agents=4,
            disconnected_agents=2,
            queued_spawns=1,
            template_distribution={'explorer': 3, 'warrior': 2, 'merchant': 1},
            max_agents=20
        )

        return WorldState(
            tick=int(current_time * 60),  # Mock 60 Hz
            entities=entities,
            active_players=4,
            inactive_players=2,
            server_stats={
                'entities_created': 9,  # Realistic count
                'entities_destroyed': 0,
                'total_damage': 0.0,
                'total_healing': 0.0
            },
            agent_stats=agent_stats,
            performance_metrics={
                'fps': 60.0,
                'memory_usage_mb': 125.6,
                'active_connections': 4,
                'messages_per_second': 42.3
            },
            timestamp=current_time
        )

    async def _display_loop(self):
        """Main display loop"""
        while self.running:
            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        # Reset zoom and pan
                        self.zoom_factor = 1.0
                        self.pan_x = 0
                        self.pan_y = 0
                    elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        # Zoom in
                        self.zoom_factor = min(self.zoom_factor * 1.2, 10.0)
                    elif event.key == pygame.K_MINUS:
                        # Zoom out
                        self.zoom_factor = max(self.zoom_factor / 1.2, 0.1)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        if self.world_area.collidepoint(event.pos):
                            self.dragging = True
                            self.last_mouse_pos = event.pos
                        else:
                            await self._handle_mouse_click(event.pos)
                    elif event.button == 4:  # Mouse wheel up
                        self.zoom_factor = min(self.zoom_factor * 1.1, 10.0)
                    elif event.button == 5:  # Mouse wheel down
                        self.zoom_factor = max(self.zoom_factor / 1.1, 0.1)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:  # Left click release
                        self.dragging = False
                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging and self.last_mouse_pos:
                        # Pan the view
                        dx = event.pos[0] - self.last_mouse_pos[0]
                        dy = event.pos[1] - self.last_mouse_pos[1]

                        # Convert screen movement to world movement
                        world_dx = dx / (self.world_scale * self.zoom_factor)
                        world_dy = dy / (self.world_scale * self.zoom_factor)

                        self.pan_x += world_dx
                        self.pan_y += world_dy

                        self.last_mouse_pos = event.pos

            # Clear screen
            self.screen.fill(self.colors['background'])

            # Draw world view
            self._draw_world()

            # Draw info panel
            self._draw_info_panel()

            # Draw agent dashboard
            self._draw_agent_dashboard()

            # Draw performance metrics
            self._draw_performance_metrics()

            # Update display
            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS

            # Allow other coroutines to run
            await asyncio.sleep(0.001)

    def _draw_world(self):
        """Draw the world view with entities"""
        # Draw world background
        pygame.draw.rect(self.screen, self.colors['world_bg'], self.world_area)
        pygame.draw.rect(self.screen, self.colors['border'], self.world_area, 2)

        # Draw grid
        self._draw_grid()

        if not self.world_state:
            # Draw "No Data" message
            text = self.font.render("Waiting for server data...", True, self.colors['text'])
            text_rect = text.get_rect(center=self.world_area.center)
            self.screen.blit(text, text_rect)
            return

        # Draw entity trails first (under entities)
        if self.show_trails:
            self._draw_entity_trails()

        # Draw entities
        for entity in self.world_state.entities.values():
            self._draw_entity(entity)

        # Draw selection highlight
        if self.selected_entity:
            self._draw_entity_selection(self.selected_entity)

        # Draw legend
        self._draw_legend()

    def _draw_grid(self):
        """Draw background grid"""
        # World grid spacing (in world units)
        world_grid_size = 1000  # 1000 unit grid

        # Calculate screen grid spacing
        screen_grid_size = world_grid_size * self.world_scale * self.zoom_factor

        # Skip grid if too small or too large
        if screen_grid_size < 10 or screen_grid_size > 200:
            return

        # Calculate starting positions
        start_world_x = -self.pan_x
        start_world_y = -self.pan_y

        # Calculate grid offset
        grid_offset_x = (start_world_x % world_grid_size) * self.world_scale * self.zoom_factor
        grid_offset_y = (start_world_y % world_grid_size) * self.world_scale * self.zoom_factor

        # Draw vertical lines
        x = self.world_area.x - grid_offset_x
        while x < self.world_area.x + self.world_area.width:
            if x >= self.world_area.x:
                start_pos = (int(x), self.world_area.y)
                end_pos = (int(x), self.world_area.y + self.world_area.height)
                pygame.draw.line(self.screen, self.colors['grid'], start_pos, end_pos, 1)
            x += screen_grid_size

        # Draw horizontal lines
        y = self.world_area.y - grid_offset_y
        while y < self.world_area.y + self.world_area.height:
            if y >= self.world_area.y:
                start_pos = (self.world_area.x, int(y))
                end_pos = (self.world_area.x + self.world_area.width, int(y))
                pygame.draw.line(self.screen, self.colors['grid'], start_pos, end_pos, 1)
            y += screen_grid_size

    def _world_to_screen(self, world_pos: tuple) -> tuple:
        """Convert world coordinates to screen coordinates"""
        x, y = world_pos

        # Apply zoom and pan
        scaled_x = (x + self.pan_x) * self.world_scale * self.zoom_factor
        scaled_y = (y + self.pan_y) * self.world_scale * self.zoom_factor

        screen_x = self.world_area.x + scaled_x
        screen_y = self.world_area.y + scaled_y
        return (int(screen_x), int(screen_y))

    def _draw_entity(self, entity: EntityData):
        """Draw a single entity"""
        screen_pos = self._world_to_screen(entity.position)

        # Skip if outside view area
        if not self.world_area.collidepoint(screen_pos):
            return

        # Choose color based on entity type and state
        if entity.entity_type == "agent":
            color = self.colors['agent_active'] if entity.is_active else self.colors['agent_inactive']
            size = 8
        elif entity.entity_type == "npc":
            color = self.colors['npc']
            size = 6
        elif entity.entity_type == "enemy":
            color = self.colors['enemy']
            size = 5
        else:
            color = self.colors['object']
            size = 4

        # Draw entity
        pygame.draw.circle(self.screen, color, screen_pos, size)

        # Draw health bar for living entities
        if entity.entity_type in ['agent', 'enemy'] and entity.health_percentage < 100:
            self._draw_health_bar(screen_pos, entity.health_percentage, size)

        # Draw name for agents (if enabled)
        if entity.entity_type == "agent" and self.show_agent_names:
            name_text = self.small_font.render(entity.name, True, self.colors['text'])
            name_pos = (screen_pos[0] - name_text.get_width() // 2, screen_pos[1] - size - 15)
            self.screen.blit(name_text, name_pos)

        # Update entity trail history
        if entity.entity_type == "agent" and entity.is_active:
            if entity.id not in self.entity_history:
                self.entity_history[entity.id] = []

            history = self.entity_history[entity.id]
            history.append((entity.position, time.time()))

            # Keep only recent history (last 50 positions)
            if len(history) > 50:
                history.pop(0)

        # Draw velocity vector
        if entity.velocity and entity.is_active:
            self._draw_velocity_vector(screen_pos, entity.velocity)

    def _draw_health_bar(self, pos: tuple, health_pct: float, entity_size: int):
        """Draw health bar above entity"""
        bar_width = entity_size * 3
        bar_height = 3
        bar_x = pos[0] - bar_width // 2
        bar_y = pos[1] - entity_size - 8

        # Background
        bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        pygame.draw.rect(self.screen, (50, 50, 50), bg_rect)

        # Health
        health_width = int(bar_width * health_pct / 100)
        if health_width > 0:
            health_rect = pygame.Rect(bar_x, bar_y, health_width, bar_height)
            health_color = (255, 0, 0) if health_pct < 30 else (255, 255, 0) if health_pct < 70 else (0, 255, 0)
            pygame.draw.rect(self.screen, health_color, health_rect)

    def _draw_velocity_vector(self, pos: tuple, velocity: tuple):
        """Draw velocity vector as an arrow"""
        vx, vy = velocity
        magnitude = math.sqrt(vx*vx + vy*vy)
        if magnitude < 0.1:
            return

        # Scale velocity for display
        scale = 2.0
        end_x = pos[0] + vx * scale
        end_y = pos[1] + vy * scale

        pygame.draw.line(self.screen, (255, 255, 0), pos, (int(end_x), int(end_y)), 2)

    def _draw_legend(self):
        """Draw entity type legend"""
        legend_x = self.world_area.x + 10
        legend_y = self.world_area.y + self.world_area.height - 100

        legend_items = [
            ("Active Player", self.colors['agent_active']),
            ("Inactive Player", self.colors['agent_inactive']),
            ("NPC", self.colors['npc']),
            ("Enemy", self.colors['enemy'])
        ]

        for i, (label, color) in enumerate(legend_items):
            y = legend_y + i * 20
            pygame.draw.circle(self.screen, color, (legend_x + 10, y + 8), 5)
            text = self.small_font.render(label, True, self.colors['text'])
            self.screen.blit(text, (legend_x + 25, y))

    def _draw_entity_trails(self):
        """Draw movement trails for agents"""
        current_time = time.time()

        for entity_id, history in self.entity_history.items():
            if len(history) < 2:
                continue

            # Filter recent positions
            recent_history = [
                (pos, timestamp) for pos, timestamp in history
                if current_time - timestamp < 30  # Show last 30 seconds
            ]

            if len(recent_history) < 2:
                continue

            # Draw trail
            points = []
            for i, (pos, timestamp) in enumerate(recent_history):
                screen_pos = self._world_to_screen(pos)
                if self.world_area.collidepoint(screen_pos):
                    points.append(screen_pos)

            if len(points) > 1:
                # Draw fading trail
                for i in range(len(points) - 1):
                    alpha = int(255 * (i / len(points)) * 0.5)  # Fade out older points
                    color = (0, 255, 255, alpha)  # Cyan trail
                    if alpha > 10:  # Only draw if visible
                        pygame.draw.line(self.screen, color[:3], points[i], points[i + 1], 1)

    def _draw_entity_selection(self, entity: EntityData):
        """Draw selection highlight around entity"""
        screen_pos = self._world_to_screen(entity.position)

        if not self.world_area.collidepoint(screen_pos):
            return

        # Draw selection circle
        pygame.draw.circle(self.screen, (255, 255, 0), screen_pos, 12, 2)

        # Draw selection info
        info_text = f"{entity.name} ({entity.entity_type}) - Level {entity.level}"
        text_surface = self.small_font.render(info_text, True, (255, 255, 255))

        # Position info text above the entity
        text_x = screen_pos[0] - text_surface.get_width() // 2
        text_y = screen_pos[1] - 30

        # Background for text
        text_bg = pygame.Rect(text_x - 5, text_y - 2,
                             text_surface.get_width() + 10,
                             text_surface.get_height() + 4)
        pygame.draw.rect(self.screen, (0, 0, 0, 180), text_bg)
        pygame.draw.rect(self.screen, (255, 255, 0), text_bg, 1)

        self.screen.blit(text_surface, (text_x, text_y))

    def _draw_info_panel(self):
        """Draw information panel"""
        # Background
        pygame.draw.rect(self.screen, self.colors['ui_bg'], self.info_area)
        pygame.draw.rect(self.screen, self.colors['border'], self.info_area, 2)

        if not self.world_state:
            return

        y = self.info_area.y + 10
        line_height = 25

        # Server Info
        self._draw_text("SERVER STATUS", y, bold=True)
        y += line_height

        # Data source indicator
        data_source = "MOCK DATA" if self.using_mock_data else "LIVE SERVER"
        source_color = (255, 100, 100) if self.using_mock_data else (100, 255, 100)
        self._draw_text_color(f"Data Source: {data_source}", self.info_area.x + 10, y, source_color)
        y += line_height

        self._draw_text(f"Tick: {self.world_state.tick}", y)
        y += line_height
        self._draw_text(f"Active Players: {self.world_state.active_players}", y)
        y += line_height
        self._draw_text(f"Inactive Players: {self.world_state.inactive_players}", y)
        y += line_height
        self._draw_text(f"Total Entities: {len(self.world_state.entities)}", y)
        y += line_height * 2

        # View Info
        self._draw_text("VIEW INFO", y, bold=True)
        y += line_height
        self._draw_text(f"Zoom: {self.zoom_factor:.1f}x", y)
        y += line_height
        self._draw_text(f"Pan: ({self.pan_x:.0f}, {self.pan_y:.0f})", y)
        y += line_height
        self._draw_text(f"World: 10000x10000", y)
        y += line_height * 2

        # Stats
        self._draw_text("SERVER STATS", y, bold=True)
        y += line_height
        for key, value in self.world_state.server_stats.items():
            display_key = key.replace('_', ' ').title()
            self._draw_text(f"{display_key}: {value}", y)
            y += line_height

        y += line_height

        # Entity counts by type
        self._draw_text("ENTITY BREAKDOWN", y, bold=True)
        y += line_height

        type_counts = {}
        active_counts = {}
        for entity in self.world_state.entities.values():
            type_counts[entity.entity_type] = type_counts.get(entity.entity_type, 0) + 1
            if entity.entity_type == "agent":
                if entity.is_active:
                    active_counts["active"] = active_counts.get("active", 0) + 1
                else:
                    active_counts["inactive"] = active_counts.get("inactive", 0) + 1

        for entity_type, count in type_counts.items():
            display_type = entity_type.title() + "s"
            self._draw_text(f"{display_type}: {count}", y)
            y += line_height

        # Controls
        y += line_height
        self._draw_text("CONTROLS", y, bold=True)
        y += line_height
        self._draw_text("ESC - Exit", y)
        y += line_height
        self._draw_text("SPACE - Reset view", y)
        y += line_height
        self._draw_text("+/- - Zoom in/out", y)
        y += line_height
        self._draw_text("Mouse wheel - Zoom", y)
        y += line_height
        self._draw_text("Drag - Pan view", y)
        y += line_height
        self._draw_text("Click - Select entity", y)

    def _draw_text(self, text: str, y: int, bold: bool = False):
        """Draw text in the info panel"""
        font = self.font if bold else self.small_font
        color = (255, 255, 100) if bold else self.colors['text']
        text_surface = font.render(text, True, color)
        self.screen.blit(text_surface, (self.info_area.x + 10, y))

    def _draw_text_color(self, text: str, y: int, color: tuple):
        """Draw text in the info panel with custom color"""
        text_surface = self.small_font.render(text, True, color)
        self.screen.blit(text_surface, (self.info_area.x + 10, y))

    def _draw_agent_dashboard(self):
        """Draw agent management dashboard"""
        # Background
        pygame.draw.rect(self.screen, self.colors['ui_bg'], self.agent_dashboard_area)
        pygame.draw.rect(self.screen, self.colors['border'], self.agent_dashboard_area, 2)

        if not self.world_state or not self.world_state.agent_stats:
            self._draw_text_in_area("No agent data available", self.agent_dashboard_area, 10, 10)
            return

        agent_stats = self.world_state.agent_stats
        x = self.agent_dashboard_area.x + 10
        y = self.agent_dashboard_area.y + 10
        line_height = 20

        # Title
        self._draw_text_bold("AGENT MANAGEMENT DASHBOARD", x, y)
        y += line_height * 1.5

        # Agent statistics
        col1_x = x
        col2_x = x + 250
        col3_x = x + 500

        # Column 1: Basic stats
        self._draw_text(f"Total Agents: {agent_stats.total_agents}", col1_x, y)
        y += line_height
        self._draw_text(f"Connected: {agent_stats.connected_agents}", col1_x, y)
        y += line_height
        self._draw_text(f"Disconnected: {agent_stats.disconnected_agents}", col1_x, y)
        y += line_height
        self._draw_text(f"Queued Spawns: {agent_stats.queued_spawns}", col1_x, y)
        y += line_height
        self._draw_text(f"Max Capacity: {agent_stats.max_agents}", col1_x, y)

        # Column 2: Template distribution
        y = self.agent_dashboard_area.y + 10 + line_height * 1.5
        self._draw_text_bold("Agent Types:", col2_x, y)
        y += line_height

        for template, count in agent_stats.template_distribution.items():
            color = self.colors['text']
            if count > 0:
                color = (100, 255, 100)  # Green for active types
            self._draw_text_color(f"{template.title()}: {count}", col2_x, y, color)
            y += line_height

        # Column 3: Capacity visualization
        y = self.agent_dashboard_area.y + 10 + line_height * 1.5
        self._draw_text_bold("Capacity:", col3_x, y)
        y += line_height

        # Draw capacity bar
        bar_width = 150
        bar_height = 20
        bar_x = col3_x
        bar_y = y + 5

        # Background bar
        pygame.draw.rect(self.screen, (50, 50, 50),
                        pygame.Rect(bar_x, bar_y, bar_width, bar_height))

        # Fill based on connected agents
        if agent_stats.max_agents > 0:
            fill_width = int(bar_width * agent_stats.connected_agents / agent_stats.max_agents)
            fill_color = (0, 255, 0) if fill_width < bar_width * 0.8 else (255, 255, 0)
            if fill_width > bar_width * 0.9:
                fill_color = (255, 0, 0)

            pygame.draw.rect(self.screen, fill_color,
                           pygame.Rect(bar_x, bar_y, fill_width, bar_height))

        # Capacity text
        capacity_text = f"{agent_stats.connected_agents}/{agent_stats.max_agents}"
        self._draw_text(capacity_text, col3_x, y + 30)

        # Activity visualization
        y += 60
        self._draw_text_bold("Recent Activity:", col1_x, y)
        y += line_height

        # Draw simple activity indicators based on connected vs total
        activity_indicators = []
        for i in range(min(20, agent_stats.total_agents)):
            indicator_x = col1_x + (i * 15)
            indicator_y = y + 5
            color = (0, 255, 0) if i < agent_stats.connected_agents else (100, 100, 100)
            pygame.draw.circle(self.screen, color, (indicator_x, indicator_y), 5)

    def _draw_performance_metrics(self):
        """Draw performance metrics and charts"""
        # Background
        pygame.draw.rect(self.screen, self.colors['ui_bg'], self.performance_area)
        pygame.draw.rect(self.screen, self.colors['border'], self.performance_area, 2)

        if not self.world_state:
            return

        x = self.performance_area.x + 10
        y = self.performance_area.y + 10
        line_height = 20

        # Title
        self._draw_text_bold("PERFORMANCE METRICS", x, y)
        y += line_height * 1.5

        # Current metrics
        metrics = self.world_state.performance_metrics
        self._draw_text(f"Server FPS: {metrics.get('fps', 'N/A')}", x, y)
        y += line_height
        self._draw_text(f"Memory: {metrics.get('memory_usage_mb', 'N/A')} MB", x, y)
        y += line_height
        self._draw_text(f"Connections: {metrics.get('active_connections', 'N/A')}", x, y)
        y += line_height
        self._draw_text(f"Msg/sec: {metrics.get('messages_per_second', 'N/A')}", x, y)
        y += line_height * 2

        # Performance history chart
        if len(self.performance_history) > 1:
            self._draw_text_bold("Performance History:", x, y)
            y += line_height

            chart_area = pygame.Rect(x, y, 400, 150)
            self._draw_performance_chart(chart_area)

        # Update performance history
        if self.world_state.performance_metrics:
            self.performance_history.append({
                'timestamp': self.world_state.timestamp,
                'fps': metrics.get('fps', 0),
                'memory': metrics.get('memory_usage_mb', 0),
                'connections': metrics.get('active_connections', 0)
            })

            # Keep only recent history
            if len(self.performance_history) > self.max_history_length:
                self.performance_history.pop(0)

    def _draw_performance_chart(self, area: pygame.Rect):
        """Draw a simple performance chart"""
        if len(self.performance_history) < 2:
            return

        # Draw chart background
        pygame.draw.rect(self.screen, (30, 30, 40), area)
        pygame.draw.rect(self.screen, self.colors['border'], area, 1)

        # Prepare data
        fps_values = [entry['fps'] for entry in self.performance_history]
        if not fps_values or max(fps_values) == 0:
            return

        # Draw FPS line
        max_fps = max(fps_values)
        min_fps = min(fps_values)
        fps_range = max_fps - min_fps if max_fps != min_fps else 1

        points = []
        for i, fps in enumerate(fps_values):
            x = area.x + (i / len(fps_values)) * area.width
            y = area.y + area.height - ((fps - min_fps) / fps_range) * area.height
            points.append((int(x), int(y)))

        if len(points) > 1:
            pygame.draw.lines(self.screen, (0, 255, 0), False, points, 2)

        # Draw target FPS line (60 FPS)
        if max_fps > 60:
            target_y = area.y + area.height - ((60 - min_fps) / fps_range) * area.height
            pygame.draw.line(self.screen, (255, 255, 0),
                           (area.x, int(target_y)), (area.x + area.width, int(target_y)), 1)

    def _draw_text_in_area(self, text: str, area: pygame.Rect, offset_x: int, offset_y: int):
        """Draw text within a specific area"""
        text_surface = self.small_font.render(text, True, self.colors['text'])
        self.screen.blit(text_surface, (area.x + offset_x, area.y + offset_y))

    def _draw_text_bold(self, text: str, x: int, y: int):
        """Draw bold text"""
        text_surface = self.font.render(text, True, (255, 255, 100))
        self.screen.blit(text_surface, (x, y))

    def _draw_text_color(self, text: str, x: int, y: int, color: tuple):
        """Draw text with custom color"""
        text_surface = self.small_font.render(text, True, color)
        self.screen.blit(text_surface, (x, y))

    async def _handle_mouse_click(self, pos: tuple):
        """Handle mouse clicks on entities"""
        if not self.world_area.collidepoint(pos):
            return

        # Convert screen to world coordinates
        rel_x = pos[0] - self.world_area.x
        rel_y = pos[1] - self.world_area.y
        world_x = (rel_x / self.world_scale) - self.world_offset_x
        world_y = (rel_y / self.world_scale) - self.world_offset_y

        # Find clicked entity
        click_range = 20 / self.world_scale  # 20 pixel click radius

        if self.world_state:
            for entity in self.world_state.entities.values():
                ex, ey = entity.position
                distance = math.sqrt((ex - world_x)**2 + (ey - world_y)**2)
                if distance <= click_range:
                    self.selected_entity = entity
                    logger.info(f"Selected {entity.name} ({entity.entity_type}) at {entity.position}")
                    break

    async def _auto_start_system(self):
        """Auto-start server and simulation if needed"""
        print("🔄 Checking for existing server...")

        # Check if server is already running
        server_running = await self._check_server_status()

        if not server_running:
            print("🚀 Starting server...")
            await self._start_server()
            # Wait for server to be ready
            await asyncio.sleep(2)

            # Verify server started
            if not await self._check_server_status():
                print("❌ Failed to start server!")
                return
        else:
            print("✅ Server already running")

        # Check for existing player data
        player_data_exists = await self._check_player_data()
        if player_data_exists:
            print("📊 Found existing player data - will resume from last state")
        else:
            print("🆕 No existing player data - starting fresh")

        # Start simulation
        print("🎮 Starting test simulation...")
        await self._start_simulation()

    async def _check_server_status(self) -> bool:
        """Check if server is responding"""
        try:
            if self.session:
                url = f"http://{self.server_host}:8080/status"
                async with self.session.get(url, timeout=2.0) as response:
                    return response.status == 200
        except Exception:
            return False
        return False

    async def _check_player_data(self) -> bool:
        """Check if player persistence data exists"""
        try:
            # Check for persistence data
            persistence_file = 'output/persistence/player_data.json'
            world_state_file = 'output/persistence/world_state.json'

            if os.path.exists(persistence_file) and os.path.exists(world_state_file):
                # Get save info
                try:
                    import json
                    with open(world_state_file, 'r') as f:
                        world_data = json.load(f)
                    with open(persistence_file, 'r') as f:
                        player_data = json.load(f)

                    save_time = world_data.get('save_timestamp', 0)
                    player_count = len(player_data)

                    if player_count > 0:
                        print(f"📊 Found {player_count} saved players from {time.ctime(save_time)}")
                        return True
                except Exception as e:
                    print(f"⚠️  Error reading save data: {e}")

            # Also check for simulation output files (legacy)
            output_dirs = [d for d in os.listdir('output') if d.startswith('simulation_') and os.path.isdir(os.path.join('output', d))]
            if len(output_dirs) > 0:
                print(f"📁 Found {len(output_dirs)} simulation output directories")
                return True

            return False
        except Exception:
            return False

    async def _start_server(self):
        """Start the server process"""
        try:
            self.server_process = subprocess.Popen(
                [sys.executable, 'run_server.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd()
            )
            print(f"✅ Server started with PID {self.server_process.pid}")
        except Exception as e:
            print(f"❌ Failed to start server: {e}")

    async def _start_simulation(self):
        """Start the test simulation"""
        try:
            # Start simulation as background task
            self.simulation_task = asyncio.create_task(self._run_simulation())
            print("✅ Test simulation started")
        except Exception as e:
            print(f"❌ Failed to start simulation: {e}")

    async def _run_simulation(self):
        """Run the quick agent test simulation"""
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, 'quick_agent_test.py',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.getcwd()
            )

            # Read output occasionally to prevent blocking
            async def read_output():
                while True:
                    try:
                        line = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
                        if not line:
                            break
                        logger.debug(f"Simulation: {line.decode().strip()}")
                    except asyncio.TimeoutError:
                        continue
                    except Exception:
                        break

            output_task = asyncio.create_task(read_output())
            await process.wait()
            output_task.cancel()

        except Exception as e:
            logger.error(f"Simulation error: {e}")

    async def _cleanup_processes(self):
        """Clean up spawned processes"""
        if self.simulation_task and not self.simulation_task.done():
            self.simulation_task.cancel()
            try:
                await self.simulation_task
            except asyncio.CancelledError:
                pass

        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                print("✅ Server stopped")
            except Exception as e:
                print(f"⚠️  Error stopping server: {e}")
                try:
                    self.server_process.kill()
                except Exception:
                    pass

def random_level() -> int:
    """Generate random level for demo"""
    import random
    return random.randint(1, 10)

async def main():
    """Main entry point for live monitor"""
    monitor = LiveServerMonitor(auto_start=True)

    print("""
    ╔══════════════════════════════════════════╗
    ║         MMO SERVER LIVE MONITOR         ║
    ║                                          ║
    ║  Auto-starting server and simulation...  ║
    ║  Press ESC to exit                       ║
    ╚══════════════════════════════════════════╝
    """)

    try:
        await monitor.start()
    except KeyboardInterrupt:
        print("\nMonitor interrupted by user")
    except Exception as e:
        print(f"Monitor error: {e}")
        logger.error(f"Monitor error: {e}", exc_info=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())