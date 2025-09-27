"""
Unit tests for the Context Manager system.

Tests environmental awareness, danger assessment, and contextual decision-making support.
"""

import math
import time
from unittest.mock import Mock

import pytest

from client.context_manager import (
    ContextManager,
    ContextSnapshot,
    ContextType,
    ContextualArea,
    DangerLevel,
    EnvironmentAnalyzer,
)


class TestEnvironmentAnalyzer:
    """Test the EnvironmentAnalyzer class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.analyzer = EnvironmentAnalyzer()

    def test_analyzer_creation(self):
        """Test basic analyzer creation"""
        assert self.analyzer.danger_detection_range > 0
        assert self.analyzer.resource_detection_range > 0
        assert self.analyzer.social_detection_range > 0

    def test_safe_environment_analysis(self):
        """Test analysis of safe environment with no threats"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0},
            {"id": "fish_1", "type": "fish", "x": 8.0, "y": 9.0},
        ]

        snapshot = self.analyzer.analyze_position(10.0, 10.0, visible_entities)

        assert snapshot.local_danger == DangerLevel.SAFE
        assert snapshot.nearby_enemies == 0
        assert snapshot.nearby_resources == 2
        assert snapshot.resource_availability > 0

    def test_dangerous_environment_analysis(self):
        """Test analysis of dangerous environment with enemies"""
        visible_entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 12.0, "y": 11.0},
            {"id": "enemy_2", "agent_type": "enemy", "x": 8.0, "y": 9.0},
            {"id": "enemy_3", "agent_type": "enemy", "x": 11.0, "y": 12.0},
        ]

        snapshot = self.analyzer.analyze_position(10.0, 10.0, visible_entities)

        assert snapshot.local_danger in [DangerLevel.HIGH, DangerLevel.CRITICAL]
        assert snapshot.nearby_enemies == 3
        assert len(snapshot.safe_directions) < 8  # Should have fewer safe directions

    def test_social_environment_analysis(self):
        """Test analysis of social environment with allies"""
        visible_entities = [
            {"id": "player_1", "agent_type": "player", "x": 12.0, "y": 11.0},
            {"id": "npc_1", "agent_type": "npc", "x": 8.0, "y": 9.0},
        ]

        snapshot = self.analyzer.analyze_position(10.0, 10.0, visible_entities)

        assert snapshot.nearby_allies == 2
        assert snapshot.social_density > 0
        assert len(snapshot.social_directions) == 2

    def test_danger_level_assessment(self):
        """Test danger level assessment with different enemy configurations"""
        # No enemies - should be safe
        snapshot = self.analyzer.analyze_position(10.0, 10.0, [])
        assert snapshot.local_danger == DangerLevel.SAFE

        # One distant enemy - should be low danger
        entities = [{"id": "enemy_1", "agent_type": "enemy", "x": 20.0, "y": 20.0}]
        snapshot = self.analyzer.analyze_position(10.0, 10.0, entities)
        assert snapshot.local_danger in [DangerLevel.SAFE, DangerLevel.LOW]

        # Multiple close enemies - should be high danger
        entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 11.0, "y": 11.0},
            {"id": "enemy_2", "agent_type": "enemy", "x": 9.0, "y": 9.0},
            {"id": "enemy_3", "agent_type": "enemy", "x": 12.0, "y": 8.0},
        ]
        snapshot = self.analyzer.analyze_position(10.0, 10.0, entities)
        assert snapshot.local_danger in [DangerLevel.HIGH, DangerLevel.CRITICAL]

    def test_safe_directions_calculation(self):
        """Test calculation of safe movement directions"""
        # Enemy to the north - south should be safer
        entities = [{"id": "enemy_1", "agent_type": "enemy", "x": 10.0, "y": 5.0}]
        snapshot = self.analyzer.analyze_position(10.0, 10.0, entities)

        # Should have directions that avoid the enemy
        assert len(snapshot.safe_directions) > 0

        # Check that directions generally point away from enemy
        # (Exact implementation details may vary)
        safe_dirs = set(snapshot.safe_directions)
        # North directions (315, 0, 45) should be less common
        dangerous_dirs = {315, 0, 45}
        safe_count = len(safe_dirs - dangerous_dirs)
        assert safe_count > 0

    def test_resource_directions_calculation(self):
        """Test calculation of resource directions"""
        entities = [
            {"id": "wood_1", "type": "wood", "x": 15.0, "y": 10.0},  # East
            {"id": "fish_1", "type": "fish", "x": 5.0, "y": 10.0},  # West
        ]

        snapshot = self.analyzer.analyze_position(10.0, 10.0, entities)

        assert len(snapshot.resource_directions) == 2
        # Should have directions pointing to resources (east and west)
        angles = set(snapshot.resource_directions)
        # Should include directions close to 0° (east) and 180° (west)
        has_east = any(abs(angle - 0) < 30 or abs(angle - 360) < 30 for angle in angles)
        has_west = any(abs(angle - 180) < 30 for angle in angles)
        assert has_east or has_west  # At least one should be detected


