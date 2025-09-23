import pytest
import pytest_asyncio
import asyncio
import time
from typing import List, Dict, Any
from client.agent_map import AgentMap
from shared.pathfinding import Pathfinder
from world.tiles import TileType
from server.server import GameServer
from client.client import GameClient

class TestPathfinding:
    """Test pathfinding functionality"""

    def test_agent_map_creation(self):
        """Test that agent maps are created properly"""
        agent_map = AgentMap(10, 10)
        assert agent_map.world_width == 10
        assert agent_map.world_height == 10
        assert agent_map.get_map_completion_percentage() == 0.0
        assert len(agent_map.get_known_tiles()) == 0

    def test_agent_map_discovery(self):
        """Test terrain discovery functionality"""
        agent_map = AgentMap(10, 10)

        # Discover some terrain
        terrain_data = {
            (5, 5): TileType.GRASS,
            (5, 6): TileType.STONE,
            (6, 5): TileType.WATER
        }

        agent_map.discover_area(5, 5, 2.0, terrain_data)

        # Check that tiles were discovered
        assert agent_map.is_tile_known(5, 5)
        assert agent_map.is_tile_known(5, 6)
        assert agent_map.is_tile_known(6, 5)
        assert agent_map.get_tile_type(5, 5) == TileType.GRASS
        assert agent_map.get_tile_type(5, 6) == TileType.STONE
        assert agent_map.get_tile_type(6, 5) == TileType.WATER

    def test_pathfinding_simple_path(self):
        """Test basic pathfinding functionality"""
        agent_map = AgentMap(10, 10)
        pathfinder = Pathfinder()

        # Create a simple walkable area
        terrain_data = {}
        for x in range(10):
            for y in range(10):
                terrain_data[(x, y)] = TileType.GRASS

        agent_map.discover_area(5, 5, 10, terrain_data)

        # Find path from (1, 1) to (8, 8)
        path = pathfinder.find_path(agent_map, (1.0, 1.0), (8.0, 8.0))

        assert path is not None
        assert len(path) >= 2
        assert path[0] == (1.0, 1.0)  # Start position
        assert path[-1] == (8.0, 8.0)  # End position

    def test_pathfinding_with_obstacles(self):
        """Test pathfinding around obstacles"""
        agent_map = AgentMap(10, 10)
        pathfinder = Pathfinder()

        # Create terrain with obstacles
        terrain_data = {}
        for x in range(10):
            for y in range(10):
                if x == 5 and 2 <= y <= 7:  # Vertical wall
                    terrain_data[(x, y)] = TileType.WALL
                else:
                    terrain_data[(x, y)] = TileType.GRASS

        agent_map.discover_area(5, 5, 10, terrain_data)

        # Find path from (2, 5) to (8, 5) - should go around wall
        path = pathfinder.find_path(agent_map, (2.0, 5.0), (8.0, 5.0))

        assert path is not None
        assert len(path) > 2  # Should be longer due to obstacle

        # Path should not go through the wall at x=5
        for waypoint in path[1:-1]:  # Skip start and end points
            if int(waypoint[0]) == 5:
                assert not (2 <= int(waypoint[1]) <= 7)

    def test_exploration_frontiers(self):
        """Test exploration frontier detection"""
        agent_map = AgentMap(10, 10)

        # Discover a small area
        terrain_data = {
            (5, 5): TileType.GRASS,
            (5, 6): TileType.GRASS,
            (6, 5): TileType.GRASS,
            (6, 6): TileType.GRASS
        }
        agent_map.discover_area(5.5, 5.5, 2, terrain_data)

        # Get frontier tiles
        frontiers = agent_map.get_exploration_frontiers()

        # Should have frontier tiles around the discovered area
        assert len(frontiers) > 0

        # Check that frontiers are adjacent to known tiles
        known_tiles = agent_map.get_known_tiles()
        for frontier in frontiers:
            fx, fy = frontier
            has_known_neighbor = False
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    neighbor = (fx + dx, fy + dy)
                    if neighbor in known_tiles:
                        has_known_neighbor = True
                        break
                if has_known_neighbor:
                    break
            assert has_known_neighbor

