"""
Bounds checking and world validation
"""

import math
from typing import Optional, List, Tuple
import logging

from shared.math_utils import Vector2
from shared.constants import WORLD_WIDTH, WORLD_HEIGHT

logger = logging.getLogger(__name__)


class BoundsChecker:
    """Validates world boundaries and safe zones"""

    def __init__(self, world_config=None):
        self.world_width = WORLD_WIDTH
        self.world_height = WORLD_HEIGHT
        self.safe_zones = []
        self.terrain_restrictions = []

        if world_config:
            self.world_width = world_config.world_settings.get('width', WORLD_WIDTH)
            self.world_height = world_config.world_settings.get('height', WORLD_HEIGHT)
            self.safe_zones = world_config.world_settings.get('safe_zones', [])
            self.terrain_restrictions = world_config.terrain

    def is_position_valid(self, position: Vector2) -> bool:
        """Check if position is within world bounds"""
        return (0 <= position.x <= self.world_width and
                0 <= position.y <= self.world_height)

    def clamp_to_bounds(self, position: Vector2) -> Vector2:
        """Clamp position to world bounds"""
        return Vector2(
            max(0, min(position.x, self.world_width)),
            max(0, min(position.y, self.world_height))
        )

    def is_in_safe_zone(self, position: Vector2) -> bool:
        """Check if position is in a safe zone"""
        for zone in self.safe_zones:
            center = Vector2.from_tuple(zone.get('center', [0, 0]))
            radius = zone.get('radius', 0)
            if position.distance_to(center) <= radius:
                return True
        return False

    def get_safe_zone_info(self, position: Vector2) -> Optional[dict]:
        """Get safe zone info if position is in one"""
        for zone in self.safe_zones:
            center = Vector2.from_tuple(zone.get('center', [0, 0]))
            radius = zone.get('radius', 0)
            if position.distance_to(center) <= radius:
                return zone
        return None

    def check_terrain_movement_modifier(self, position: Vector2) -> float:
        """Get movement speed modifier based on terrain"""
        modifier = 1.0
        for terrain in self.terrain_restrictions:
            terrain_pos = terrain.position
            terrain_size = terrain.size

            # Check if position is within terrain bounds (rectangular)
            if (terrain_pos.x <= position.x <= terrain_pos.x + terrain_size.x and
                terrain_pos.y <= position.y <= terrain_pos.y + terrain_size.y):

                terrain_modifier = terrain.properties.get('movement_speed_modifier', 1.0)
                modifier = min(modifier, terrain_modifier)  # Use most restrictive

        return modifier

    def validate_movement_path(self, start: Vector2, end: Vector2, entity_type: str = "agent") -> Tuple[bool, Vector2, List[str]]:
        """Validate a movement path and return corrected endpoint with issues"""
        issues = []
        corrected_end = end

        # Check world bounds
        if not self.is_position_valid(end):
            corrected_end = self.clamp_to_bounds(end)
            issues.append("Position clamped to world bounds")

        # Check for terrain restrictions (example: water for non-swimming entities)
        movement_modifier = self.check_terrain_movement_modifier(corrected_end)
        if movement_modifier < 0.1:  # Nearly impassable terrain
            issues.append("Terrain is impassable")
            return False, start, issues

        # Check line of sight for teleportation detection
        distance = start.distance_to(corrected_end)
        max_teleport_distance = 500  # Anti-cheat threshold

        if distance > max_teleport_distance:
            # Limit movement to reasonable distance
            direction = (corrected_end - start).normalize()
            corrected_end = start + direction * max_teleport_distance
            issues.append("Movement limited due to teleportation detection")

        return True, corrected_end, issues

    def get_nearest_safe_position(self, position: Vector2, search_radius: float = 100) -> Vector2:
        """Find nearest position that is valid and safe"""
        if self.is_position_valid(position):
            return position

        # Try positions in expanding circles
        for radius in range(10, int(search_radius), 10):
            for angle in range(0, 360, 15):  # Every 15 degrees
                test_pos = Vector2(
                    position.x + radius * math.cos(math.radians(angle)),
                    position.y + radius * math.sin(math.radians(angle))
                )
                if self.is_position_valid(test_pos):
                    return test_pos

        # Fallback to center of world
        return Vector2(self.world_width / 2, self.world_height / 2)

    def check_collision_with_terrain(self, position: Vector2, entity_radius: float = 5.0) -> bool:
        """Check if entity would collide with solid terrain"""
        # This would be expanded for more complex collision detection
        # For now, just ensure we're not in restricted areas
        for terrain in self.terrain_restrictions:
            if terrain.type == "mountain":  # Example of solid terrain
                terrain_pos = terrain.position
                terrain_size = terrain.size

                # Simple AABB collision
                if (terrain_pos.x - entity_radius <= position.x <= terrain_pos.x + terrain_size.x + entity_radius and
                    terrain_pos.y - entity_radius <= position.y <= terrain_pos.y + terrain_size.y + entity_radius):
                    return True

        return False

    def validate_spawn_position(self, position: Vector2, entity_type: str = "agent") -> Tuple[bool, Vector2]:
        """Validate a spawn position and return corrected position if needed"""
        if not self.is_position_valid(position):
            position = self.clamp_to_bounds(position)

        # Ensure not spawning in solid terrain
        if self.check_collision_with_terrain(position):
            position = self.get_nearest_safe_position(position)

        # For agents, prefer spawning in safe zones if available
        if entity_type == "agent" and self.safe_zones:
            if not self.is_in_safe_zone(position):
                # Try to spawn in first safe zone
                safe_zone = self.safe_zones[0]
                center = Vector2.from_tuple(safe_zone.get('center', [500, 500]))
                radius = safe_zone.get('radius', 100)

                # Random position within safe zone
                import random
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(0, radius * 0.8)  # Stay well within bounds
                position = Vector2(
                    center.x + distance * math.cos(angle),
                    center.y + distance * math.sin(angle)
                )

        return True, position