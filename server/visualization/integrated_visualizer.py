"""
Integrated visualizer that runs in the same process as the server
"""

import asyncio
import logging
import math
import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any, Dict, List, Optional

import pygame

logger = logging.getLogger(__name__)


@dataclass
class VisualizationData:
    """Data packet for visualization updates"""

    tick: int
    entities: Dict[str, Dict[str, Any]]
    active_players: int
    inactive_players: int
    server_stats: Dict[str, Any]
    performance_metrics: Dict[str, Any]
    timestamp: float


class IntegratedVisualizer:
    """Integrated server visualizer that runs in the same process"""

    def __init__(self, game_state):
        self.game_state = game_state
        self.running = False
        self.visualization_thread = None
        self.update_queue = Queue(maxsize=100)

        # Pygame will be initialized in the visualization thread
        self.screen = None
        self.clock = None
        self.width = 1200
        self.height = 800

        # Colors
        self.colors = {
            "background": (20, 20, 30),
            "world_bg": (40, 40, 50),
            "grid": (60, 60, 70),
            "agent_active": (0, 255, 0),
            "agent_inactive": (128, 128, 128),
            "npc": (0, 150, 255),
            "enemy": (255, 50, 50),
            "object": (200, 200, 100),
            "text": (255, 255, 255),
            "ui_bg": (50, 50, 60),
            "border": (100, 100, 120),
        }

        # Layout areas (will be initialized after pygame)
        self.world_area = None
        self.info_area = None
        self.stats_area = None
        self.performance_area = None

        # Visualization state
        self.current_data = None
        self.entity_history = {}
        self.performance_history = []
        self.max_history_length = 100

        # Camera controls
        self.zoom_factor = 8.0  # Start zoomed in
        self.pan_x = -4500  # Center on spawn area
        self.pan_y = -4500
        self.dragging = False
        self.last_mouse_pos = None
        self.world_scale = 700.0 / 10000.0  # Scale to fit world

        # Display options
        self.show_trails = True
        self.show_agent_names = True
        self.selected_entity = None

    def start(self):
        """Start the visualizer in a separate thread"""
        if self.running:
            return

        self.running = True
        self.visualization_thread = threading.Thread(
            target=self._run_visualization, daemon=True
        )
        self.visualization_thread.start()
        logger.info("Integrated visualizer started")

    def stop(self):
        """Stop the visualizer"""
        self.running = False
        if self.visualization_thread:
            self.visualization_thread.join(timeout=2.0)
        logger.info("Integrated visualizer stopped")

    def update(self, data: VisualizationData):
        """Queue an update for the visualizer"""
        if not self.running:
            return

        try:
            # Non-blocking put, drop old updates if queue is full
            if self.update_queue.full():
                try:
                    self.update_queue.get_nowait()
                except Empty:
                    pass
            self.update_queue.put_nowait(data)
        except Exception as e:
            logger.debug(f"Failed to queue visualization update: {e}")

    def _run_visualization(self):
        """Main visualization loop (runs in separate thread)"""
        try:
            # Initialize pygame in this thread
            logger.info("Initializing pygame...")
            pygame.init()
            logger.info(f"Creating display: {self.width}x{self.height}")
            self.screen = pygame.display.set_mode((self.width, self.height))
            pygame.display.set_caption("MMO Server - Integrated Visualizer")
            self.clock = pygame.time.Clock()
            self.font = pygame.font.Font(None, 24)
            self.small_font = pygame.font.Font(None, 18)
            logger.info("Pygame display created successfully")

            # Initialize layout areas
            self.world_area = pygame.Rect(10, 10, 700, 500)
            self.info_area = pygame.Rect(720, 10, 470, 250)
            self.stats_area = pygame.Rect(720, 270, 470, 240)
            self.performance_area = pygame.Rect(10, 520, 1180, 270)

            while self.running:
                # Process pygame events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self._handle_key_event(event)
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        self._handle_mouse_down(event)
                    elif event.type == pygame.MOUSEBUTTONUP:
                        self._handle_mouse_up(event)
                    elif event.type == pygame.MOUSEMOTION:
                        self._handle_mouse_motion(event)

                # Get latest update from queue
                self._process_updates()

                # Render frame
                self._render_frame()

                # Control frame rate
                self.clock.tick(60)

        except Exception as e:
            logger.error(f"Visualization thread error: {e}")
        finally:
            pygame.quit()

    def _process_updates(self):
        """Process all pending updates from the queue"""
        # Get all available updates, keep only the latest
        latest_data = None
        while True:
            try:
                latest_data = self.update_queue.get_nowait()
            except Empty:
                break

        if latest_data:
            self.current_data = latest_data
            # Update performance history
            if latest_data.performance_metrics:
                self.performance_history.append(
                    {
                        "timestamp": latest_data.timestamp,
                        "fps": latest_data.performance_metrics.get("fps", 0),
                        "memory": latest_data.performance_metrics.get(
                            "memory_usage_mb", 0
                        ),
                        "connections": latest_data.performance_metrics.get(
                            "active_connections", 0
                        ),
                    }
                )
                if len(self.performance_history) > self.max_history_length:
                    self.performance_history.pop(0)

    def _render_frame(self):
        """Render a single frame"""
        # Clear screen
        self.screen.fill(self.colors["background"])

        # Draw main areas
        self._draw_world()
        self._draw_info_panel()
        self._draw_stats_panel()
        self._draw_performance_panel()

        # Update display
        pygame.display.flip()

    def _draw_world(self):
        """Draw the world view"""
        pygame.draw.rect(self.screen, self.colors["world_bg"], self.world_area)
        pygame.draw.rect(self.screen, self.colors["border"], self.world_area, 2)

        # Draw grid
        self._draw_grid()

        if not self.current_data:
            text = self.font.render(
                "Waiting for server data...", True, self.colors["text"]
            )
            text_rect = text.get_rect(center=self.world_area.center)
            self.screen.blit(text, text_rect)
            return

        # Draw trails if enabled
        if self.show_trails:
            self._draw_entity_trails()

        # Draw entities
        for entity_id, entity_data in self.current_data.entities.items():
            self._draw_entity(entity_id, entity_data)

        # Draw selection
        if self.selected_entity and self.selected_entity in self.current_data.entities:
            self._draw_entity_selection(
                self.current_data.entities[self.selected_entity]
            )

        # Draw legend
        self._draw_legend()

    def _draw_grid(self):
        """Draw background grid"""
        world_grid_size = 1000
        screen_grid_size = world_grid_size * self.world_scale * self.zoom_factor

        if screen_grid_size < 10 or screen_grid_size > 200:
            return

        start_world_x = -self.pan_x
        start_world_y = -self.pan_y

        grid_offset_x = (
            (start_world_x % world_grid_size) * self.world_scale * self.zoom_factor
        )
        grid_offset_y = (
            (start_world_y % world_grid_size) * self.world_scale * self.zoom_factor
        )

        # Vertical lines
        x = self.world_area.x - grid_offset_x
        while x < self.world_area.x + self.world_area.width:
            if x >= self.world_area.x:
                pygame.draw.line(
                    self.screen,
                    self.colors["grid"],
                    (int(x), self.world_area.y),
                    (int(x), self.world_area.y + self.world_area.height),
                    1,
                )
            x += screen_grid_size

        # Horizontal lines
        y = self.world_area.y - grid_offset_y
        while y < self.world_area.y + self.world_area.height:
            if y >= self.world_area.y:
                pygame.draw.line(
                    self.screen,
                    self.colors["grid"],
                    (self.world_area.x, int(y)),
                    (self.world_area.x + self.world_area.width, int(y)),
                    1,
                )
            y += screen_grid_size

    def _world_to_screen(self, world_pos: tuple) -> tuple:
        """Convert world coordinates to screen coordinates"""
        x, y = world_pos
        scaled_x = (x + self.pan_x) * self.world_scale * self.zoom_factor
        scaled_y = (y + self.pan_y) * self.world_scale * self.zoom_factor
        screen_x = self.world_area.x + scaled_x
        screen_y = self.world_area.y + scaled_y
        return (int(screen_x), int(screen_y))

    def _draw_entity(self, entity_id: str, entity_data: Dict[str, Any]):
        """Draw a single entity"""
        screen_pos = self._world_to_screen(entity_data["position"])

        if not self.world_area.collidepoint(screen_pos):
            return

        # Choose color and size based on entity type
        entity_type = entity_data.get("entity_type", "object")
        is_active = entity_data.get("is_active", True)

        if entity_type == "agent":
            color = (
                self.colors["agent_active"]
                if is_active
                else self.colors["agent_inactive"]
            )
            size = 8
        elif entity_type == "npc":
            color = self.colors["npc"]
            size = 6
        elif entity_type == "enemy":
            color = self.colors["enemy"]
            size = 5
        else:
            color = self.colors["object"]
            size = 4

        # Draw entity circle
        pygame.draw.circle(self.screen, color, screen_pos, size)

        # Draw health bar if damaged
        health_pct = entity_data.get("health_percentage", 100)
        if entity_type in ["agent", "enemy"] and health_pct < 100:
            self._draw_health_bar(screen_pos, health_pct, size)

        # Draw name for agents
        if entity_type == "agent" and self.show_agent_names:
            name = entity_data.get("name", "Unknown")
            name_text = self.small_font.render(name, True, self.colors["text"])
            name_pos = (
                screen_pos[0] - name_text.get_width() // 2,
                screen_pos[1] - size - 15,
            )
            self.screen.blit(name_text, name_pos)

        # Update entity trail
        if entity_type == "agent" and is_active:
            if entity_id not in self.entity_history:
                self.entity_history[entity_id] = []
            history = self.entity_history[entity_id]
            history.append((entity_data["position"], time.time()))
            if len(history) > 50:
                history.pop(0)

    def _draw_health_bar(self, pos: tuple, health_pct: float, entity_size: int):
        """Draw health bar above entity"""
        bar_width = entity_size * 3
        bar_height = 3
        bar_x = pos[0] - bar_width // 2
        bar_y = pos[1] - entity_size - 8

        # Background
        pygame.draw.rect(
            self.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height)
        )

        # Health
        health_width = int(bar_width * health_pct / 100)
        if health_width > 0:
            if health_pct < 30:
                color = (255, 0, 0)
            elif health_pct < 70:
                color = (255, 255, 0)
            else:
                color = (0, 255, 0)
            pygame.draw.rect(
                self.screen, color, (bar_x, bar_y, health_width, bar_height)
            )

    def _draw_entity_trails(self):
        """Draw movement trails"""
        current_time = time.time()

        for entity_id, history in self.entity_history.items():
            if len(history) < 2:
                continue

            # Filter recent positions
            recent_history = [(pos, t) for pos, t in history if current_time - t < 30]

            if len(recent_history) < 2:
                continue

            # Draw trail
            points = []
            for pos, _ in recent_history:
                screen_pos = self._world_to_screen(pos)
                if self.world_area.collidepoint(screen_pos):
                    points.append(screen_pos)

            if len(points) > 1:
                for i in range(len(points) - 1):
                    alpha = int(255 * (i / len(points)) * 0.5)
                    if alpha > 10:
                        pygame.draw.line(
                            self.screen, (0, 255, 255), points[i], points[i + 1], 1
                        )

    def _draw_entity_selection(self, entity_data: Dict[str, Any]):
        """Draw selection highlight"""
        screen_pos = self._world_to_screen(entity_data["position"])

        if not self.world_area.collidepoint(screen_pos):
            return

        pygame.draw.circle(self.screen, (255, 255, 0), screen_pos, 12, 2)

        # Draw info
        info_text = f"{entity_data['name']} ({entity_data['entity_type']}) - Level {entity_data['level']}"
        text_surface = self.small_font.render(info_text, True, (255, 255, 255))

        text_x = screen_pos[0] - text_surface.get_width() // 2
        text_y = screen_pos[1] - 30

        # Background
        pygame.draw.rect(
            self.screen,
            (0, 0, 0),
            (
                text_x - 5,
                text_y - 2,
                text_surface.get_width() + 10,
                text_surface.get_height() + 4,
            ),
        )
        pygame.draw.rect(
            self.screen,
            (255, 255, 0),
            (
                text_x - 5,
                text_y - 2,
                text_surface.get_width() + 10,
                text_surface.get_height() + 4,
            ),
            1,
        )

        self.screen.blit(text_surface, (text_x, text_y))

    def _draw_legend(self):
        """Draw entity type legend"""
        legend_x = self.world_area.x + 10
        legend_y = self.world_area.y + self.world_area.height - 100

        legend_items = [
            ("Active Player", self.colors["agent_active"]),
            ("Inactive Player", self.colors["agent_inactive"]),
            ("NPC", self.colors["npc"]),
            ("Enemy", self.colors["enemy"]),
        ]

        for i, (label, color) in enumerate(legend_items):
            y = legend_y + i * 20
            pygame.draw.circle(self.screen, color, (legend_x + 10, y + 8), 5)
            text = self.small_font.render(label, True, self.colors["text"])
            self.screen.blit(text, (legend_x + 25, y))

    def _draw_info_panel(self):
        """Draw information panel"""
        pygame.draw.rect(self.screen, self.colors["ui_bg"], self.info_area)
        pygame.draw.rect(self.screen, self.colors["border"], self.info_area, 2)

        if not self.current_data:
            return

        y = self.info_area.y + 10
        line_height = 25

        # Title
        self._draw_text("SERVER STATUS", self.info_area.x + 10, y, bold=True)
        y += line_height

        # Connection status (always direct now)
        self._draw_text_color(
            "Connection: DIRECT (Integrated)", self.info_area.x + 10, y, (100, 255, 100)
        )
        y += line_height

        self._draw_text(f"Tick: {self.current_data.tick}", self.info_area.x + 10, y)
        y += line_height
        self._draw_text(
            f"Active Players: {self.current_data.active_players}",
            self.info_area.x + 10,
            y,
        )
        y += line_height
        self._draw_text(
            f"Inactive Players: {self.current_data.inactive_players}",
            self.info_area.x + 10,
            y,
        )
        y += line_height
        self._draw_text(
            f"Total Entities: {len(self.current_data.entities)}",
            self.info_area.x + 10,
            y,
        )
        y += line_height * 2

        # View controls
        self._draw_text("VIEW CONTROLS", self.info_area.x + 10, y, bold=True)
        y += line_height
        self._draw_text(f"Zoom: {self.zoom_factor:.1f}x", self.info_area.x + 10, y)
        y += line_height
        self._draw_text(
            f"Pan: ({self.pan_x:.0f}, {self.pan_y:.0f})", self.info_area.x + 10, y
        )

    def _draw_stats_panel(self):
        """Draw statistics panel"""
        pygame.draw.rect(self.screen, self.colors["ui_bg"], self.stats_area)
        pygame.draw.rect(self.screen, self.colors["border"], self.stats_area, 2)

        if not self.current_data:
            return

        y = self.stats_area.y + 10
        line_height = 25

        self._draw_text("SERVER STATS", self.stats_area.x + 10, y, bold=True)
        y += line_height

        for key, value in self.current_data.server_stats.items():
            display_key = key.replace("_", " ").title()
            self._draw_text(f"{display_key}: {value}", self.stats_area.x + 10, y)
            y += line_height
            if y > self.stats_area.y + self.stats_area.height - 30:
                break

        # Controls help
        y = self.stats_area.y + self.stats_area.height - 80
        self._draw_text("CONTROLS", self.stats_area.x + 10, y, bold=True)
        y += 20
        self._draw_text("ESC - Exit | SPACE - Reset View", self.stats_area.x + 10, y)
        y += 20
        self._draw_text("+/- or Mouse Wheel - Zoom", self.stats_area.x + 10, y)
        y += 20
        self._draw_text("Click & Drag - Pan View", self.stats_area.x + 10, y)

    def _draw_performance_panel(self):
        """Draw performance metrics panel"""
        pygame.draw.rect(self.screen, self.colors["ui_bg"], self.performance_area)
        pygame.draw.rect(self.screen, self.colors["border"], self.performance_area, 2)

        if not self.current_data:
            return

        y = self.performance_area.y + 10
        self._draw_text(
            "PERFORMANCE METRICS", self.performance_area.x + 10, y, bold=True
        )

        # Current metrics
        metrics = self.current_data.performance_metrics
        x_offset = 10
        for i, (key, value) in enumerate(metrics.items()):
            if i % 4 == 0 and i > 0:
                y += 25
                x_offset = 10
            display_key = key.replace("_", " ").title()
            self._draw_text(
                f"{display_key}: {value}", self.performance_area.x + x_offset, y + 25
            )
            x_offset += 250

        # Draw performance chart if we have history
        if len(self.performance_history) > 1:
            chart_area = pygame.Rect(
                self.performance_area.x + 10,
                self.performance_area.y + 100,
                self.performance_area.width - 20,
                150,
            )
            self._draw_performance_chart(chart_area)

    def _draw_performance_chart(self, area: pygame.Rect):
        """Draw performance chart"""
        if len(self.performance_history) < 2:
            return

        pygame.draw.rect(self.screen, (30, 30, 40), area)
        pygame.draw.rect(self.screen, self.colors["border"], area, 1)

        # Draw FPS line
        fps_values = [entry["fps"] for entry in self.performance_history]
        if fps_values and max(fps_values) > 0:
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

            # Draw 60 FPS target line
            if max_fps > 60 and min_fps < 60:
                target_y = (
                    area.y + area.height - ((60 - min_fps) / fps_range) * area.height
                )
                pygame.draw.line(
                    self.screen,
                    (255, 255, 0),
                    (area.x, int(target_y)),
                    (area.x + area.width, int(target_y)),
                    1,
                )

    def _draw_text(self, text: str, x: int, y: int, bold: bool = False):
        """Draw text on screen"""
        font = self.font if bold else self.small_font
        color = (255, 255, 100) if bold else self.colors["text"]
        text_surface = font.render(text, True, color)
        self.screen.blit(text_surface, (x, y))

    def _draw_text_color(self, text: str, x: int, y: int, color: tuple):
        """Draw text with custom color"""
        text_surface = self.small_font.render(text, True, color)
        self.screen.blit(text_surface, (x, y))

    def _handle_key_event(self, event):
        """Handle keyboard input"""
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_SPACE:
            # Reset view
            self.zoom_factor = 8.0
            self.pan_x = -4500
            self.pan_y = -4500
        elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
            self.zoom_factor = min(self.zoom_factor * 1.2, 20.0)
        elif event.key == pygame.K_MINUS:
            self.zoom_factor = max(self.zoom_factor / 1.2, 0.5)
        elif event.key == pygame.K_t:
            self.show_trails = not self.show_trails
        elif event.key == pygame.K_n:
            self.show_agent_names = not self.show_agent_names

    def _handle_mouse_down(self, event):
        """Handle mouse button down"""
        if event.button == 1:  # Left click
            if self.world_area.collidepoint(event.pos):
                self.dragging = True
                self.last_mouse_pos = event.pos
                # Try to select entity
                self._try_select_entity(event.pos)
        elif event.button == 4:  # Mouse wheel up
            self.zoom_factor = min(self.zoom_factor * 1.1, 20.0)
        elif event.button == 5:  # Mouse wheel down
            self.zoom_factor = max(self.zoom_factor / 1.1, 0.5)

    def _handle_mouse_up(self, event):
        """Handle mouse button up"""
        if event.button == 1:
            self.dragging = False

    def _handle_mouse_motion(self, event):
        """Handle mouse motion"""
        if self.dragging and self.last_mouse_pos:
            dx = event.pos[0] - self.last_mouse_pos[0]
            dy = event.pos[1] - self.last_mouse_pos[1]

            world_dx = dx / (self.world_scale * self.zoom_factor)
            world_dy = dy / (self.world_scale * self.zoom_factor)

            self.pan_x += world_dx
            self.pan_y += world_dy

            self.last_mouse_pos = event.pos

    def _try_select_entity(self, mouse_pos):
        """Try to select an entity at mouse position"""
        if not self.current_data:
            return

        # Convert screen to world coordinates
        rel_x = (mouse_pos[0] - self.world_area.x) / (
            self.world_scale * self.zoom_factor
        )
        rel_y = (mouse_pos[1] - self.world_area.y) / (
            self.world_scale * self.zoom_factor
        )
        world_x = rel_x - self.pan_x
        world_y = rel_y - self.pan_y

        # Find closest entity
        min_distance = 50  # Maximum selection distance in world units
        selected = None

        for entity_id, entity_data in self.current_data.entities.items():
            ex, ey = entity_data["position"]
            distance = math.sqrt((ex - world_x) ** 2 + (ey - world_y) ** 2)
            if distance < min_distance:
                min_distance = distance
                selected = entity_id

        self.selected_entity = selected
        if selected:
            entity = self.current_data.entities[selected]
            logger.info(f"Selected {entity['name']} ({entity['entity_type']})")
