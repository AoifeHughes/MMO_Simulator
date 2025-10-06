from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pygame

from simulation_framework.src.entities.agent import Agent


@dataclass
class UIElement:
    """Base class for UI elements"""

    x: int
    y: int
    width: int
    height: int
    visible: bool = True


class Button(UIElement):
    """Simple button UI element"""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        color: Tuple[int, int, int] = (100, 100, 100),
        text_color: Tuple[int, int, int] = (255, 255, 255),
    ):
        super().__init__(x, y, width, height)
        self.text = text
        self.color = color
        self.text_color = text_color
        self.font = pygame.font.Font(None, 24)
        self.hovered = False

    def is_clicked(self, mouse_pos: Tuple[int, int]) -> bool:
        """Check if the button was clicked"""
        mx, my = mouse_pos
        return (
            self.x <= mx <= self.x + self.width and self.y <= my <= self.y + self.height
        )

    def update(self, mouse_pos: Tuple[int, int]):
        """Update button state"""
        self.hovered = self.is_clicked(mouse_pos)

    def render(self, screen: pygame.Surface):
        """Render the button"""
        if not self.visible:
            return

        # Button background
        color = (
            tuple(min(255, c + 20) for c in self.color) if self.hovered else self.color
        )
        pygame.draw.rect(screen, color, (self.x, self.y, self.width, self.height))
        pygame.draw.rect(
            screen, (200, 200, 200), (self.x, self.y, self.width, self.height), 2
        )

        # Button text
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(
            center=(self.x + self.width // 2, self.y + self.height // 2)
        )
        screen.blit(text_surface, text_rect)


class InfoPanel(UIElement):
    """Information panel for displaying agent/NPC details"""

    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__(x, y, width, height)
        self.background_color = (30, 30, 30, 240)
        self.border_color = (100, 100, 100)
        self.font_large = pygame.font.Font(None, 32)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        self.content: Dict[str, Any] = {}
        self.scroll_offset = 0
        self.max_scroll = 0

    def set_content(self, entity: Optional[Agent]):
        """Set the content to display"""
        if entity is None:
            self.content = {}
            return

        self.content = {
            "name": entity.name,
            "type": "Agent" if isinstance(entity, Agent) else "NPC",
            "position": entity.position,
            "health": entity.stats.health,
            "max_health": entity.stats.max_health,
            "stamina": entity.stats.stamina,
            "max_stamina": entity.stats.max_stamina,
            "magic": entity.stats.magic,
            "max_magic": entity.stats.max_magic,
            "is_alive": entity.stats.is_alive,
        }

        # Add agent-specific content
        if isinstance(entity, Agent):
            self.content.update(
                {
                    "character_class": (
                        entity.character_class.name
                        if entity.character_class
                        else "Unknown"
                    ),
                    "current_goals": [str(goal) for goal in entity.current_goals],
                    "personality": (
                        entity.personality.get_dominant_traits()
                        if hasattr(entity, "personality")
                        else []
                    ),
                }
            )

    def handle_scroll(self, scroll_y: int):
        """Handle scrolling within the panel"""
        self.scroll_offset = max(
            0, min(self.max_scroll, self.scroll_offset - scroll_y * 20)
        )

    def render(self, screen: pygame.Surface):
        """Render the information panel"""
        if not self.visible or not self.content:
            return

        # Create a surface for the panel content
        panel_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        panel_surface.fill(self.background_color)

        # Draw border
        pygame.draw.rect(
            panel_surface, self.border_color, (0, 0, self.width, self.height), 2
        )

        # Render content
        y_offset = 20 - self.scroll_offset
        margin = 15

        # Title
        name = self.content.get("name", "Unknown")
        entity_type = self.content.get("type", "Entity")
        title = f"{name} ({entity_type})"
        title_surface = self.font_large.render(title, True, (255, 255, 255))
        panel_surface.blit(title_surface, (margin, y_offset))
        y_offset += 40

        # Character class (for agents)
        if "character_class" in self.content:
            class_text = f"Class: {self.content['character_class']}"
            class_surface = self.font_medium.render(class_text, True, (200, 200, 200))
            panel_surface.blit(class_surface, (margin, y_offset))
            y_offset += 30

        # Stats section
        stats_title = self.font_medium.render("Stats:", True, (255, 255, 255))
        panel_surface.blit(stats_title, (margin, y_offset))
        y_offset += 25

        stats = [
            f"Health: {self.content['health']}/{self.content['max_health']}",
            f"Stamina: {self.content['stamina']}/{self.content['max_stamina']}",
            f"Magic: {self.content['magic']}/{self.content['max_magic']}",
            f"Position: {self.content['position']}",
            f"Status: {'Alive' if self.content['is_alive'] else 'Dead'}",
        ]

        for stat in stats:
            stat_surface = self.font_small.render(stat, True, (180, 180, 180))
            panel_surface.blit(stat_surface, (margin, y_offset))
            y_offset += 20

        # Goals section (for agents)
        if "current_goals" in self.content and self.content["current_goals"]:
            y_offset += 10
            goals_title = self.font_medium.render(
                "Current Goals:", True, (255, 255, 255)
            )
            panel_surface.blit(goals_title, (margin, y_offset))
            y_offset += 25

            for i, goal in enumerate(
                self.content["current_goals"][:10]
            ):  # Max 10 goals
                # Truncate long goal descriptions
                goal_text = goal[:40] + "..." if len(goal) > 40 else goal
                goal_surface = self.font_small.render(
                    f"{i+1}. {goal_text}", True, (180, 180, 180)
                )
                panel_surface.blit(goal_surface, (margin, y_offset))
                y_offset += 18

        # Personality section (for agents)
        if "personality" in self.content and self.content["personality"]:
            y_offset += 15
            personality_title = self.font_medium.render(
                "Personality Traits:", True, (255, 255, 255)
            )
            panel_surface.blit(personality_title, (margin, y_offset))
            y_offset += 25

            for trait in self.content["personality"][:5]:  # Show top 5 traits
                trait_text = f"• {trait.replace('_', ' ').title()}"
                trait_surface = self.font_small.render(
                    trait_text, True, (180, 180, 180)
                )
                panel_surface.blit(trait_surface, (margin, y_offset))
                y_offset += 18

        # Calculate max scroll
        self.max_scroll = max(0, y_offset - self.height + 40)

        # Blit panel to screen
        screen.blit(panel_surface, (self.x, self.y))

        # Scroll indicator
        if self.max_scroll > 0:
            self._render_scroll_indicator(screen)

    def _render_scroll_indicator(self, screen: pygame.Surface):
        """Render scroll indicator"""
        indicator_width = 6
        indicator_x = self.x + self.width - indicator_width - 5
        indicator_height = self.height - 20
        indicator_y = self.y + 10

        # Background
        pygame.draw.rect(
            screen,
            (60, 60, 60),
            (indicator_x, indicator_y, indicator_width, indicator_height),
        )

        # Thumb
        if self.max_scroll > 0:
            thumb_height = max(
                20, indicator_height * self.height // (self.height + self.max_scroll)
            )
            thumb_y = indicator_y + (self.scroll_offset / self.max_scroll) * (
                indicator_height - thumb_height
            )
            pygame.draw.rect(
                screen,
                (120, 120, 120),
                (indicator_x, int(thumb_y), indicator_width, thumb_height),
            )


class HUD:
    """Heads-up display for simulation information"""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        self.background_color = (0, 0, 0, 150)
        self.text_color = (255, 255, 255)
        self.height = 80

    def render(self, screen: pygame.Surface, simulation_data: Dict[str, Any]):
        """Render the HUD"""
        # Background
        hud_surface = pygame.Surface((self.screen_width, self.height), pygame.SRCALPHA)
        hud_surface.fill(self.background_color)

        # Main simulation info
        y_offset = 10
        alive_agents = simulation_data.get("alive_agents", 0)
        total_agents = simulation_data.get("total_agents", 0)
        alive_npcs = simulation_data.get("alive_npcs", 0)
        total_npcs = simulation_data.get("total_npcs", 0)
        main_info = [
            f"Tick: {simulation_data.get('current_tick', 0)}",
            f"Agents: {alive_agents}/{total_agents}",
            f"NPCs: {alive_npcs}/{total_npcs}",
            f"Zoom: {simulation_data.get('zoom', 1.0):.2f}x",
        ]

        x_offset = 15
        for info in main_info:
            text_surface = self.font_medium.render(info, True, self.text_color)
            hud_surface.blit(text_surface, (x_offset, y_offset))
            x_offset += text_surface.get_width() + 30

        # Instructions
        instruction_text = (
            "Left Click + Drag: Pan  |  Mouse Wheel: Zoom  |  "
            "Click Agent: Info  |  Space: Center  |  ESC: Deselect"
        )
        instruction_surface = self.font_small.render(
            instruction_text, True, (200, 200, 200)
        )
        text_rect = instruction_surface.get_rect()
        text_rect.centerx = self.screen_width // 2
        text_rect.y = y_offset + 35
        hud_surface.blit(instruction_surface, text_rect)

        # Blit HUD to screen
        screen.blit(hud_surface, (0, 0))


class UIManager:
    """Manages all UI components"""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Initialize UI components
        self.hud = HUD(screen_width, screen_height)

        # Info panel on the right side
        panel_width = 320
        self.info_panel = InfoPanel(
            screen_width - panel_width, 0, panel_width, screen_height
        )
        self.info_panel.visible = False

        # Buttons
        self.buttons: List[Button] = []

        # Selected entity
        self.selected_entity: Optional[Agent] = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle UI events. Returns True if event was consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            # Check button clicks
            for button in self.buttons:
                if button.visible and button.is_clicked(mouse_pos):
                    return True

            # If clicking in info panel area, consume the event
            if (
                self.info_panel.visible
                and self.info_panel.x
                <= mouse_pos[0]
                <= self.info_panel.x + self.info_panel.width
            ):
                return True

        elif event.type == pygame.MOUSEWHEEL and self.info_panel.visible:
            mouse_pos = pygame.mouse.get_pos()
            # If mouse is over info panel, handle scrolling
            if (
                self.info_panel.x
                <= mouse_pos[0]
                <= self.info_panel.x + self.info_panel.width
            ):
                self.info_panel.handle_scroll(event.y)
                return True

        return False

    def update(self):
        """Update UI state"""
        mouse_pos = pygame.mouse.get_pos()

        # Update buttons
        for button in self.buttons:
            button.update(mouse_pos)

    def show_entity_info(self, entity: Optional[Agent]):
        """Show information panel for an entity"""
        self.selected_entity = entity
        self.info_panel.set_content(entity)
        self.info_panel.visible = entity is not None

    def hide_entity_info(self):
        """Hide the information panel"""
        self.selected_entity = None
        self.info_panel.visible = False

    def render(self, screen: pygame.Surface, simulation_data: Dict[str, Any]):
        """Render all UI components"""
        # Render HUD
        self.hud.render(screen, simulation_data)

        # Render info panel
        if self.info_panel.visible:
            self.info_panel.render(screen)

        # Render buttons
        for button in self.buttons:
            button.render(screen)

    def is_mouse_over_ui(self, mouse_pos: Tuple[int, int]) -> bool:
        """Check if mouse is over any UI element"""
        mx, my = mouse_pos

        # Check HUD area
        if my < self.hud.height:
            return True

        # Check info panel
        if (
            self.info_panel.visible
            and self.info_panel.x <= mx <= self.info_panel.x + self.info_panel.width
        ):
            return True

        # Check buttons
        for button in self.buttons:
            if button.visible and button.is_clicked(mouse_pos):
                return True

        return False
