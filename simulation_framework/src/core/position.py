from __future__ import annotations
import math
from typing import Tuple, Union


class Position:
    """Represents a 2D position in the game world"""

    def __init__(self, x: Union[int, float], y: Union[int, float]):
        self.x = x
        self.y = y

    def distance_to(self, other: Position) -> float:
        """Calculate Euclidean distance to another position"""
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

    def manhattan_distance_to(self, other: Position) -> int:
        """Calculate Manhattan distance to another position"""
        return abs(int(self.x - other.x)) + abs(int(self.y - other.y))

    def is_adjacent_to(self, other: Position, diagonal: bool = True) -> bool:
        """Check if this position is adjacent to another position"""
        dx = abs(self.x - other.x)
        dy = abs(self.y - other.y)

        if diagonal:
            return dx <= 1 and dy <= 1 and (dx > 0 or dy > 0)
        else:
            return (dx == 1 and dy == 0) or (dx == 0 and dy == 1)

    def get_direction_to(self, other: Position) -> Tuple[int, int]:
        """Get the direction vector to another position (normalized to -1, 0, 1)"""
        dx = other.x - self.x
        dy = other.y - self.y

        # Normalize to -1, 0, or 1
        if dx > 0:
            dx = 1
        elif dx < 0:
            dx = -1
        else:
            dx = 0

        if dy > 0:
            dy = 1
        elif dy < 0:
            dy = -1
        else:
            dy = 0

        return (dx, dy)

    def move_towards(self, other: Position, distance: float = 1.0) -> Position:
        """Create a new position moved towards another position by a given distance"""
        if self.distance_to(other) == 0:
            return Position(self.x, self.y)

        dx = other.x - self.x
        dy = other.y - self.y
        current_distance = math.sqrt(dx * dx + dy * dy)

        # Normalize and scale by desired distance
        scale = distance / current_distance
        new_x = self.x + dx * scale
        new_y = self.y + dy * scale

        return Position(new_x, new_y)

    def copy(self) -> Position:
        """Create a copy of this position"""
        return Position(self.x, self.y)

    def to_tuple(self) -> Tuple[Union[int, float], Union[int, float]]:
        """Convert to tuple format"""
        return (self.x, self.y)

    def to_int_tuple(self) -> Tuple[int, int]:
        """Convert to integer tuple format"""
        return (int(self.x), int(self.y))

    @classmethod
    def from_tuple(cls, coords: Tuple[Union[int, float], Union[int, float]]) -> Position:
        """Create position from tuple"""
        return cls(coords[0], coords[1])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __str__(self) -> str:
        return f"Position({self.x}, {self.y})"

    def __repr__(self) -> str:
        return f"Position(x={self.x}, y={self.y})"

    def __add__(self, other: Position) -> Position:
        return Position(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Position) -> Position:
        return Position(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: Union[int, float]) -> Position:
        return Position(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: Union[int, float]) -> Position:
        return Position(self.x / scalar, self.y / scalar)