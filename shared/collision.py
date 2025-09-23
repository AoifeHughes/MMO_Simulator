"""
Collision detection system for the MMO simulator.
Handles boundary checking, agent-to-agent collisions, and obstacle collisions.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class CollisionBounds:
    """Defines the collision bounds for an entity"""

    x: float
    y: float
    radius: float


@dataclass
class CollisionResult:
    """Result of a collision check"""

    collided: bool
    correction_x: float = 0.0
    correction_y: float = 0.0
    collision_type: str = "none"


class CollisionDetector:
    """Handles all collision detection for the game world"""

    def __init__(self, world_width: int, world_height: int):
        self.world_width = world_width
        self.world_height = world_height
        self.agent_radius = 0.4  # Default agent collision radius

    def check_boundary_collision(
        self, x: float, y: float, radius: float = None
    ) -> CollisionResult:
        """Check if position would collide with world boundaries"""
        if radius is None:
            radius = self.agent_radius

        collision = CollisionResult(collided=False)

        # Check left boundary
        if x - radius < 0:
            collision.collided = True
            collision.correction_x = radius - x
            collision.collision_type = "boundary_left"

        # Check right boundary
        elif x + radius >= self.world_width:
            collision.collided = True
            collision.correction_x = (self.world_width - 1 - radius) - x
            collision.collision_type = "boundary_right"

        # Check top boundary
        if y - radius < 0:
            collision.collided = True
            collision.correction_y = radius - y
            collision.collision_type = (
                "boundary_top" if not collision.collided else "boundary_corner"
            )

        # Check bottom boundary
        elif y + radius >= self.world_height:
            collision.collided = True
            collision.correction_y = (self.world_height - 1 - radius) - y
            collision.collision_type = (
                "boundary_bottom" if not collision.collided else "boundary_corner"
            )

        return collision

    def check_agent_collision(
        self,
        pos1: Tuple[float, float],
        pos2: Tuple[float, float],
        radius1: float = None,
        radius2: float = None,
    ) -> CollisionResult:
        """Check collision between two agents"""
        if radius1 is None:
            radius1 = self.agent_radius
        if radius2 is None:
            radius2 = self.agent_radius

        x1, y1 = pos1
        x2, y2 = pos2

        # Calculate distance between centers
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx * dx + dy * dy)

        # Check if collision occurs
        min_distance = radius1 + radius2

        if distance < min_distance and distance > 0:
            # Calculate correction vector
            correction_factor = (min_distance - distance) / distance
            correction_x = (
                -dx * correction_factor * 0.5
            )  # Split correction between both agents
            correction_y = -dy * correction_factor * 0.5

            return CollisionResult(
                collided=True,
                correction_x=correction_x,
                correction_y=correction_y,
                collision_type="agent",
            )

        return CollisionResult(collided=False)

    def check_multiple_agent_collisions(
        self,
        agent_pos: Tuple[float, float],
        other_agents: List[Tuple[float, float]],
        radius: float = None,
    ) -> CollisionResult:
        """Check collision with multiple agents and return combined correction"""
        if radius is None:
            radius = self.agent_radius

        total_correction_x = 0.0
        total_correction_y = 0.0
        collision_count = 0

        for other_pos in other_agents:
            collision = self.check_agent_collision(agent_pos, other_pos, radius, radius)
            if collision.collided:
                total_correction_x += collision.correction_x
                total_correction_y += collision.correction_y
                collision_count += 1

        if collision_count > 0:
            return CollisionResult(
                collided=True,
                correction_x=total_correction_x,
                correction_y=total_correction_y,
                collision_type="multiple_agents",
            )

        return CollisionResult(collided=False)

    def is_position_valid(self, x: float, y: float, radius: float = None) -> bool:
        """Check if a position is valid (within bounds)"""
        if radius is None:
            radius = self.agent_radius

        return (
            radius <= x < self.world_width - radius
            and radius <= y < self.world_height - radius
        )

    def clamp_to_bounds(
        self, x: float, y: float, radius: float = None
    ) -> Tuple[float, float]:
        """Clamp position to valid bounds"""
        if radius is None:
            radius = self.agent_radius

        x = max(radius, min(self.world_width - radius - 0.01, x))
        y = max(radius, min(self.world_height - radius - 0.01, y))

        return x, y

    def resolve_movement_collision(
        self,
        current_pos: Tuple[float, float],
        intended_pos: Tuple[float, float],
        other_agents: List[Tuple[float, float]] = None,
        radius: float = None,
    ) -> Tuple[float, float]:
        """
        Resolve collisions for movement from current to intended position.
        Returns the final safe position.
        """
        if radius is None:
            radius = self.agent_radius

        intended_x, intended_y = intended_pos

        # First check boundary collision
        boundary_collision = self.check_boundary_collision(
            intended_x, intended_y, radius
        )
        if boundary_collision.collided:
            intended_x += boundary_collision.correction_x
            intended_y += boundary_collision.correction_y

        # Then check agent collisions if other agents provided
        if other_agents:
            agent_collision = self.check_multiple_agent_collisions(
                (intended_x, intended_y), other_agents, radius
            )
            if agent_collision.collided:
                intended_x += agent_collision.correction_x
                intended_y += agent_collision.correction_y

        # Final clamp to ensure we're in bounds
        return self.clamp_to_bounds(intended_x, intended_y, radius)

    def get_safe_spawn_position(
        self,
        existing_agents: List[Tuple[float, float]],
        attempts: int = 50,
        world_map=None,
    ) -> Tuple[float, float]:
        """Find a safe spawn position that doesn't collide with existing agents and is on walkable terrain"""
        import random

        for _ in range(attempts):
            # Try random position within bounds
            x = random.uniform(
                self.agent_radius + 1, self.world_width - self.agent_radius - 1
            )
            y = random.uniform(
                self.agent_radius + 1, self.world_height - self.agent_radius - 1
            )

            # Check if position is on walkable terrain
            if world_map and not world_map.is_walkable(int(x), int(y)):
                continue

            # Check if it collides with any existing agent
            collision = self.check_multiple_agent_collisions((x, y), existing_agents)
            if not collision.collided:
                return x, y

        # Fallback: find any walkable position near center
        if world_map:
            center_x, center_y = self.world_width // 2, self.world_height // 2
            for radius in range(1, min(self.world_width, self.world_height) // 4):
                for angle_deg in range(0, 360, 30):  # Check every 30 degrees
                    angle_rad = math.radians(angle_deg)
                    test_x = center_x + radius * math.cos(angle_rad)
                    test_y = center_y + radius * math.sin(angle_rad)

                    # Ensure within bounds
                    if not self.is_position_valid(test_x, test_y):
                        continue

                    # Check if walkable
                    if world_map.is_walkable(int(test_x), int(test_y)):
                        collision = self.check_multiple_agent_collisions(
                            (test_x, test_y), existing_agents
                        )
                        if not collision.collided:
                            return test_x, test_y

        # Last fallback to center if no safe position found
        return self.world_width / 2, self.world_height / 2
