"""
Unit tests for shared mathematical utility functions.

Tests cover edge cases, boundary conditions, and typical usage patterns
for all mathematical operations used throughout the MMO simulator.
"""

import math
import pytest
from shared.math_utils import distance, normalize_angle, angle_between, point_in_cone, clamp


class TestDistance:
    """Test the distance calculation function."""

    def test_distance_zero(self):
        """Test distance between identical points."""
        assert distance((0, 0), (0, 0)) == 0.0
        assert distance((5, 3), (5, 3)) == 0.0

    def test_distance_horizontal(self):
        """Test distance along horizontal line."""
        assert distance((0, 0), (3, 0)) == 3.0
        assert distance((1, 5), (4, 5)) == 3.0

    def test_distance_vertical(self):
        """Test distance along vertical line."""
        assert distance((0, 0), (0, 4)) == 4.0
        assert distance((3, 1), (3, 6)) == 5.0

    def test_distance_diagonal(self):
        """Test distance along diagonal (Pythagorean theorem)."""
        assert distance((0, 0), (3, 4)) == 5.0
        assert distance((0, 0), (1, 1)) == pytest.approx(math.sqrt(2))

    def test_distance_negative_coordinates(self):
        """Test distance with negative coordinates."""
        assert distance((-1, -1), (2, 3)) == 5.0
        assert distance((-5, 0), (0, 0)) == 5.0

    def test_distance_large_numbers(self):
        """Test distance with large coordinates."""
        assert distance((0, 0), (1000, 0)) == 1000.0
        assert distance((1000, 1000), (1003, 1004)) == 5.0


class TestNormalizeAngle:
    """Test angle normalization to [0, 360) range."""

    def test_normalize_zero(self):
        """Test normalization of zero."""
        assert normalize_angle(0) == 0.0

    def test_normalize_positive_in_range(self):
        """Test angles already in [0, 360) range."""
        assert normalize_angle(90) == 90.0
        assert normalize_angle(180) == 180.0
        assert normalize_angle(359.9) == 359.9

    def test_normalize_positive_above_360(self):
        """Test angles above 360 degrees."""
        assert normalize_angle(360) == 0.0
        assert normalize_angle(450) == 90.0
        assert normalize_angle(720) == 0.0
        assert normalize_angle(810) == 90.0

    def test_normalize_negative(self):
        """Test negative angles."""
        assert normalize_angle(-90) == 270.0
        assert normalize_angle(-180) == 180.0
        assert normalize_angle(-270) == 90.0
        assert normalize_angle(-360) == 0.0

    def test_normalize_large_negative(self):
        """Test large negative angles."""
        assert normalize_angle(-450) == 270.0
        assert normalize_angle(-720) == 0.0

    def test_normalize_floating_point(self):
        """Test floating point angles."""
        assert normalize_angle(45.5) == 45.5
        assert normalize_angle(-45.5) == 314.5


class TestAngleBetween:
    """Test angle calculation between two points."""

    def test_angle_east(self):
        """Test angle pointing east (0 degrees)."""
        angle = angle_between((0, 0), (1, 0))
        assert angle == pytest.approx(0.0)

    def test_angle_north(self):
        """Test angle pointing north (90 degrees)."""
        angle = angle_between((0, 0), (0, 1))
        assert angle == pytest.approx(90.0)

    def test_angle_west(self):
        """Test angle pointing west (180 degrees)."""
        angle = angle_between((0, 0), (-1, 0))
        assert angle == pytest.approx(180.0)

    def test_angle_south(self):
        """Test angle pointing south (-90 degrees)."""
        angle = angle_between((0, 0), (0, -1))
        assert angle == pytest.approx(-90.0)

    def test_angle_northeast(self):
        """Test angle pointing northeast (45 degrees)."""
        angle = angle_between((0, 0), (1, 1))
        assert angle == pytest.approx(45.0)

    def test_angle_southwest(self):
        """Test angle pointing southwest (-135 degrees)."""
        angle = angle_between((0, 0), (-1, -1))
        assert angle == pytest.approx(-135.0)

    def test_angle_identical_points(self):
        """Test angle between identical points (undefined, returns 0)."""
        angle = angle_between((5, 5), (5, 5))
        assert angle == pytest.approx(0.0)

    def test_angle_offset_origin(self):
        """Test angle calculation with non-origin starting point."""
        angle = angle_between((2, 3), (3, 3))
        assert angle == pytest.approx(0.0)  # East
        angle = angle_between((2, 3), (2, 4))
        assert angle == pytest.approx(90.0)  # North


