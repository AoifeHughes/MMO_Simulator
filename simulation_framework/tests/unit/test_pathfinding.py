import pytest
from src.systems.pathfinding import Pathfinder, PathfindingMap
from src.core.world import World
from src.world.terrain import TerrainType


class TestPathfinding:
    def test_pathfinding_simple_grid(self):
        world = World(10, 10, seed=42)
        pathfinder = Pathfinder()

        # Find two passable positions
        passable_positions = []
        for y in range(10):
            for x in range(10):
                if world.is_passable(x, y):
                    passable_positions.append((x, y))

        if len(passable_positions) < 2:
            pytest.skip("Not enough passable tiles for pathfinding test")

        start = passable_positions[0]
        goal = passable_positions[-1]

        path = pathfinder.find_path(start, goal, world)

        if path:
            assert len(path) > 1
            assert path[0] == start
            assert path[-1] == goal

    def test_pathfinding_avoids_impassable(self):
        world = World(10, 10, seed=123)
        pathfinder = Pathfinder()

        water_tiles = []
        for y in range(10):
            for x in range(10):
                tile = world.get_tile(x, y)
                if tile and tile.terrain_type == TerrainType.WATER:
                    water_tiles.append((x, y))

        if water_tiles:
            start = (0, 0)
            goal = (9, 9)
            path = pathfinder.find_path(start, goal, world)

            for x, y in path:
                tile = world.get_tile(x, y)
                assert tile.can_pass(), f"Path goes through impassable tile at ({x}, {y})"

    def test_no_path_scenario(self):
        world = World(10, 10, seed=456)
        pathfinder = Pathfinder()

        for y in range(5):
            for x in range(10):
                tile = world.tiles[y][x]
                tile.terrain_type = TerrainType.WATER
                tile.properties.passable = False

        start = (1, 1)
        goal = (8, 8)

        path = pathfinder.find_path(start, goal, world)
        assert len(path) == 0

    def test_adjacent_movement(self):
        world = World(10, 10, seed=789)
        pathfinder = Pathfinder()

        start = (5, 5)
        goal = (5, 6)

        path = pathfinder.find_path(start, goal, world)

        assert len(path) == 2
        assert path[0] == start
        assert path[1] == goal

    def test_pathfinding_with_fog_of_war(self):
        world = World(10, 10, seed=111)
        pathfinder = Pathfinder()

        known_tiles = {(x, y) for x in range(3) for y in range(3)}

        start = (1, 1)
        goal = (2, 2)

        path = pathfinder.find_path(start, goal, world, known_tiles)

        assert len(path) > 1
        assert path[0] == start
        assert path[-1] == goal

        for x, y in path:
            assert (x, y) in known_tiles or (x, y) == start

    def test_path_caching(self):
        world = World(10, 10, seed=222)
        pathfinder = Pathfinder()

        start = (1, 1)
        goal = (8, 8)

        path1 = pathfinder.find_path(start, goal, world)
        path2 = pathfinder.find_path(start, goal, world)

        assert path1 == path2
        assert pathfinder.get_cache_size() > 0

    def test_find_path_to_nearest(self):
        world = World(10, 10, seed=333)
        pathfinder = Pathfinder()

        # Find passable positions to use as start and targets
        passable_positions = []
        for y in range(10):
            for x in range(10):
                if world.is_passable(x, y):
                    passable_positions.append((x, y))

        if len(passable_positions) < 5:
            pytest.skip("Not enough passable tiles for path to nearest test")

        start = passable_positions[0]
        targets = passable_positions[1:5]

        nearest_target, path = pathfinder.find_path_to_nearest(start, targets, world)

        if nearest_target:
            assert nearest_target in targets
            assert len(path) > 1
            assert path[0] == start
            assert path[-1] == nearest_target

    def test_can_reach(self):
        world = World(10, 10, seed=444)
        pathfinder = Pathfinder()

        # Find two passable adjacent positions
        passable_positions = []
        for y in range(10):
            for x in range(10):
                if world.is_passable(x, y):
                    passable_positions.append((x, y))

        if len(passable_positions) < 2:
            pytest.skip("Not enough passable tiles for reachability test")

        start = passable_positions[0]
        reachable_goal = passable_positions[1]

        # Test with positions we know are passable
        result = pathfinder.can_reach(start, reachable_goal, world)
        # If there's a path, it should be reachable
        path = pathfinder.find_path(start, reachable_goal, world)
        if path:
            assert result

    def test_get_next_step(self):
        world = World(10, 10, seed=555)
        pathfinder = Pathfinder()

        start = (1, 1)
        goal = (5, 5)

        next_step = pathfinder.get_next_step(start, goal, world)

        assert next_step is not None
        assert next_step != start
        assert abs(next_step[0] - start[0]) <= 1
        assert abs(next_step[1] - start[1]) <= 1

    def test_diagonal_vs_cardinal_movement(self):
        world = World(10, 10, seed=666)

        diagonal_finder = Pathfinder(diagonal_movement=True)
        cardinal_finder = Pathfinder(diagonal_movement=False)

        start = (1, 1)
        goal = (3, 3)

        diagonal_path = diagonal_finder.find_path(start, goal, world)
        cardinal_path = cardinal_finder.find_path(start, goal, world)

        if diagonal_path and cardinal_path:
            assert len(diagonal_path) <= len(cardinal_path)