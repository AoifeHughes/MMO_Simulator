"""
Unit tests for world physics and collision detection

Fast, focused tests for movement, collision, and terrain systems.
"""

import pytest
import math
from unittest.mock import MagicMock

from server.world import ServerWorld
from shared.collision import CollisionDetector
from shared.messages import AgentData
from tests.fixtures.test_maps import TestMaps, MapBuilder
from world.tiles import TileType


class TestCollisionDetector:
    """Test collision detection system"""

    def setup_method(self):
        """Set up collision detector"""
        self.detector = CollisionDetector(20, 20)

    def test_basic_bounds_checking(self):
        """Should enforce world boundaries"""
        # Inside bounds (accounting for agent radius)
        assert self.detector.is_position_valid(10, 10)
        assert self.detector.is_position_valid(1, 1)  # Safe distance from edge
        assert self.detector.is_position_valid(18, 18)  # Safe distance from other edge

        # Outside bounds
        assert not self.detector.is_position_valid(-1, 10)
        assert not self.detector.is_position_valid(10, -1)
        assert not self.detector.is_position_valid(20, 10)
        assert not self.detector.is_position_valid(10, 20)

    def test_clamp_to_bounds(self):
        """Should clamp positions to valid boundaries"""
        # Already valid positions should be unchanged
        x, y = self.detector.clamp_to_bounds(10, 10)
        assert x == 10 and y == 10

        # Out of bounds positions should be clamped (accounting for agent radius)
        x, y = self.detector.clamp_to_bounds(-5, 10)
        assert x >= self.detector.agent_radius and y == 10

        x, y = self.detector.clamp_to_bounds(25, 15)
        assert x <= (20 - self.detector.agent_radius) and y == 15

    def test_agent_collision_detection(self):
        """Should detect collisions between agents"""
        current_pos = (10, 10)
        intended_pos = (12, 10)
        other_agents = [(11, 10)]  # Agent in the path

        # Should adjust position to avoid collision
        safe_x, safe_y = self.detector.resolve_movement_collision(
            current_pos, intended_pos, other_agents
        )

        # Should be moved away from the collision
        distance_to_other = ((safe_x - 11) ** 2 + (safe_y - 10) ** 2) ** 0.5
        assert distance_to_other >= 1.0, "Should maintain minimum distance from other agent"

    def test_safe_spawn_position(self):
        """Should find safe spawn positions"""
        existing_positions = [(10, 10), (11, 11), (9, 9)]
        world_map = MagicMock()
        world_map.is_walkable.return_value = True
        world_map.width = 20
        world_map.height = 20

        x, y = self.detector.get_safe_spawn_position(existing_positions, world_map)

        # Should be within bounds
        assert 0 <= x < 20 and 0 <= y < 20

        # Should be away from existing agents
        min_distance = min([
            ((x - ex) ** 2 + (y - ey) ** 2) ** 0.5
            for ex, ey in existing_positions
        ])
        assert min_distance >= 1.0, "Spawn should be away from existing agents"

    def test_no_collision_when_clear_path(self):
        """Should not modify position when path is clear"""
        current_pos = (5, 5)
        intended_pos = (7, 7)
        other_agents = [(15, 15)]  # Far away

        safe_x, safe_y = self.detector.resolve_movement_collision(
            current_pos, intended_pos, other_agents
        )

        assert abs(safe_x - intended_pos[0]) < 0.1
        assert abs(safe_y - intended_pos[1]) < 0.1


