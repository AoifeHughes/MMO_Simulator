"""
Tests for the world objects management system.
"""

import time
from unittest.mock import Mock

import pytest

from server.world_objects import WorldObject, WorldObjectManager, WorldObjectType


class TestWorldObject:
    def test_world_object_creation(self):
        """Test WorldObject creation with default values"""
        obj = WorldObject(
            object_type=WorldObjectType.FIRE, position=(10.5, 20.3), duration=300.0
        )

        assert obj.object_type == WorldObjectType.FIRE
        assert obj.position == (10.5, 20.3)
        assert obj.duration == 300.0
        assert obj.object_id is not None
        assert len(obj.object_id) == 8  # UUID truncated to 8 chars
        assert obj.created_time > 0

    def test_world_object_is_expired(self):
        """Test WorldObject expiration checking"""
        # Create object with short duration
        obj = WorldObject(
            object_type=WorldObjectType.FIRE,
            position=(0, 0),
            duration=0.1,  # 0.1 seconds
        )

        # Should not be expired immediately
        assert not obj.is_expired()

        # Wait for expiration
        time.sleep(0.15)

        # Should now be expired
        assert obj.is_expired()

    def test_world_object_time_remaining(self):
        """Test WorldObject time remaining calculation"""
        obj = WorldObject(
            object_type=WorldObjectType.CAMPFIRE, position=(0, 0), duration=100.0
        )

        time_remaining = obj.time_remaining()
        assert 95.0 <= time_remaining <= 100.0  # Account for execution time

        # Test expired object
        obj.created_time = time.time() - 200.0  # 200 seconds ago
        assert obj.time_remaining() <= 0


class TestWorldObjectManager:
    def test_create_fire_basic(self):
        """Test creating a basic fire"""
        manager = WorldObjectManager()

        fire_obj = manager.create_fire(x=15.0, y=25.0, duration=300.0)

        assert fire_obj is not None
        assert fire_obj.object_id in manager.objects

        assert fire_obj.object_type == WorldObjectType.FIRE
        assert fire_obj.position == (15.0, 25.0)
        assert fire_obj.duration == 300.0

    def test_create_campfire(self):
        """Test creating a campfire"""
        manager = WorldObjectManager()

        campfire_obj = manager.create_campfire(x=30.0, y=40.0)

        assert campfire_obj is not None
        assert campfire_obj.object_type == WorldObjectType.CAMPFIRE
        assert campfire_obj.duration == 900.0  # Default campfire duration

    def test_get_fires_near_position(self):
        """Test getting fires near a specific position"""
        manager = WorldObjectManager()

        # Create fires at different positions
        fire1 = manager.create_fire(10.0, 10.0, duration=300.0)
        fire2 = manager.create_fire(12.0, 12.0, duration=300.0)
        fire3 = manager.create_campfire(20.0, 20.0)

        # Search near position (11, 11) with radius 5
        nearby_fires = manager.get_fires_near(11.0, 11.0, radius=5.0)

        # Should find fire1 and fire2 (within radius), but not fire3
        nearby_ids = [f.object_id for f in nearby_fires]
        assert fire1.object_id in nearby_ids
        assert fire2.object_id in nearby_ids
        assert fire3.object_id not in nearby_ids

    def test_get_fires_near_position_empty(self):
        """Test getting fires near position when none exist"""
        manager = WorldObjectManager()

        nearby_fires = manager.get_fires_near(50.0, 50.0, radius=10.0)
        assert len(nearby_fires) == 0

    def test_update_removes_expired_objects(self):
        """Test that update() removes expired objects"""
        manager = WorldObjectManager()

        # Create fire with very short duration
        fire_obj = manager.create_fire(x=5.0, y=5.0, duration=0.1)  # 0.1 seconds

        assert len(manager.objects) == 1

        # Wait for expiration and reset last_cleanup to allow immediate cleanup
        time.sleep(0.15)
        manager.last_cleanup = 0  # Force cleanup to run

        # Update should remove expired fire
        expired_count = manager.update()

        assert expired_count == 1
        assert len(manager.objects) == 0
        assert fire_obj.object_id not in manager.objects

    def test_update_keeps_active_objects(self):
        """Test that update() keeps non-expired objects"""
        manager = WorldObjectManager()

        # Create fire with long duration
        fire_obj = manager.create_fire(x=5.0, y=5.0, duration=300.0)  # 5 minutes

        assert len(manager.objects) == 1

        # Update should keep the fire
        expired_count = manager.update()

        assert expired_count == 0
        assert len(manager.objects) == 1
        assert fire_obj.object_id in manager.objects

    def test_fire_creation_properties(self):
        """Test fire objects have correct properties"""
        manager = WorldObjectManager()

        # Test basic fire properties
        fire = manager.create_fire(10.0, 10.0)
        assert fire.properties["can_cook"] == True
        assert fire.properties["heat_radius"] == 3.0
        assert fire.properties["light_radius"] == 5.0

        # Test campfire properties
        campfire = manager.create_campfire(20.0, 20.0)
        assert campfire.properties["can_cook"] == True
        assert campfire.properties["upgraded_fire"] == True
        assert campfire.properties["heat_radius"] == 5.0
        assert campfire.properties["light_radius"] == 8.0

    def test_object_lifecycle(self):
        """Test object creation, retrieval, and removal"""
        manager = WorldObjectManager()

        # Create object
        fire = manager.create_fire(15.0, 15.0)
        fire_id = fire.object_id

        # Retrieve object
        retrieved = manager.get_object(fire_id)
        assert retrieved is not None
        assert retrieved.object_id == fire_id

        # Remove object
        removed = manager.remove_object(fire_id)
        assert removed == True
        assert manager.get_object(fire_id) is None

        # Try to remove non-existent object
        removed_again = manager.remove_object(fire_id)
        assert removed_again == False

    def test_fire_position_distance_calculation(self):
        """Test distance calculation for fire positioning"""
        manager = WorldObjectManager()

        # Create fire
        fire = manager.create_fire(0.0, 0.0)

        # Test exact position match
        nearby_fires = manager.get_fires_near(0.0, 0.0, radius=1.0)
        assert len(nearby_fires) == 1

        # Test position within radius
        nearby_fires = manager.get_fires_near(3.0, 4.0, radius=6.0)  # Distance = 5
        assert len(nearby_fires) == 1

        # Test position outside radius
        nearby_fires = manager.get_fires_near(3.0, 4.0, radius=4.0)  # Distance = 5 > 4
        assert len(nearby_fires) == 0

    def test_multiple_object_types(self):
        """Test handling multiple types of world objects"""
        manager = WorldObjectManager()

        # Create different types
        fire = manager.create_fire(10.0, 10.0)
        campfire = manager.create_campfire(20.0, 20.0)

        assert len(manager.objects) == 2

        # Get all fires near a central position
        all_fires = manager.get_fires_near(15.0, 15.0, radius=10.0)
        assert len(all_fires) == 2

        # Verify types are preserved
        fire_types = {f.object_type for f in all_fires}
        assert WorldObjectType.FIRE in fire_types
        assert WorldObjectType.CAMPFIRE in fire_types

        # Test get objects by type
        fires = manager.get_objects_by_type(WorldObjectType.FIRE)
        campfires = manager.get_objects_by_type(WorldObjectType.CAMPFIRE)
        assert len(fires) == 1
        assert len(campfires) == 1
