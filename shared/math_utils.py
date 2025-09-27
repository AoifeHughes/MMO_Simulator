"""
Mathematical utility functions for game physics and spatial calculations.

This module provides core mathematical operations used throughout the MMO
simulator for position calculations, angle computations, and geometric
operations essential for movement, combat, and AI decision making.
"""

import math
from typing import Tuple


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    Calculate Euclidean distance between two 2D points.

    Args:
        p1: First point as (x, y) tuple
        p2: Second point as (x, y) tuple

    Returns:
        Distance between the points as a float

    Example:
        >>> distance((0, 0), (3, 4))
        5.0
    """
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def normalize_angle(angle: float) -> float:
    """
    Normalize angle to [0, 360) degree range.

    Args:
        angle: Angle in degrees (can be any value)

    Returns:
        Equivalent angle in [0, 360) range

    Example:
        >>> normalize_angle(-90)
        270.0
        >>> normalize_angle(450)
        90.0
    """
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle


def angle_between(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    Calculate angle from point p1 to point p2 in degrees.

    Args:
        p1: Starting point as (x, y) tuple
        p2: Target point as (x, y) tuple

    Returns:
        Angle in degrees where 0° = East, 90° = North, etc.
        Range: [-180, 180]

    Example:
        >>> angle_between((0, 0), (1, 1))
        45.0
    """
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx))


def point_in_cone(
    origin: Tuple[float, float],
    direction: float,
    cone_angle: float,
    cone_range: float,
    target: Tuple[float, float],
) -> bool:
    """
    Check if a target point lies within a cone of vision/attack.

    Useful for line-of-sight calculations, attack range validation,
    and AI perception systems.

    Args:
        origin: Center point of the cone as (x, y) tuple
        direction: Cone's central direction in degrees (0° = East)
        cone_angle: Total cone width in degrees (e.g., 60° for ±30° spread)
        cone_range: Maximum distance the cone extends
        target: Point to test as (x, y) tuple

    Returns:
        True if target is within the cone, False otherwise

    Example:
        >>> # 90° cone facing north, range 10
        >>> point_in_cone((0, 0), 90, 90, 10, (1, 5))
        True
        >>> point_in_cone((0, 0), 90, 90, 10, (15, 0))  # Too far
        False
    """
    dist = distance(origin, target)
    if dist > cone_range:
        return False

    angle_to_target = angle_between(origin, target)
    angle_diff = abs(normalize_angle(angle_to_target - direction))

    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    return angle_diff <= cone_angle / 2


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Constrain a value to a specified range.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Value clamped to [min_val, max_val] range

    Example:
        >>> clamp(15, 0, 10)
        10
        >>> clamp(-5, 0, 10)
        0
        >>> clamp(5, 0, 10)
        5
    """
    return max(min_val, min(value, max_val))