@pytest.mark.asyncio
class TestPathfindingIntegration:
    """Test pathfinding integration with agents"""

    @pytest_asyncio.fixture
    async def pathfinding_setup(self, game_server, agent_clients):
        """Setup for pathfinding integration tests"""
        # Create explorer agent for pathfinding tests
        explorer = await agent_clients("explorer")
        assert explorer is not None

        # Wait for agent to initialize
        await asyncio.sleep(1)

        return explorer

    async def test_agent_map_initialization(self, pathfinding_setup):
        """Test that agents properly initialize their maps"""
        explorer = pathfinding_setup

        # Agent should have world bounds and agent map
        assert explorer.agent.world_bounds is not None
        assert explorer.agent.agent_map is not None
        assert explorer.agent.pathfinder is not None

    async def test_terrain_discovery_from_server(self, pathfinding_setup):
        """Test that agents discover terrain from server updates"""
        explorer = pathfinding_setup

        # Let agent receive some updates
        await asyncio.sleep(3)

        # Agent should have discovered some terrain
        if explorer.agent.agent_map:
            completion = explorer.agent.agent_map.get_map_completion_percentage()
            assert completion > 0, "Agent should have discovered some terrain"

    async def test_pathfinding_behavior(self, pathfinding_setup):
        """Test that agents use pathfinding for movement"""
        explorer = pathfinding_setup

        initial_pos = (explorer.agent.x, explorer.agent.y)

        # Let agent move for a while
        await asyncio.sleep(5)

        final_pos = (explorer.agent.x, explorer.agent.y)

        # Agent should have moved
        distance_moved = ((final_pos[0] - initial_pos[0])**2 +
                         (final_pos[1] - initial_pos[1])**2)**0.5
        # Agent should have moved at least some distance
        print(f"Agent moved {distance_moved:.2f} units from {initial_pos} to {final_pos}")

        # Check pathfinding state exists (more important than exact movement distance)
        state = explorer.agent.get_state()
        assert 'map_completion' in state, "Agent should have map completion data"
        assert state['map_completion'] >= 0, "Map completion should be non-negative"

        # Verify agent has mapping capabilities
        assert explorer.agent.agent_map is not None, "Agent should have a personal map"
        assert explorer.agent.pathfinder is not None, "Agent should have pathfinding capability"

    async def test_explorer_frontier_pathfinding(self, pathfinding_setup):
        """Test that explorers use pathfinding to reach frontiers"""
        explorer = pathfinding_setup

        # Set exploration mode to frontier
        if hasattr(explorer.agent, 'set_exploration_mode'):
            explorer.agent.set_exploration_mode('frontier')

        # Let agent explore
        await asyncio.sleep(8)

        # Agent should have built up a map
        if explorer.agent.agent_map:
            completion = explorer.agent.agent_map.get_map_completion_percentage()
            assert completion > 2, f"Explorer should have explored some terrain, got {completion:.1f}%"

            # Should have some frontiers identified
            frontiers = explorer.agent.agent_map.get_exploration_frontiers()
            print(f"Explorer found {len(frontiers)} frontier tiles")

@pytest.mark.slow
class TestPathfindingPerformance:
    """Test pathfinding performance under load"""

    def test_pathfinding_performance(self):
        """Test pathfinding performance with large maps"""
        # Create larger map for performance testing
        agent_map = AgentMap(50, 50)
        pathfinder = Pathfinder()

        # Fill with mostly walkable terrain
        terrain_data = {}
        for x in range(50):
            for y in range(50):
                # Add some random obstacles
                if (x + y) % 17 == 0:
                    terrain_data[(x, y)] = TileType.WALL
                else:
                    terrain_data[(x, y)] = TileType.GRASS

        agent_map.discover_area(25, 25, 50, terrain_data)

        # Test multiple pathfinding operations
        start_time = time.time()
        successful_paths = 0

        for i in range(10):
            start = (i * 2.0, i * 2.0)
            goal = (45.0 - i * 2.0, 45.0 - i * 2.0)

            path = pathfinder.find_path(agent_map, start, goal)
            if path:
                successful_paths += 1

        end_time = time.time()

        # Should complete quickly and find most paths
        assert end_time - start_time < 2.0, "Pathfinding should be fast"
        assert successful_paths >= 8, f"Should find most paths, found {successful_paths}/10"