class TestPointInCone:
    """Test cone containment checking."""

    def test_point_in_cone_center(self):
        """Test point directly in front of cone."""
        # Cone facing east (0°), 90° wide, range 10
        assert point_in_cone((0, 0), 0, 90, 10, (5, 0)) is True

    def test_point_in_cone_edge(self):
        """Test point at edge of cone."""
        # Cone facing east (0°), 90° wide (±45°)
        assert point_in_cone((0, 0), 0, 90, 10, (5, 5)) is True  # 45° from center
        assert point_in_cone((0, 0), 0, 90, 10, (5, -5)) is True  # -45° from center

    def test_point_outside_cone_angle(self):
        """Test point outside cone's angular range."""
        # Cone facing east (0°), 90° wide
        assert point_in_cone((0, 0), 0, 90, 10, (0, 5)) is False  # 90° from center
        assert point_in_cone((0, 0), 0, 90, 10, (-5, 0)) is False  # 180° from center

    def test_point_outside_cone_range(self):
        """Test point outside cone's distance range."""
        # Cone facing east (0°), range 5
        assert point_in_cone((0, 0), 0, 90, 5, (10, 0)) is False  # Too far

    def test_point_in_cone_north_facing(self):
        """Test cone facing north."""
        # Cone facing north (90°), 60° wide
        assert point_in_cone((0, 0), 90, 60, 10, (0, 5)) is True  # Dead center
        assert point_in_cone((0, 0), 90, 60, 10, (2, 5)) is True  # Slight angle
        assert point_in_cone((0, 0), 90, 60, 10, (5, 0)) is False  # East, outside cone

    def test_point_in_cone_narrow(self):
        """Test very narrow cone."""
        # 10° cone facing east
        assert point_in_cone((0, 0), 0, 10, 10, (10, 0)) is True  # Center
        assert point_in_cone((0, 0), 0, 10, 10, (10, 1)) is False  # Just outside

    def test_point_in_cone_wide(self):
        """Test very wide cone (nearly 360°)."""
        # 350° cone facing east (excludes 10° slice around west)
        assert point_in_cone((0, 0), 0, 350, 10, (5, 0)) is True  # East
        assert point_in_cone((0, 0), 0, 350, 10, (0, 5)) is True  # North
        assert point_in_cone((0, 0), 0, 350, 10, (-4, 3)) is True  # Northwest, inside cone
        assert point_in_cone((0, 0), 0, 350, 10, (0, -5)) is True  # South
        assert point_in_cone((0, 0), 0, 350, 10, (-5, 0)) is False  # West, outside narrow exclusion

    def test_point_in_cone_offset_origin(self):
        """Test cone with non-origin center."""
        assert point_in_cone((5, 5), 0, 90, 10, (10, 5)) is True  # East from (5,5)
        assert point_in_cone((5, 5), 90, 90, 10, (5, 10)) is True  # North from (5,5)


class TestClamp:
    """Test value clamping to specified ranges."""

    def test_clamp_within_range(self):
        """Test values already within range."""
        assert clamp(5, 0, 10) == 5
        assert clamp(0, 0, 10) == 0  # Lower bound
        assert clamp(10, 0, 10) == 10  # Upper bound

    def test_clamp_below_range(self):
        """Test values below minimum."""
        assert clamp(-5, 0, 10) == 0
        assert clamp(-100, 0, 10) == 0

    def test_clamp_above_range(self):
        """Test values above maximum."""
        assert clamp(15, 0, 10) == 10
        assert clamp(100, 0, 10) == 10

    def test_clamp_negative_range(self):
        """Test clamping with negative range."""
        assert clamp(-2, -5, -1) == -2
        assert clamp(-10, -5, -1) == -5
        assert clamp(0, -5, -1) == -1

    def test_clamp_floating_point(self):
        """Test clamping with floating point values."""
        assert clamp(2.5, 0.0, 5.0) == 2.5
        assert clamp(-1.5, 0.0, 5.0) == 0.0
        assert clamp(7.8, 0.0, 5.0) == 5.0

    def test_clamp_equal_bounds(self):
        """Test clamping with equal min and max (single value)."""
        assert clamp(5, 3, 3) == 3
        assert clamp(1, 3, 3) == 3
        assert clamp(10, 3, 3) == 3