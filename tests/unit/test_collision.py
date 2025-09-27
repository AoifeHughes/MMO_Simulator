"""
Unit tests for collision detection system.

Tests cover boundary checking, entity-to-entity collisions, and collision
resolution for the MMO simulator's physics system.
"""

import pytest

from shared.collision import CollisionBounds, CollisionDetector, CollisionResult


class TestCollisionDetector:
    """Test the main collision detection system."""

    def test_collision_detector_initialization(self):
        """Test collision detector initialization."""
        detector = CollisionDetector(100, 50)
        assert detector.world_width == 100
        assert detector.world_height == 50

    def test_is_position_valid_true(self):
        """Test valid positions within world bounds."""
        detector = CollisionDetector(100, 50)

        # Test center
        assert detector.is_position_valid(50, 25) is True

        # Test edges (valid with default radius)
        assert detector.is_position_valid(5, 5) is True
        assert detector.is_position_valid(95, 45) is True

    def test_is_position_valid_false(self):
        """Test invalid positions outside world bounds."""
        detector = CollisionDetector(100, 50)

        # Test outside bounds
        assert detector.is_position_valid(-1, 25) is False
        assert detector.is_position_valid(100, 25) is False
        assert detector.is_position_valid(50, -1) is False
        assert detector.is_position_valid(50, 50) is False

        # Test far outside bounds
        assert detector.is_position_valid(-100, 25) is False
        assert detector.is_position_valid(200, 25) is False

    def test_check_agent_collision_no_collision(self):
        """Test agents that don't collide."""
        detector = CollisionDetector(100, 100)

        # Check collision between two distant positions
        result = detector.check_agent_collision((10, 10), (20, 20))
        assert result.collided is False
        assert result.correction_x == 0.0
        assert result.correction_y == 0.0

    def test_check_agent_collision_touching(self):
        """Test entities that are just touching."""
        detector = CollisionDetector(100, 100)

        # Entities with radius 1 each, 2 units apart (just touching)
        entity1 = CollisionBounds(10, 10, 1)
        entity2 = CollisionBounds(12, 10, 1)

        result = detector.check_agent_collision(
            (entity1.x, entity1.y),
            (entity2.x, entity2.y),
            entity1.radius,
            entity2.radius,
        )
        # Touching should not count as collision for most physics systems
        assert result.collided is False

    def test_check_agent_collision_overlapping(self):
        """Test entities that overlap."""
        detector = CollisionDetector(100, 100)

        # Entities with radius 1 each, 1.5 units apart (overlapping)
        entity1 = CollisionBounds(10, 10, 1)
        entity2 = CollisionBounds(11.5, 10, 1)

        result = detector.check_agent_collision(
            (entity1.x, entity1.y),
            (entity2.x, entity2.y),
            entity1.radius,
            entity2.radius,
        )
        assert result.collided is True
        assert result.correction_x != 0.0  # Should have correction

    def test_check_agent_collision_same_position(self):
        """Test entities at exactly the same position."""
        detector = CollisionDetector(100, 100)

        entity1 = CollisionBounds(10, 10, 1)
        entity2 = CollisionBounds(10, 10, 1)

        result = detector.check_agent_collision(
            (entity1.x, entity1.y),
            (entity2.x, entity2.y),
            entity1.radius,
            entity2.radius,
        )
        assert result.collided is True

    def test_check_agent_collision_different_radii(self):
        """Test entities with different collision radii."""
        detector = CollisionDetector(100, 100)

        # Large entity (radius 5) and small entity (radius 1)
        large_entity = CollisionBounds(10, 10, 5)
        small_entity = CollisionBounds(14, 10, 1)  # 4 units away

        result = detector.check_agent_collision(
            (large_entity.x, large_entity.y),
            (small_entity.x, small_entity.y),
            large_entity.radius,
            small_entity.radius,
        )
        assert result.collided is True  # 4 < (5 + 1)

    def test_check_agent_collision_vertical_separation(self):
        """Test entities separated vertically."""
        detector = CollisionDetector(100, 100)

        entity1 = CollisionBounds(10, 10, 1)
        entity2 = CollisionBounds(10, 15, 1)  # 5 units vertically apart

        result = detector.check_agent_collision(
            (entity1.x, entity1.y),
            (entity2.x, entity2.y),
            entity1.radius,
            entity2.radius,
        )
        assert result.collided is False  # 5 > (1 + 1)

    def test_check_agent_collision_diagonal(self):
        """Test entities separated diagonally."""
        detector = CollisionDetector(100, 100)

        entity1 = CollisionBounds(0, 0, 1)
        entity2 = CollisionBounds(3, 4, 1)  # 5 units away (3-4-5 triangle)

        result = detector.check_agent_collision(
            (entity1.x, entity1.y),
            (entity2.x, entity2.y),
            entity1.radius,
            entity2.radius,
        )
        assert result.collided is False  # 5 > (1 + 1)

    def test_check_boundary_collision_valid_positions(self):
        """Test boundary collision for valid positions."""
        detector = CollisionDetector(100, 50)

        # Entity well within bounds
        entity = CollisionBounds(50, 25, 5)
        result = detector.check_boundary_collision(entity.x, entity.y, entity.radius)
        assert result.collided is False

    def test_check_boundary_collision_edge_positions(self):
        """Test boundary collision at world edges."""
        detector = CollisionDetector(100, 50)

        # Entity at left edge (radius extends beyond boundary)
        entity = CollisionBounds(2, 25, 5)  # x=2, radius=5, so extends to x=-3
        result = detector.check_boundary_collision(entity.x, entity.y, entity.radius)
        assert result.collided is True
        assert result.correction_x > 0  # Should push right

    def test_check_boundary_collision_corner(self):
        """Test boundary collision at world corner."""
        detector = CollisionDetector(100, 50)

        # Entity at bottom-left corner
        entity = CollisionBounds(3, 3, 5)  # Extends beyond both boundaries
        result = detector.check_boundary_collision(entity.x, entity.y, entity.radius)
        assert result.collided is True
        assert result.correction_x > 0  # Push right
        assert result.correction_y > 0  # Push up

    def test_multiple_entity_collision_detection(self):
        """Test collision detection with multiple entities."""
        detector = CollisionDetector(100, 100)

        entities = [
            CollisionBounds(10, 10, 2),
            CollisionBounds(20, 10, 2),
            CollisionBounds(30, 10, 2),
            CollisionBounds(11, 11, 1),  # This one should collide with first
        ]

        # Check collisions between all pairs
        collisions = []
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                result = detector.check_agent_collision(
                    (entities[i].x, entities[i].y),
                    (entities[j].x, entities[j].y),
                    entities[i].radius,
                    entities[j].radius,
                )
                if result.collided:
                    collisions.append((i, j))

        # Should detect collision between entity 0 and entity 3
        assert len(collisions) >= 1
        assert (0, 3) in collisions or (3, 0) in collisions


