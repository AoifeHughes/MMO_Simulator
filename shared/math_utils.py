import math
from typing import Tuple

def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def normalize_angle(angle: float) -> float:
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle

def angle_between(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dy, dx))

def point_in_cone(origin: Tuple[float, float], direction: float, cone_angle: float,
                  cone_range: float, target: Tuple[float, float]) -> bool:
    dist = distance(origin, target)
    if dist > cone_range:
        return False

    angle_to_target = angle_between(origin, target)
    angle_diff = abs(normalize_angle(angle_to_target - direction))

    if angle_diff > 180:
        angle_diff = 360 - angle_diff

    return angle_diff <= cone_angle / 2

def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(value, max_val))