class TestContextualArea:
    """Test the ContextualArea class"""

    def test_contextual_area_creation(self):
        """Test basic contextual area creation"""
        area = ContextualArea(
            area_id="test_area",
            center=(10.0, 10.0),
            radius=5.0,
            context_type=ContextType.DANGER,
        )

        assert area.area_id == "test_area"
        assert area.center == (10.0, 10.0)
        assert area.radius == 5.0
        assert area.context_type == ContextType.DANGER

    def test_position_inside_check(self):
        """Test position inside area checking"""
        area = ContextualArea(
            area_id="test_area",
            center=(10.0, 10.0),
            radius=5.0,
            context_type=ContextType.RESOURCE,
        )

        # Position inside
        assert area.is_position_inside(12.0, 11.0)
        assert area.is_position_inside(10.0, 10.0)  # Center

        # Position outside
        assert not area.is_position_inside(20.0, 20.0)
        assert not area.is_position_inside(10.0, 16.0)  # Just outside radius

    def test_distance_calculation(self):
        """Test distance calculation to area center"""
        area = ContextualArea(
            area_id="test_area",
            center=(0.0, 0.0),
            radius=5.0,
            context_type=ContextType.SOCIAL,
        )

        # Test known distances
        assert abs(area.get_distance_to(3.0, 4.0) - 5.0) < 0.001  # 3-4-5 triangle
        assert abs(area.get_distance_to(0.0, 0.0) - 0.0) < 0.001  # Center

    def test_area_expiration(self):
        """Test area expiration logic"""
        area = ContextualArea(
            area_id="test_area",
            center=(10.0, 10.0),
            radius=5.0,
            context_type=ContextType.DANGER,
        )

        # Should not be expired immediately
        assert not area.is_expired(max_age=300.0)

        # Wait a tiny bit then check expiration with very short max age
        time.sleep(0.01)
        assert area.is_expired(max_age=0.001)

    def test_update_from_entities(self):
        """Test updating area properties from entity data"""
        area = ContextualArea(
            area_id="test_area",
            center=(10.0, 10.0),
            radius=5.0,
            context_type=ContextType.DANGER,
        )

        # Entities with various types
        entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 11.0, "y": 11.0},
            {"id": "enemy_2", "agent_type": "enemy", "x": 9.0, "y": 9.0},
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 10.0},
            {"id": "player_1", "agent_type": "player", "x": 8.0, "y": 12.0},
        ]

        initial_time = area.last_updated
        area.update_from_entities(entities)

        # Should update danger level based on enemies
        assert area.danger_level in [DangerLevel.MODERATE, DangerLevel.HIGH]
        assert area.resource_density > 0
        assert area.social_activity > 0
        assert area.last_updated > initial_time


class TestContextSnapshot:
    """Test the ContextSnapshot class"""

    def test_snapshot_creation(self):
        """Test basic snapshot creation"""
        snapshot = ContextSnapshot(timestamp=time.time(), position=(10.0, 10.0))

        assert snapshot.position == (10.0, 10.0)
        assert snapshot.local_danger == DangerLevel.SAFE
        assert snapshot.resource_availability == 0.0


