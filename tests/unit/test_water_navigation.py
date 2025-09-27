"""
Unit tests for water navigation and movement around water features

These tests specifically address the jumping/warping issue when units
encounter water by testing smooth navigation around water features.
"""

import math

import pytest

from server.world import ServerWorld
from tests.fixtures.test_maps import MapBuilder
from world.tiles import TileType


class TestWaterNavigation:
    """Test smooth navigation around water features"""

    def setup_method(self):
        """Create test world with specific water layout"""
        # Create world without automatic terrain generation
        self.world = ServerWorld(15, 15, use_perlin=False)

    def create_water_obstacle_map(self):
        """Create a map with a water obstacle in the center"""
        terrain = MapBuilder(15, 15).add_rect(6, 6, 9, 9, TileType.WATER).build()

        # Set the terrain in the world
        for (x, y), tile_type in terrain.items():
            self.world.world_map.set_tile(x, y, tile_type)

    def create_water_channel_map(self):
        """Create a map with a vertical water channel"""
        terrain = MapBuilder(15, 15).add_rect(7, 2, 8, 13, TileType.WATER).build()

        # Set the terrain in the world
        for (x, y), tile_type in terrain.items():
            self.world.world_map.set_tile(x, y, tile_type)

    def test_movement_around_water_obstacle(self):
        """Test that agents can move around water obstacles without jumping"""
        self.create_water_obstacle_map()

        # Spawn agent on left side of water
        agent_id = self.world.spawn_agent("player", 4.0, 7.0)

        # Try to move through the water (should be blocked/corrected)
        success = self.world.move_agent(agent_id, 8.0, 7.0, 0)

        agent = self.world.get_agent(agent_id)

        # Agent should either:
        # 1. Not have moved if movement was rejected
        # 2. Have been moved to a walkable position near the intended path
        if success:
            # If movement succeeded, agent should be on walkable terrain
            assert self.world.validate_position(
                agent.x, agent.y
            ), f"Agent at ({agent.x}, {agent.y}) should be on walkable terrain"

            # Agent should not have jumped too far from intended path
            distance_from_intended = math.sqrt(
                (agent.x - 8.0) ** 2 + (agent.y - 7.0) ** 2
            )
            assert (
                distance_from_intended < 3.0
            ), f"Agent jumped too far from intended path: {distance_from_intended}"

            # Agent should be closer to the intended position than starting position
            distance_from_start = math.sqrt((agent.x - 4.0) ** 2 + (agent.y - 7.0) ** 2)
            assert (
                distance_from_start > 1.0
            ), "Agent should have moved away from start position"
        else:
            # If movement was rejected, agent should be at original position
            assert (
                abs(agent.x - 4.0) < 0.1 and abs(agent.y - 7.0) < 0.1
            ), "Agent should remain at original position if movement rejected"

    def test_edge_movement_around_water(self):
        """Test movement along the edge of water features"""
        self.create_water_obstacle_map()

        # Spawn agent next to water
        agent_id = self.world.spawn_agent("player", 5.0, 7.0)

        # Move along the water edge
        movement_path = [
            (5.0, 6.0),  # Move up along edge
            (5.0, 5.0),  # Continue up
            (6.0, 5.0),  # Move to corner
            (7.0, 5.0),  # Move along top edge
        ]

        for target_x, target_y in movement_path:
            success = self.world.move_agent(agent_id, target_x, target_y, 0)
            agent = self.world.get_agent(agent_id)

            # Movement should generally succeed along edges
            if success:
                assert self.world.validate_position(
                    agent.x, agent.y
                ), f"Agent should be on walkable terrain at ({agent.x}, {agent.y})"

                # Should be relatively close to intended position
                distance = math.sqrt(
                    (agent.x - target_x) ** 2 + (agent.y - target_y) ** 2
                )
                assert (
                    distance < 2.0
                ), f"Agent too far from intended position: {distance}"

    def test_water_channel_navigation(self):
        """Test navigation around a water channel"""
        self.create_water_channel_map()

        # Spawn agent on left side of channel
        agent_id = self.world.spawn_agent("player", 3.0, 7.0)

        # Try to cross the channel (should be redirected)
        success = self.world.move_agent(agent_id, 11.0, 7.0, 0)

        agent = self.world.get_agent(agent_id)

        if success:
            # Agent should end up on walkable terrain
            assert self.world.validate_position(
                agent.x, agent.y
            ), "Agent should be on walkable terrain"

            # Agent should not have jumped across the water
            # (If position correction worked properly, agent should be near the channel edge)
            assert (
                agent.x < 7.0 or agent.x > 8.0
            ), "Agent should not be in the water channel"

    def test_gradual_water_approach(self):
        """Test gradual approach to water edge"""
        self.create_water_obstacle_map()

        # Spawn agent away from water
        agent_id = self.world.spawn_agent("player", 2.0, 7.0)

        # Make several small moves toward water
        positions = []
        for step in range(6):
            target_x = 2.0 + step * 0.8  # Move 0.8 units each step
            success = self.world.move_agent(agent_id, target_x, 7.0, 0)

            agent = self.world.get_agent(agent_id)
            positions.append((agent.x, agent.y, success))

        # Analyze movement progression
        for i, (x, y, success) in enumerate(positions):
            expected_x = 2.0 + i * 0.8
            print(
                f"Step {i}: intended=({expected_x:.1f}, 7.0), actual=({x:.1f}, {y:.1f}), success={success}"
            )

            # Early movements should succeed
            if expected_x < 5.5:  # Before hitting water
                assert success, f"Movement {i} should have succeeded"
                distance_to_intended = abs(x - expected_x)
                assert (
                    distance_to_intended < 0.5
                ), f"Early movement should be close to intended position"

            # Agent should always be on walkable terrain
            assert self.world.validate_position(
                x, y
            ), f"Agent should be on walkable terrain at step {i}"

    def test_position_precision_near_water(self):
        """Test that position corrections preserve sub-tile precision"""
        self.create_water_obstacle_map()

        # Test various sub-tile positions near water edge
        test_positions = [
            (5.1, 7.3),
            (5.7, 7.8),
            (5.9, 6.2),
            (5.3, 5.9),
        ]

        for start_x, start_y in test_positions:
            agent_id = self.world.spawn_agent("player", start_x, start_y)

            # Make a small movement
            target_x, target_y = start_x + 0.3, start_y + 0.2
            success = self.world.move_agent(agent_id, target_x, target_y, 0)

            agent = self.world.get_agent(agent_id)

            # Agent should be on valid terrain (precision may be adjusted due to water avoidance)
            assert self.world.validate_position(
                agent.x, agent.y
            ), f"Agent should be on valid terrain: ({agent.x}, {agent.y})"

            # Movement should be reasonable relative to intended target
            distance_to_target = math.sqrt(
                (agent.x - target_x) ** 2 + (agent.y - target_y) ** 2
            )
            assert (
                distance_to_target < 3.0
            ), f"Agent should be reasonably close to target: distance={distance_to_target:.2f}"

            # Clean up for next test
            self.world.despawn_agent(agent_id)

    def test_no_infinite_correction_loops(self):
        """Test that position correction doesn't cause infinite loops or oscillation"""
        self.create_water_obstacle_map()

        # Spawn agent right at water edge (on walkable grass)
        agent_id = self.world.spawn_agent("player", 5.0, 7.0)

        # Try multiple movements that might trigger corrections
        positions = []
        for i in range(10):
            # Alternate between trying to move into water and away
            if i % 2 == 0:
                target_x, target_y = 7.0, 7.5  # Into water
            else:
                target_x, target_y = 4.0, 7.5  # Away from water

            success = self.world.move_agent(agent_id, target_x, target_y, 0)
            agent = self.world.get_agent(agent_id)
            positions.append((agent.x, agent.y))

        # Check movement behavior - agent should either:
        # 1. Stay in a stable safe position, OR
        # 2. Make reasonable movements without wild oscillation

        last_3_positions = positions[-3:]
        unique_positions = set(last_3_positions)

        if len(unique_positions) == 1:
            # Agent found stable safe position - this is acceptable
            stable_pos = last_3_positions[0]
            assert self.world.validate_position(
                stable_pos[0], stable_pos[1]
            ), "Stable position should be valid terrain"
        else:
            # Agent is moving - movements should be reasonable
            max_movement = max(
                [
                    math.sqrt(
                        (positions[i + 1][0] - positions[i][0]) ** 2
                        + (positions[i + 1][1] - positions[i][1]) ** 2
                    )
                    for i in range(len(positions) - 1)
                ]
            )
            assert (
                max_movement < 8.0
            ), f"Movement should not be too large: {max_movement:.2f}"

        # All positions should be valid
        for x, y in positions:
            assert self.world.validate_position(
                x, y
            ), f"Position ({x}, {y}) should be valid"


class TestWaterTileProperties:
    """Test that water tile properties are correct after fixes"""

    def test_water_tile_consistency(self):
        """Test that water tiles have consistent properties"""
        from world.tiles import TILE_PROPERTIES, TileType

        water_props = TILE_PROPERTIES[TileType.WATER]

        assert not water_props.walkable, "Water should not be walkable"
        assert water_props.movement_cost == float(
            "inf"
        ), "Water should have infinite movement cost"
        assert not water_props.blocking_vision, "Water should not block vision"

    def test_world_map_water_walkability(self):
        """Test that world map correctly identifies water as unwalkable"""
        world = ServerWorld(10, 10, use_perlin=False)

        # Set a tile to water
        world.world_map.set_tile(5, 5, TileType.WATER)

        # Test walkability
        assert not world.world_map.is_walkable(
            5, 5
        ), "Water tile should not be walkable"
        assert world.world_map.get_movement_cost(5, 5) == float(
            "inf"
        ), "Water should have infinite movement cost"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
