from __future__ import annotations
import pygame
import pygame.font
from typing import Optional, Tuple, Dict, TYPE_CHECKING
import math

from simulation_framework.src.world.terrain import TerrainType
from simulation_framework.src.entities.agent import Agent
from simulation_framework.src.entities.npc import NPC

if TYPE_CHECKING:
    from simulation_framework.src.core.simulation import Simulation


class Camera:
    """Camera system for panning and zooming"""

    def __init__(self, screen_width: int, screen_height: int):
        self.x = 0.0
        self.y = 0.0
        self.zoom = 1.0
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.min_zoom = 0.2
        self.max_zoom = 5.0

    def world_to_screen(self, world_x: int, world_y: int, tile_size: int) -> Tuple[int, int]:
        """Convert world coordinates to screen coordinates"""
        screen_x = int((world_x * tile_size - self.x) * self.zoom)
        screen_y = int((world_y * tile_size - self.y) * self.zoom)
        return screen_x, screen_y

    def screen_to_world(self, screen_x: int, screen_y: int, tile_size: int) -> Tuple[float, float]:
        """Convert screen coordinates to world coordinates"""
        world_x = (screen_x / self.zoom + self.x) / tile_size
        world_y = (screen_y / self.zoom + self.y) / tile_size
        return world_x, world_y

    def pan(self, dx: int, dy: int):
        """Pan the camera by screen coordinates"""
        self.x -= dx / self.zoom
        self.y -= dy / self.zoom

    def zoom_at(self, screen_x: int, screen_y: int, zoom_delta: float, tile_size: int):
        """Zoom at a specific screen coordinate"""
        # Convert screen point to world coordinates before zooming
        world_x, world_y = self.screen_to_world(screen_x, screen_y, tile_size)

        # Apply zoom
        old_zoom = self.zoom
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * zoom_delta))

        # Adjust camera position to keep the zoom point fixed
        if self.zoom != old_zoom:
            self.x = world_x * tile_size - screen_x / self.zoom
            self.y = world_y * tile_size - screen_y / self.zoom


