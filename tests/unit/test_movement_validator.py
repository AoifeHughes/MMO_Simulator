"""
Unit tests for movement validation system.

Tests movement validation logic used to reduce server-client conflicts
by pre-validating movements before sending to the server.
"""

import pytest
from client.movement_validator import MovementValidator


class TestMovementValidator:
    """Test the movement validation system."""

    def test_validator_initialization(self):
        """Test movement validator initialization."""
        validator = MovementValidator("test_agent_123")
        assert validator.agent_id == "test_agent_123"
        assert validator.max_single_movement == 10.0
        assert validator.max_speed == 5.0
        assert validator.min_movement_distance == 0.1

    def test_validate_movement_distance_valid(self):
        """Test validation of valid movement distances."""
        validator = MovementValidator("agent1")

        # Valid movements within limits
        assert validator.validate_movement_distance((0, 0), (5, 0)) is True
        assert validator.validate_movement_distance((0, 0), (3, 4)) is True  # 5 units
        assert validator.validate_movement_distance((10, 10), (15, 15)) is True

    def test_validate_movement_distance_too_far(self):
        """Test validation rejects movements that are too far."""
        validator = MovementValidator("agent1")

        # Movements exceeding max_single_movement (10.0)
        assert validator.validate_movement_distance((0, 0), (15, 0)) is False
        assert validator.validate_movement_distance((0, 0), (8, 8)) is False  # ~11.3 units

    def test_validate_movement_distance_too_small(self):
        """Test validation rejects movements that are too small."""
        validator = MovementValidator("agent1")

        # Movements below min_movement_distance (0.1)
        assert validator.validate_movement_distance((0, 0), (0.05, 0)) is False
        assert validator.validate_movement_distance((10, 10), (10.01, 10.01)) is False

    def test_validate_movement_distance_zero(self):
        """Test validation of zero distance movements."""
        validator = MovementValidator("agent1")

        # Zero movement (same position)
        assert validator.validate_movement_distance((5, 5), (5, 5)) is False

    def test_validate_movement_distance_edge_cases(self):
        """Test validation at exact boundaries."""
        validator = MovementValidator("agent1")

        # Exactly at max distance (10.0)
        assert validator.validate_movement_distance((0, 0), (6, 8)) is True  # Exactly 10

        # Exactly at min distance (0.1)
        assert validator.validate_movement_distance((0, 0), (0.1, 0)) is True

    def test_validate_movement_speed_valid(self):
        """Test validation of valid movement speeds."""
        validator = MovementValidator("agent1")

        # Valid speeds within limits
        assert validator.validate_movement_speed((0, 0), (2, 0), 1.0) is True  # 2 units/sec
        assert validator.validate_movement_speed((0, 0), (5, 0), 1.0) is True  # 5 units/sec
        assert validator.validate_movement_speed((0, 0), (3, 4), 1.0) is True  # 5 units/sec

    def test_validate_movement_speed_too_fast(self):
        """Test validation rejects movements that are too fast."""
        validator = MovementValidator("agent1")

        # Speeds exceeding max_speed (5.0 units/sec)
        assert validator.validate_movement_speed((0, 0), (10, 0), 1.0) is False  # 10 units/sec
        assert validator.validate_movement_speed((0, 0), (5, 0), 0.5) is False  # 10 units/sec

    def test_validate_movement_speed_zero_time(self):
        """Test validation with zero delta time."""
        validator = MovementValidator("agent1")

        # Zero time should be handled gracefully
        result = validator.validate_movement_speed((0, 0), (2, 0), 0.0)
        assert result is False  # Should reject infinite speed

    def test_validate_movement_speed_very_slow(self):
        """Test validation of very slow movements."""
        validator = MovementValidator("agent1")

        # Very slow movement (should be valid)
        assert validator.validate_movement_speed((0, 0), (0.1, 0), 1.0) is True  # 0.1 units/sec

    def test_validate_world_bounds_valid(self):
        """Test validation of positions within world bounds."""
        validator = MovementValidator("agent1")
        validator.set_world_bounds(100, 50)

        # Valid positions within bounds
        assert validator.validate_world_bounds((50, 25)) is True
        assert validator.validate_world_bounds((0, 0)) is True
        assert validator.validate_world_bounds((99, 49)) is True

    def test_validate_world_bounds_invalid(self):
        """Test validation rejects positions outside world bounds."""
        validator = MovementValidator("agent1")
        validator.set_world_bounds(100, 50)

        # Invalid positions outside bounds
        assert validator.validate_world_bounds((-1, 25)) is False
        assert validator.validate_world_bounds((100, 25)) is False
        assert validator.validate_world_bounds((50, -1)) is False
        assert validator.validate_world_bounds((50, 50)) is False

    def test_validate_world_bounds_no_bounds_set(self):
        """Test validation when world bounds are not set."""
        validator = MovementValidator("agent1")

        # Should accept any position when bounds not set
        assert validator.validate_world_bounds((0, 0)) is True
        assert validator.validate_world_bounds((-100, -100)) is True
        assert validator.validate_world_bounds((1000, 1000)) is True

    def test_set_world_bounds(self):
        """Test setting world bounds."""
        validator = MovementValidator("agent1")

        validator.set_world_bounds(200, 150)
        assert validator.world_width == 200
        assert validator.world_height == 150

    def test_validate_complete_movement_valid(self):
        """Test complete movement validation with all checks."""
        validator = MovementValidator("agent1")
        validator.set_world_bounds(100, 100)

        # Valid movement: reasonable distance, speed, and within bounds
        result = validator.validate_complete_movement(
            current_pos=(10, 10),
            target_pos=(13, 14),  # ~5 units distance in 1 sec = 5 units/sec (within limit)
            delta_time=1.0
        )
        assert result is True

    def test_validate_complete_movement_invalid_distance(self):
        """Test complete movement validation fails on distance."""
        validator = MovementValidator("agent1")
        validator.set_world_bounds(100, 100)

        # Invalid: too far
        result = validator.validate_complete_movement(
            current_pos=(0, 0),
            target_pos=(20, 0),  # 20 units > max of 10
            delta_time=1.0
        )
        assert result is False

    def test_validate_complete_movement_invalid_speed(self):
        """Test complete movement validation fails on speed."""
        validator = MovementValidator("agent1")
        validator.set_world_bounds(100, 100)

        # Invalid: too fast
        result = validator.validate_complete_movement(
            current_pos=(0, 0),
            target_pos=(8, 0),  # 8 units in 0.5 sec = 16 units/sec > max of 5
            delta_time=0.5
        )
        assert result is False

    def test_validate_complete_movement_invalid_bounds(self):
        """Test complete movement validation fails on bounds."""
        validator = MovementValidator("agent1")
        validator.set_world_bounds(100, 100)

        # Invalid: outside world bounds
        result = validator.validate_complete_movement(
            current_pos=(95, 95),
            target_pos=(105, 105),  # Outside 100x100 world
            delta_time=1.0
        )
        assert result is False

    def test_custom_validation_parameters(self):
        """Test validator with custom parameters."""
        validator = MovementValidator("agent1")

        # Modify validation parameters
        validator.max_single_movement = 20.0
        validator.max_speed = 10.0
        validator.min_movement_distance = 0.5

        # Test with new parameters
        assert validator.validate_movement_distance((0, 0), (15, 0)) is True  # Was too far
        assert validator.validate_movement_distance((0, 0), (0.1, 0)) is False  # Now too small
        assert validator.validate_movement_speed((0, 0), (8, 0), 1.0) is True  # Was too fast

    def test_negative_coordinates(self):
        """Test validation with negative coordinates."""
        validator = MovementValidator("agent1")

        # Distance validation should work with negative coordinates
        assert validator.validate_movement_distance((-5, -5), (0, 0)) is True  # ~7.07 units
        assert validator.validate_movement_distance((-10, 0), (10, 0)) is False  # 20 units

    def test_floating_point_precision(self):
        """Test validation with floating point precision."""
        validator = MovementValidator("agent1")

        # Test with very precise floating point numbers
        assert validator.validate_movement_distance(
            (0.123456789, 0.987654321),
            (5.123456789, 4.987654321)
        ) is True

        # Test at exact boundaries with floating point
        assert validator.validate_movement_distance((0.0, 0.0), (6.0, 8.0)) is True  # Exactly 10.0