class TestCollisionBounds:
    """Test the CollisionBounds data structure."""

    def test_collision_bounds_creation(self):
        """Test creating collision bounds."""
        bounds = CollisionBounds(10.5, 20.3, 2.5)
        assert bounds.x == 10.5
        assert bounds.y == 20.3
        assert bounds.radius == 2.5

    def test_collision_bounds_zero_radius(self):
        """Test collision bounds with zero radius."""
        bounds = CollisionBounds(10, 10, 0)
        assert bounds.radius == 0

    def test_collision_bounds_negative_position(self):
        """Test collision bounds with negative coordinates."""
        bounds = CollisionBounds(-5, -10, 1)
        assert bounds.x == -5
        assert bounds.y == -10


class TestCollisionResult:
    """Test the CollisionResult data structure."""

    def test_collision_result_no_collision(self):
        """Test collision result for no collision."""
        result = CollisionResult(False)
        assert result.collided is False
        assert result.correction_x == 0.0
        assert result.correction_y == 0.0
        assert result.collision_type == "none"

    def test_collision_result_with_collision(self):
        """Test collision result with collision data."""
        result = CollisionResult(
            True, correction_x=2.5, correction_y=-1.0, collision_type="entity"
        )
        assert result.collided is True
        assert result.correction_x == 2.5
        assert result.correction_y == -1.0
        assert result.collision_type == "entity"

    def test_collision_result_boundary_type(self):
        """Test collision result for boundary collision."""
        result = CollisionResult(
            True, correction_x=0.0, correction_y=3.0, collision_type="boundary"
        )
        assert result.collided is True
        assert result.collision_type == "boundary"


class TestCollisionDetectorEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_size_world(self):
        """Test collision detector with zero-size world."""
        detector = CollisionDetector(0, 0)
        assert detector.world_width == 0
        assert detector.world_height == 0

        # Any position should be out of bounds in a zero-size world
        # Check if 0,0 is within bounds (no collision means within bounds)
        result = detector.check_boundary_collision(0, 0)
        assert result.collided is True  # 0,0 should be invalid in zero-size world
        result = detector.check_boundary_collision(1, 1)
        assert (
            result.collided is True
        )  # 1,1 should be out of bounds for zero-size world

    def test_very_large_world(self):
        """Test collision detector with very large world."""
        detector = CollisionDetector(10000, 10000)
        result = detector.check_boundary_collision(5000, 5000)
        assert result.collided is False  # Should be within bounds
        result = detector.check_boundary_collision(9999, 9999)
        assert result.collided is False  # Should be within bounds
        result = detector.check_boundary_collision(10000, 10000)
        assert result.collided is True  # Should be out of bounds

    def test_floating_point_precision(self):
        """Test collision detection with floating point precision."""
        detector = CollisionDetector(100, 100)

        # Very close but not colliding
        entity1 = CollisionBounds(10.0, 10.0, 1.0)
        entity2 = CollisionBounds(12.000001, 10.0, 1.0)  # Just over 2 units apart

        result = detector.check_agent_collision(
            (entity1.x, entity1.y),
            (entity2.x, entity2.y),
            entity1.radius,
            entity2.radius,
        )
        assert result.collided is False

    def test_very_small_radii(self):
        """Test collision detection with very small radii."""
        detector = CollisionDetector(100, 100)

        entity1 = CollisionBounds(10, 10, 0.001)
        entity2 = CollisionBounds(10.001, 10, 0.001)

        result = detector.check_agent_collision(
            (entity1.x, entity1.y),
            (entity2.x, entity2.y),
            entity1.radius,
            entity2.radius,
        )
        assert result.collided is True  # 0.001 < (0.001 + 0.001)
