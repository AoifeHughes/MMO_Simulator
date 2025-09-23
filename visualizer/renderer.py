import pygame
import math
from typing import Dict, List, Tuple, Optional
from world.tiles import TILE_PROPERTIES, TileType
from shared.constants import TILE_SIZE, WORLD_WIDTH, WORLD_HEIGHT

class Renderer:
    def __init__(self, screen_width: int = 1024, screen_height: int = 768):
        pygame.init()
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption("MMO Simulator")

        self.font_small = pygame.font.Font(None, 20)
        self.font_medium = pygame.font.Font(None, 30)

        self.camera_x = 0
        self.camera_y = 0
        self.zoom = 1.0

        self.debug_mode = False
        self.show_vision_cones = True
        self.show_minimap = True

        # Mouse panning
        self.is_panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.camera_start_x = 0
        self.camera_start_y = 0
        self.follow_mode = False  # Disable auto-follow when manually panning

        self.agent_colors = {
            'player': (0, 100, 255),
            'npc': (0, 255, 100),
            'enemy': (255, 50, 50),
            'explorer': (255, 165, 0)
        }

    def render_frame(self, world_map, agents: List[Dict], focus_agent_id: Optional[str] = None):
        self.screen.fill((20, 20, 20))

        if focus_agent_id and self.follow_mode and not self.is_panning:
            self.update_camera_focus(agents, focus_agent_id)

        self.render_map(world_map)
        self.render_agents(agents)

        if self.show_vision_cones:
            self.render_vision_cones(agents)

        if self.show_minimap:
            self.render_minimap(world_map, agents)

        if self.debug_mode:
            self.render_debug_info(agents)

        pygame.display.flip()

    def render_map(self, world_map):
        tile_size = int(TILE_SIZE * self.zoom)

        start_x = max(0, int(self.camera_x / TILE_SIZE))
        end_x = min(world_map.width, start_x + int(self.screen_width / tile_size) + 2)
        start_y = max(0, int(self.camera_y / TILE_SIZE))
        end_y = min(world_map.height, start_y + int(self.screen_height / tile_size) + 2)

        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                tile = world_map.get_tile(x, y)
                if tile:
                    color = TILE_PROPERTIES[tile].color
                    screen_x = x * tile_size - int(self.camera_x * self.zoom)
                    screen_y = y * tile_size - int(self.camera_y * self.zoom)

                    pygame.draw.rect(self.screen, color,
                                   (screen_x, screen_y, tile_size, tile_size))

                    if self.debug_mode:
                        pygame.draw.rect(self.screen, (50, 50, 50),
                                       (screen_x, screen_y, tile_size, tile_size), 1)

    def render_agents(self, agents: List[Dict]):
        for agent in agents:
            x, y = self.world_to_screen(agent['x'], agent['y'])
            agent_type = agent.get('agent_type', 'player')
            color = self.agent_colors.get(agent_type, (255, 255, 255))

            radius = int(10 * self.zoom)
            pygame.draw.circle(self.screen, color, (int(x), int(y)), radius)

            health = agent.get('health', 100)
            if health < 100:
                bar_width = 30
                bar_height = 4
                bar_x = x - bar_width // 2
                bar_y = y - radius - 10

                pygame.draw.rect(self.screen, (100, 0, 0),
                               (bar_x, bar_y, bar_width, bar_height))
                pygame.draw.rect(self.screen, (0, 255, 0),
                               (bar_x, bar_y, int(bar_width * health / 100), bar_height))

            rotation = agent.get('rotation', 0)
            end_x = x + math.cos(math.radians(rotation)) * radius * 1.5
            end_y = y + math.sin(math.radians(rotation)) * radius * 1.5
            pygame.draw.line(self.screen, (255, 255, 255),
                           (x, y), (end_x, end_y), 2)

            if self.debug_mode:
                text = self.font_small.render(agent['id'][:8], True, (255, 255, 255))
                self.screen.blit(text, (x - 30, y + radius + 5))

    def render_vision_cones(self, agents: List[Dict]):
        for agent in agents:
            if agent.get('agent_type') == 'player':
                x, y = self.world_to_screen(agent['x'], agent['y'])
                rotation = agent.get('rotation', 0)
                vision_range = 10 * TILE_SIZE * self.zoom
                vision_angle = 90

                start_angle = rotation - vision_angle / 2
                end_angle = rotation + vision_angle / 2

                points = [(x, y)]
                for angle in range(int(start_angle), int(end_angle) + 1, 5):
                    rad = math.radians(angle)
                    px = x + math.cos(rad) * vision_range
                    py = y + math.sin(rad) * vision_range
                    points.append((px, py))

                if len(points) > 2:
                    vision_surface = pygame.Surface((self.screen_width, self.screen_height),
                                                  pygame.SRCALPHA)
                    pygame.draw.polygon(vision_surface, (255, 255, 100, 30), points)
                    self.screen.blit(vision_surface, (0, 0))

    def render_minimap(self, world_map, agents: List[Dict]):
        minimap_size = 200
        minimap_x = self.screen_width - minimap_size - 10
        minimap_y = 10

        pygame.draw.rect(self.screen, (40, 40, 40),
                        (minimap_x, minimap_y, minimap_size, minimap_size))
        pygame.draw.rect(self.screen, (100, 100, 100),
                        (minimap_x, minimap_y, minimap_size, minimap_size), 2)

        scale_x = minimap_size / world_map.width
        scale_y = minimap_size / world_map.height

        for agent in agents:
            x = minimap_x + agent['x'] * scale_x
            y = minimap_y + agent['y'] * scale_y
            agent_type = agent.get('agent_type', 'player')
            color = self.agent_colors.get(agent_type, (255, 255, 255))
            pygame.draw.circle(self.screen, color, (int(x), int(y)), 2)

        viewport_x = minimap_x + (self.camera_x / TILE_SIZE) * scale_x
        viewport_y = minimap_y + (self.camera_y / TILE_SIZE) * scale_y
        viewport_w = (self.screen_width / (TILE_SIZE * self.zoom)) * scale_x
        viewport_h = (self.screen_height / (TILE_SIZE * self.zoom)) * scale_y

        pygame.draw.rect(self.screen, (255, 255, 0),
                        (viewport_x, viewport_y, viewport_w, viewport_h), 1)

    def render_debug_info(self, agents: List[Dict]):
        debug_info = [
            f"Camera: ({int(self.camera_x)}, {int(self.camera_y)})",
            f"Zoom: {self.zoom:.2f}",
            f"Agents: {len(agents)}",
            f"FPS: {int(pygame.time.Clock().get_fps())}"
        ]

        y_offset = 10
        for info in debug_info:
            text = self.font_small.render(info, True, (255, 255, 255))
            self.screen.blit(text, (10, y_offset))
            y_offset += 25

    def world_to_screen(self, world_x: float, world_y: float) -> Tuple[float, float]:
        screen_x = (world_x * TILE_SIZE - self.camera_x) * self.zoom
        screen_y = (world_y * TILE_SIZE - self.camera_y) * self.zoom
        return screen_x, screen_y

    def screen_to_world(self, screen_x: float, screen_y: float) -> Tuple[float, float]:
        world_x = (screen_x / self.zoom + self.camera_x) / TILE_SIZE
        world_y = (screen_y / self.zoom + self.camera_y) / TILE_SIZE
        return world_x, world_y

    def update_camera_focus(self, agents: List[Dict], focus_agent_id: str):
        for agent in agents:
            if agent['id'] == focus_agent_id:
                target_x = agent['x'] * TILE_SIZE - self.screen_width / (2 * self.zoom)
                target_y = agent['y'] * TILE_SIZE - self.screen_height / (2 * self.zoom)

                self.camera_x += (target_x - self.camera_x) * 0.1
                self.camera_y += (target_y - self.camera_y) * 0.1
                break

    def handle_zoom(self, delta: float):
        self.zoom = max(0.5, min(2.0, self.zoom + delta))

    def toggle_debug(self):
        self.debug_mode = not self.debug_mode

    def toggle_vision_cones(self):
        self.show_vision_cones = not self.show_vision_cones

    def toggle_follow_mode(self):
        self.follow_mode = not self.follow_mode

    def start_panning(self, mouse_x: int, mouse_y: int):
        self.is_panning = True
        self.pan_start_x = mouse_x
        self.pan_start_y = mouse_y
        self.camera_start_x = self.camera_x
        self.camera_start_y = self.camera_y
        self.follow_mode = False

    def update_panning(self, mouse_x: int, mouse_y: int):
        if self.is_panning:
            dx = mouse_x - self.pan_start_x
            dy = mouse_y - self.pan_start_y
            self.camera_x = self.camera_start_x - dx / self.zoom
            self.camera_y = self.camera_start_y - dy / self.zoom

    def stop_panning(self):
        self.is_panning = False

    def cleanup(self):
        pygame.quit()