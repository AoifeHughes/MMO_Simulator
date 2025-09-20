"""
Shared mathematical utilities
"""

import math
from typing import Tuple, Optional


class Vector2:
    """2D vector for position and movement"""

    def __init__(self, x: float = 0, y: float = 0):
        self.x = x
        self.y = y

    def distance_to(self, other: 'Vector2') -> float:
        """Calculate distance to another vector"""
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

    def normalize(self) -> 'Vector2':
        """Return normalized vector"""
        magnitude = self.magnitude()
        if magnitude > 0:
            return Vector2(self.x / magnitude, self.y / magnitude)
        return Vector2(0, 0)

    def magnitude(self) -> float:
        """Get vector magnitude"""
        return math.sqrt(self.x * self.x + self.y * self.y)

    def __add__(self, other: 'Vector2') -> 'Vector2':
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: 'Vector2') -> 'Vector2':
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> 'Vector2':
        return Vector2(self.x * scalar, self.y * scalar)

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    @staticmethod
    def from_tuple(t: Tuple[float, float]) -> 'Vector2':
        return Vector2(t[0], t[1])

    def __repr__(self):
        return f"Vector2({self.x:.2f}, {self.y:.2f})"


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max"""
    return max(min_val, min(value, max_val))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b"""
    return a + (b - a) * t


def angle_between(v1: Vector2, v2: Vector2) -> float:
    """Calculate angle between two vectors in radians"""
    dot = v1.x * v2.x + v1.y * v2.y
    det = v1.x * v2.y - v1.y * v2.x
    return math.atan2(det, dot)


def point_in_circle(point: Vector2, center: Vector2, radius: float) -> bool:
    """Check if point is inside circle"""
    return point.distance_to(center) <= radius


def point_in_rect(point: Vector2, rect_pos: Vector2, rect_size: Vector2) -> bool:
    """Check if point is inside rectangle"""
    return (rect_pos.x <= point.x <= rect_pos.x + rect_size.x and
            rect_pos.y <= point.y <= rect_pos.y + rect_size.y)


def circle_intersects_rect(circle_center: Vector2, radius: float,
                          rect_pos: Vector2, rect_size: Vector2) -> bool:
    """Check if circle intersects with rectangle"""
    closest_x = clamp(circle_center.x, rect_pos.x, rect_pos.x + rect_size.x)
    closest_y = clamp(circle_center.y, rect_pos.y, rect_pos.y + rect_size.y)
    closest = Vector2(closest_x, closest_y)
    return circle_center.distance_to(closest) <= radius


def raycast(origin: Vector2, direction: Vector2, max_distance: float,
           obstacles: list) -> Optional[Tuple[Vector2, float]]:
    """Simple raycast against list of obstacles
    Returns (hit_point, distance) or None"""
    # Simplified for now - would need proper implementation
    return None