class TestContextManager:
    """Test the ContextManager class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.context_manager = ContextManager("test_agent")

    def test_context_manager_creation(self):
        """Test basic context manager creation"""
        assert self.context_manager.agent_id == "test_agent"
        assert self.context_manager.analyzer is not None
        assert len(self.context_manager.contextual_areas) == 0

    def test_context_update_basic(self):
        """Test basic context update functionality"""
        visible_entities = [
            {"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0},
            {"id": "enemy_1", "agent_type": "enemy", "x": 15.0, "y": 15.0},
        ]

        snapshot = self.context_manager.update_context(10.0, 10.0, visible_entities)

        assert snapshot is not None
        assert snapshot.position == (10.0, 10.0)
        assert snapshot.nearby_resources > 0

    def test_context_history_tracking(self):
        """Test that context history is properly tracked"""
        visible_entities = [{"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0}]

        # Update multiple times
        for _ in range(3):
            self.context_manager.update_context(10.0, 10.0, visible_entities)
            time.sleep(0.01)  # Ensure different timestamps

        # Should have history entries
        assert len(self.context_manager.context_history) >= 1

    def test_danger_assessment(self):
        """Test danger assessment for specific locations"""
        # Add some contextual areas with danger
        danger_area = ContextualArea(
            area_id="danger_zone",
            center=(15.0, 15.0),
            radius=5.0,
            context_type=ContextType.DANGER,
            danger_level=DangerLevel.HIGH,
        )
        self.context_manager.contextual_areas["danger_zone"] = danger_area

        # Test positions
        safe_pos_danger = self.context_manager.get_danger_assessment(5.0, 5.0)
        dangerous_pos_danger = self.context_manager.get_danger_assessment(15.0, 15.0)

        assert safe_pos_danger == DangerLevel.SAFE
        assert dangerous_pos_danger == DangerLevel.HIGH

    def test_resource_density_calculation(self):
        """Test resource density calculation"""
        # Add resource area
        resource_area = ContextualArea(
            area_id="resource_zone",
            center=(10.0, 10.0),
            radius=5.0,
            context_type=ContextType.RESOURCE,
            resource_density=0.8,
        )
        self.context_manager.contextual_areas["resource_zone"] = resource_area

        density = self.context_manager.get_resource_density(10.0, 10.0, radius=10.0)
        assert density > 0

    def test_social_activity_calculation(self):
        """Test social activity calculation"""
        # Add social area
        social_area = ContextualArea(
            area_id="social_zone",
            center=(10.0, 10.0),
            radius=8.0,
            context_type=ContextType.SOCIAL,
            social_activity=0.6,
        )
        self.context_manager.contextual_areas["social_zone"] = social_area

        activity = self.context_manager.get_social_activity(10.0, 10.0, radius=15.0)
        assert activity > 0

    def test_safe_position_finding(self):
        """Test finding safe positions"""
        # Create a context with safe directions
        self.context_manager.last_snapshot = ContextSnapshot(
            timestamp=time.time(),
            position=(10.0, 10.0),
            safe_directions=[90, 180, 270],  # East, South, West
        )

        safe_pos = self.context_manager.find_safe_position(
            10.0, 10.0, search_radius=15.0
        )

        # Should find some safe position
        if safe_pos:
            assert isinstance(safe_pos, tuple)
            assert len(safe_pos) == 2

    def test_context_factors_for_behavior(self):
        """Test getting context factors for specific behaviors"""
        # Set up a context snapshot
        self.context_manager.last_snapshot = ContextSnapshot(
            timestamp=time.time(),
            position=(10.0, 10.0),
            local_danger=DangerLevel.MODERATE,
            resource_availability=0.7,
            social_density=0.3,
            nearby_enemies=2,
            nearby_resources=3,
            nearby_allies=1,
        )

        # Test combat behavior factors
        combat_factors = self.context_manager.get_context_factors_for_behavior(
            "combat_action"
        )
        assert "danger_level" in combat_factors
        assert "enemy_count" in combat_factors

        # Test resource behavior factors
        resource_factors = self.context_manager.get_context_factors_for_behavior(
            "resource_gathering"
        )
        assert "resource_availability" in resource_factors
        assert "danger_modifier" in resource_factors

        # Test social behavior factors
        social_factors = self.context_manager.get_context_factors_for_behavior(
            "social_interaction"
        )
        assert "social_density" in social_factors
        assert "ally_count" in social_factors

    def test_movement_recommendation(self):
        """Test movement recommendations"""
        # Set up context with some danger
        danger_area = ContextualArea(
            area_id="danger_zone",
            center=(20.0, 20.0),
            radius=5.0,
            context_type=ContextType.DANGER,
            danger_level=DangerLevel.HIGH,
        )
        self.context_manager.contextual_areas["danger_zone"] = danger_area

        self.context_manager.last_snapshot = ContextSnapshot(
            timestamp=time.time(), position=(10.0, 10.0), safe_directions=[90, 180, 270]
        )

        # Test movement to safe area
        safe_recommendation = self.context_manager.get_movement_recommendation(5.0, 5.0)
        assert safe_recommendation["recommended"] is True

        # Test movement to dangerous area
        dangerous_recommendation = self.context_manager.get_movement_recommendation(
            20.0, 20.0
        )
        assert dangerous_recommendation["recommended"] is False
        assert dangerous_recommendation["danger_level"] == "high"

    def test_contextual_area_updates(self):
        """Test that contextual areas are updated from entity observations"""
        visible_entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 12.0, "y": 11.0},
            {"id": "wood_1", "type": "wood", "x": 8.0, "y": 9.0},
            {"id": "player_1", "agent_type": "player", "x": 15.0, "y": 15.0},
        ]

        # Update context
        self.context_manager.update_context(10.0, 10.0, visible_entities)

        # Should have created contextual areas
        assert len(self.context_manager.contextual_areas) > 0

        # Should have different types of areas
        area_types = {
            area.context_type for area in self.context_manager.contextual_areas.values()
        }
        assert ContextType.DANGER in area_types

    def test_area_cleanup(self):
        """Test cleanup of old contextual areas"""
        # Add an old area
        old_area = ContextualArea(
            area_id="old_area",
            center=(10.0, 10.0),
            radius=5.0,
            context_type=ContextType.DANGER,
        )
        old_area.last_updated = time.time() - 400.0  # Very old
        self.context_manager.contextual_areas["old_area"] = old_area

        # Add a recent area
        recent_area = ContextualArea(
            area_id="recent_area",
            center=(15.0, 15.0),
            radius=5.0,
            context_type=ContextType.RESOURCE,
        )
        self.context_manager.contextual_areas["recent_area"] = recent_area

        # Force cleanup
        self.context_manager._cleanup_old_areas()

        # Old area should be removed, recent area should remain
        assert "old_area" not in self.context_manager.contextual_areas
        assert "recent_area" in self.context_manager.contextual_areas

    def test_analysis_throttling(self):
        """Test that analysis is throttled for performance"""
        visible_entities = [{"id": "wood_1", "type": "wood", "x": 12.0, "y": 11.0}]

        # Set very long analysis interval
        self.context_manager.analysis_interval = 10.0

        # First update should work
        snapshot1 = self.context_manager.update_context(10.0, 10.0, visible_entities)
        assert snapshot1 is not None

        # Immediate second update should return cached result
        snapshot2 = self.context_manager.update_context(10.0, 10.0, visible_entities)
        assert snapshot2 is not None

        # Should be same or similar timestamp (cached)
        time_diff = abs(snapshot2.timestamp - snapshot1.timestamp)
        assert time_diff < 0.1

    def test_debug_info(self):
        """Test debug information generation"""
        # Add some areas and context
        visible_entities = [
            {"id": "enemy_1", "agent_type": "enemy", "x": 12.0, "y": 11.0}
        ]

        self.context_manager.update_context(10.0, 10.0, visible_entities)

        debug_info = self.context_manager.get_debug_info()

        assert "agent_id" in debug_info
        assert "active_areas" in debug_info
        assert "history_size" in debug_info
        assert "last_snapshot" in debug_info
        assert "contextual_areas" in debug_info

        assert debug_info["agent_id"] == "test_agent"


if __name__ == "__main__":
    pytest.main([__file__])