class TestServerWorldPhysics:
    """Test server world physics and movement"""

    def setup_method(self):
        """Create test world"""
        self.world = ServerWorld(20, 20)

    def test_agent_spawning(self):
        """Should spawn agents in valid positions"""
        agent_id = self.world.spawn_agent("player")

        agent = self.world.get_agent(agent_id)
        assert agent is not None
        assert agent.agent_type == "player"
        assert 0 <= agent.x < 20
        assert 0 <= agent.y < 20
        assert agent.is_alive

    def test_agent_spawning_with_coordinates(self):
        """Should spawn agents at specified coordinates"""
        agent_id = self.world.spawn_agent("player", x=15.0, y=10.0)

        agent = self.world.get_agent(agent_id)
        assert agent is not None
        assert agent.x == 15.0
        assert agent.y == 10.0

    def test_agent_movement_validation(self):
        """Should validate agent movement"""
        agent_id = self.world.spawn_agent("player", 10, 10)

        # Valid movement
        success = self.world.move_agent(agent_id, 12, 12, 0)
        assert success

        agent = self.world.get_agent(agent_id)
        assert agent.x == 12
        assert agent.y == 12

    def test_dead_agent_cannot_move(self):
        """Dead agents should not be able to move"""
        agent_id = self.world.spawn_agent("player", 10, 10)
        agent = self.world.get_agent(agent_id)
        agent.is_alive = False

        success = self.world.move_agent(agent_id, 15, 15, 0)
        assert not success

        # Position should not change
        assert agent.x == 10
        assert agent.y == 10

    def test_movement_bounds_enforcement(self):
        """Should enforce world boundaries for movement"""
        agent_id = self.world.spawn_agent("player", 19, 19)

        # Try to move out of bounds
        success = self.world.move_agent(agent_id, 25, 25, 0)

        agent = self.world.get_agent(agent_id)
        # Should be clamped to valid position
        assert agent.x < 20
        assert agent.y < 20

    def test_visibility_calculation(self):
        """Should calculate agent visibility correctly"""
        # Spawn two agents close to each other
        agent1_id = self.world.spawn_agent("player", 10, 10)
        agent2_id = self.world.spawn_agent("enemy", 12, 10)

        visible = self.world.get_visible_agents(agent1_id, vision_range=5.0)

        # Should see the other agent
        visible_ids = [a.id for a in visible]
        assert agent2_id in visible_ids

    def test_visibility_range_limits(self):
        """Should respect vision range limits"""
        # Spawn agents far apart
        agent1_id = self.world.spawn_agent("player", 5, 5)
        agent2_id = self.world.spawn_agent("enemy", 15, 15)

        visible = self.world.get_visible_agents(agent1_id, vision_range=5.0)

        # Should not see distant agent
        visible_ids = [a.id for a in visible]
        assert agent2_id not in visible_ids

    def test_dead_agents_not_visible(self):
        """Dead agents should not be visible"""
        agent1_id = self.world.spawn_agent("player", 10, 10)
        agent2_id = self.world.spawn_agent("enemy", 11, 10)

        # Kill second agent
        agent2 = self.world.get_agent(agent2_id)
        agent2.is_alive = False

        visible = self.world.get_visible_agents(agent1_id, vision_range=10.0)

        # Should not see dead agent
        visible_ids = [a.id for a in visible]
        assert agent2_id not in visible_ids

    def test_terrain_walkability_validation(self):
        """Should validate walkability based on terrain"""
        # Create a world with some walls
        terrain_map = MapBuilder(20, 20)\
            .add_rect(5, 5, 10, 10, TileType.WALL)\
            .build()

        # Override world terrain for testing
        for (x, y), tile_type in terrain_map.items():
            self.world.world_map.set_tile(x, y, tile_type)

        # Test walkable position
        assert self.world.validate_position(2, 2)  # Grass area

        # Test non-walkable position
        assert not self.world.validate_position(7, 7)  # Wall area

    def test_pathfinding_validation(self):
        """Should validate movement paths don't cross walls"""
        # Create terrain with wall barrier
        terrain_map = MapBuilder(20, 20)\
            .add_line(0, 10, 19, 10, TileType.WALL)\
            .build()

        # Override world terrain
        for (x, y), tile_type in terrain_map.items():
            self.world.world_map.set_tile(x, y, tile_type)

        # Test path that crosses wall
        valid_path = self.world.validate_movement_path((5, 5), (15, 5))  # Same side

        # Create a path that crosses multiple wall tiles (should be invalid)
        # Add a thick wall barrier to make the path definitely invalid
        thick_wall_map = MapBuilder(20, 20)\
            .add_rect(0, 9, 20, 12, TileType.WALL)\
            .build()

        for (x, y), tile_type in thick_wall_map.items():
            self.world.world_map.set_tile(x, y, tile_type)

        invalid_path = self.world.validate_movement_path((5, 5), (5, 15))  # Cross thick wall

        assert valid_path, "Path on same side should be valid"
        assert not invalid_path, "Path crossing thick wall should be invalid"

    def test_movement_cost_calculation(self):
        """Should calculate movement costs based on terrain"""
        # Create varied terrain
        terrain_map = MapBuilder(20, 20)\
            .add_rect(0, 0, 5, 20, TileType.GRASS)\
            .add_rect(5, 0, 10, 20, TileType.SAND)\
            .add_rect(10, 0, 15, 20, TileType.WALL)\
            .add_rect(15, 0, 20, 20, TileType.WATER)\
            .build()

        # Override terrain
        for (x, y), tile_type in terrain_map.items():
            self.world.world_map.set_tile(x, y, tile_type)

        # Test different movement costs
        grass_cost = self.world.get_movement_cost_penalty(2, 10)
        sand_cost = self.world.get_movement_cost_penalty(7, 10)
        wall_cost = self.world.get_movement_cost_penalty(12, 10)

        assert grass_cost == 1.0, "Grass should have normal movement cost"
        assert sand_cost < 1.0, "Sand should slow movement"
        assert wall_cost == 0.0, "Walls should block movement"

    def test_find_nearest_walkable_position(self):
        """Should find nearest walkable position when needed"""
        # Create terrain with island of walkable area
        terrain_map = {}
        for y in range(20):
            for x in range(20):
                if 8 <= x <= 12 and 8 <= y <= 12:
                    terrain_map[(x, y)] = TileType.GRASS
                else:
                    terrain_map[(x, y)] = TileType.WALL

        # Override terrain
        for (x, y), tile_type in terrain_map.items():
            self.world.world_map.set_tile(x, y, tile_type)

        # Request position in wall - should find nearby grass
        safe_x, safe_y = self.world.find_nearest_walkable_position(5, 5)

        # Should be in the walkable area
        assert 8 <= safe_x <= 12
        assert 8 <= safe_y <= 12


