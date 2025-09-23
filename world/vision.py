import math
from typing import List, Optional, Tuple

from shared.math_utils import distance, point_in_cone
from world.map import WorldMap


class VisionSystem:
    def __init__(self, world_map: WorldMap):
        self.world_map = world_map

    def get_visible_positions(
        self,
        origin: Tuple[float, float],
        direction: float,
        cone_angle: float,
        vision_range: float,
    ) -> List[Tuple[int, int]]:
        visible_positions = []
        origin_tile = (int(origin[0]), int(origin[1]))

        search_radius = int(vision_range) + 1

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                tile_x = origin_tile[0] + dx
                tile_y = origin_tile[1] + dy

                if not self.world_map.is_valid_position(tile_x, tile_y):
                    continue

                tile_center = (tile_x + 0.5, tile_y + 0.5)

                if not point_in_cone(
                    origin, direction, cone_angle, vision_range, tile_center
                ):
                    continue

                if self.has_line_of_sight(origin, tile_center):
                    visible_positions.append((tile_x, tile_y))

        return visible_positions

    def has_line_of_sight(
        self, start: Tuple[float, float], end: Tuple[float, float]
    ) -> bool:
        x1, y1 = start
        x2, y2 = end

        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        steps = int(max(dx, dy) * 2)
        if steps == 0:
            return True

        x_step = (x2 - x1) / steps
        y_step = (y2 - y1) / steps

        for i in range(1, steps):
            x = x1 + x_step * i
            y = y1 + y_step * i

            tile_x = int(x)
            tile_y = int(y)

            if self.world_map.blocks_vision(tile_x, tile_y):
                return False

        return True

    def get_entities_in_vision(
        self,
        origin: Tuple[float, float],
        direction: float,
        cone_angle: float,
        vision_range: float,
        entities: List[Tuple[str, Tuple[float, float]]],
    ) -> List[str]:
        visible_entities = []

        for entity_id, entity_pos in entities:
            if point_in_cone(origin, direction, cone_angle, vision_range, entity_pos):
                if self.has_line_of_sight(origin, entity_pos):
                    visible_entities.append(entity_id)

        return visible_entities