class GameVisualizer:
    """Main pygame visualizer for the MMO simulation"""

    # Terrain colors
    TERRAIN_COLORS = {
        TerrainType.WATER: (64, 128, 255),      # Blue
        TerrainType.GRASS: (34, 139, 34),       # Forest Green
        TerrainType.FOREST: (0, 100, 0),        # Dark Green
        TerrainType.MOUNTAIN: (139, 137, 137),  # Gray
        TerrainType.DESERT: (238, 203, 173)     # Sandy Brown
    }

    # Entity colors
    AGENT_COLORS = {
        'Explorer': (255, 215, 0),    # Gold
        'Warrior': (255, 69, 0),      # Red-Orange
        'Mage': (138, 43, 226),       # Blue-Violet
        'Crafter': (32, 178, 170),    # Light Sea Green
        'Merchant': (255, 20, 147)    # Deep Pink
    }

    NPC_COLOR = (220, 20, 60)  # Crimson

    def __init__(self, width: int = 1024, height: int = 768, tile_size: int = 20):
        """Initialize the pygame visualizer"""
        pygame.init()
        pygame.font.init()

        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.running = True

        # Create display
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("MMO Simulator - Pygame Visualizer")

        # Initialize camera
        self.camera = Camera(width, height)

        # Initialize fonts
        self.font_small = pygame.font.Font(None, 16)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_large = pygame.font.Font(None, 32)

        # Mouse state
        self.mouse_dragging = False
        self.last_mouse_pos = (0, 0)

        # Selected agent
        self.selected_agent: Optional[Agent] = None

    def handle_events(self, simulation: Simulation) -> bool:
        """Handle pygame events. Returns False if should quit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    self.mouse_dragging = True
                    self.last_mouse_pos = event.pos

                    # Check for agent clicks
                    self._handle_agent_click(event.pos, simulation)

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left click release
                    self.mouse_dragging = False

            elif event.type == pygame.MOUSEMOTION:
                if self.mouse_dragging:
                    dx = event.pos[0] - self.last_mouse_pos[0]
                    dy = event.pos[1] - self.last_mouse_pos[1]
                    self.camera.pan(dx, dy)
                    self.last_mouse_pos = event.pos

            elif event.type == pygame.MOUSEWHEEL:
                mouse_x, mouse_y = pygame.mouse.get_pos()
                zoom_factor = 1.1 if event.y > 0 else 1/1.1
                self.camera.zoom_at(mouse_x, mouse_y, zoom_factor, self.tile_size)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.selected_agent = None
                elif event.key == pygame.K_SPACE:
                    # Center camera on first agent
                    if simulation.agents:
                        agent = simulation.agents[0]
                        self.camera.x = agent.position[0] * self.tile_size - self.width // 2
                        self.camera.y = agent.position[1] * self.tile_size - self.height // 2

        return True

    def _handle_agent_click(self, mouse_pos: Tuple[int, int], simulation: Simulation):
        """Handle clicking on agents"""
        world_x, world_y = self.camera.screen_to_world(mouse_pos[0], mouse_pos[1], self.tile_size)
        click_tolerance = 0.5  # Half a tile

        # Check agents
        for agent in simulation.agents:
            agent_x, agent_y = agent.position
            distance = math.sqrt((world_x - agent_x)**2 + (world_y - agent_y)**2)
            if distance <= click_tolerance:
                self.selected_agent = agent
                return

    def render(self, simulation: Simulation):
        """Render the current simulation state"""
        # Clear screen
        self.screen.fill((0, 0, 0))

        # Calculate visible world bounds
        visible_bounds = self._get_visible_bounds(simulation.world.width, simulation.world.height)

        # Render terrain
        self._render_terrain(simulation, visible_bounds)

        # Render entities
        self._render_npcs(simulation, visible_bounds)
        self._render_agents(simulation, visible_bounds)

    def _get_visible_bounds(self, world_width: int, world_height: int) -> Tuple[int, int, int, int]:
        """Get the bounds of visible world tiles"""
        # Convert screen bounds to world coordinates
        left_x, top_y = self.camera.screen_to_world(0, 0, self.tile_size)
        right_x, bottom_y = self.camera.screen_to_world(self.width, self.height, self.tile_size)

        # Clamp to world bounds with some padding
        min_x = max(0, int(left_x) - 1)
        min_y = max(0, int(top_y) - 1)
        max_x = min(world_width, int(right_x) + 2)
        max_y = min(world_height, int(bottom_y) + 2)

        return min_x, min_y, max_x, max_y

    def _render_terrain(self, simulation: Simulation, visible_bounds: Tuple[int, int, int, int]):
        """Render visible terrain tiles"""
        min_x, min_y, max_x, max_y = visible_bounds

        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                if 0 <= x < simulation.world.width and 0 <= y < simulation.world.height:
                    tile = simulation.world.get_tile(x, y)
                    if tile:
                        color = self.TERRAIN_COLORS.get(tile.terrain_type, (100, 100, 100))
                        screen_x, screen_y = self.camera.world_to_screen(x, y, self.tile_size)
                        scaled_size = max(1, int(self.tile_size * self.camera.zoom))

                        pygame.draw.rect(self.screen, color,
                                       (screen_x, screen_y, scaled_size, scaled_size))

                        # Draw grid lines if zoomed in enough
                        if self.camera.zoom >= 1.0:
                            pygame.draw.rect(self.screen, (50, 50, 50),
                                           (screen_x, screen_y, scaled_size, scaled_size), 1)

    def _render_agents(self, simulation: Simulation, visible_bounds: Tuple[int, int, int, int]):
        """Render visible agents"""
        min_x, min_y, max_x, max_y = visible_bounds

        for agent in simulation.agents:
            if not agent.stats.is_alive:
                continue

            agent_x, agent_y = agent.position
            if min_x <= agent_x < max_x and min_y <= agent_y < max_y:
                screen_x, screen_y = self.camera.world_to_screen(agent_x, agent_y, self.tile_size)
                scaled_size = max(4, int(self.tile_size * self.camera.zoom * 0.8))

                # Get color based on character class
                class_name = agent.character_class.name if agent.character_class else 'Unknown'
                color = self.AGENT_COLORS.get(class_name, (255, 255, 255))

                # Highlight selected agent
                if agent == self.selected_agent:
                    # Draw selection circle
                    pygame.draw.circle(self.screen, (255, 255, 0),
                                     (screen_x + scaled_size//2, screen_y + scaled_size//2),
                                     scaled_size//2 + 3, 2)

                # Draw agent as circle
                pygame.draw.circle(self.screen, color,
                                 (screen_x + scaled_size//2, screen_y + scaled_size//2),
                                 scaled_size//2)

                # Draw health bar if zoomed in enough
                if self.camera.zoom >= 1.5 and agent.stats.health < agent.stats.max_health:
                    self._draw_health_bar(screen_x, screen_y - 8, scaled_size,
                                        agent.stats.health, agent.stats.max_health)

                # Draw name if zoomed in enough
                if self.camera.zoom >= 2.0:
                    text = self.font_small.render(agent.name, True, (255, 255, 255))
                    self.screen.blit(text, (screen_x, screen_y - 20))

    def _render_npcs(self, simulation: Simulation, visible_bounds: Tuple[int, int, int, int]):
        """Render visible NPCs"""
        min_x, min_y, max_x, max_y = visible_bounds

        for npc in simulation.npcs:
            if not npc.stats.is_alive:
                continue

            npc_x, npc_y = npc.position
            if min_x <= npc_x < max_x and min_y <= npc_y < max_y:
                screen_x, screen_y = self.camera.world_to_screen(npc_x, npc_y, self.tile_size)
                scaled_size = max(4, int(self.tile_size * self.camera.zoom * 0.7))

                # Draw NPC as square
                pygame.draw.rect(self.screen, self.NPC_COLOR,
                               (screen_x + (self.tile_size * self.camera.zoom - scaled_size)//2,
                                screen_y + (self.tile_size * self.camera.zoom - scaled_size)//2,
                                scaled_size, scaled_size))

                # Draw health bar if zoomed in enough
                if self.camera.zoom >= 1.5 and npc.stats.health < npc.stats.max_health:
                    self._draw_health_bar(screen_x, screen_y - 8, scaled_size,
                                        npc.stats.health, npc.stats.max_health)

    def _draw_health_bar(self, x: int, y: int, width: int, current_health: int, max_health: int):
        """Draw a health bar"""
        bar_height = 4
        health_ratio = current_health / max_health if max_health > 0 else 0

        # Background (red)
        pygame.draw.rect(self.screen, (255, 0, 0), (x, y, width, bar_height))
        # Foreground (green)
        pygame.draw.rect(self.screen, (0, 255, 0), (x, y, int(width * health_ratio), bar_height))



    def quit(self):
        """Clean up and quit pygame"""
        pygame.quit()