class TestTerrainInteraction:
    """Test agent interaction with different terrain types"""

    def test_water_interaction(self):
        """Test behavior around water tiles"""
        terrain = TestMaps.get_fishing_pond()
        world = ServerWorld(25, 25)

        # Override terrain
        for (x, y), tile_type in terrain.items():
            world.world_map.set_tile(x, y, tile_type)

        # Spawn agent near water
        agent_id = world.spawn_agent("player", 20, 12)

        # Should be able to move to water edge
        success = world.move_agent(agent_id, 19, 12, 0)
        assert success

        agent = world.get_agent(agent_id)
        # Position might be adjusted to safe/walkable position
        assert abs(agent.x - 19) < 2.0, f"Agent moved to {agent.x}, expected near 19"
        assert abs(agent.y - 12) < 2.0, f"Agent moved to {agent.y}, expected near 12"

    def test_varied_terrain_traversal(self):
        """Test movement across varied terrain types"""
        terrain = TestMaps.get_exploration_terrain()
        world = ServerWorld(30, 30)

        # Override terrain
        for (x, y), tile_type in terrain.items():
            world.world_map.set_tile(x, y, tile_type)

        agent_id = world.spawn_agent("explorer", 5, 15)

        # Test movement across different terrain
        positions = [(10, 15), (15, 15), (25, 15)]

        for target_x, target_y in positions:
            if world.world_map.is_walkable(int(target_x), int(target_y)):
                success = world.move_agent(agent_id, target_x, target_y, 0)
                assert success, f"Should be able to move to walkable position ({target_x}, {target_y})"
            else:
                # If not walkable, should find nearby position
                success = world.move_agent(agent_id, target_x, target_y, 0)
                agent = world.get_agent(agent_id)
                # Should be moved to a safe position near the target
                distance = ((agent.x - target_x) ** 2 + (agent.y - target_y) ** 2) ** 0.5
                assert distance < 5.0, "Should move to nearby safe position"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])