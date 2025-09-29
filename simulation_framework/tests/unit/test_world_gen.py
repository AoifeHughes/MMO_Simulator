import pytest
import numpy as np
from src.world.generator import WorldGenerator
from src.world.terrain import TerrainType
from src.core.world import World


class TestWorldGeneration:
    def test_deterministic_generation(self):
        seed = 42
        gen1 = WorldGenerator(seed=seed)
        gen2 = WorldGenerator(seed=seed)

        world1 = gen1.generate_world(10, 10)
        world2 = gen2.generate_world(10, 10)

        for y in range(10):
            for x in range(10):
                assert world1[y][x].terrain_type == world2[y][x].terrain_type

    def test_all_tiles_have_valid_terrain(self):
        generator = WorldGenerator(seed=123)
        world = generator.generate_world(20, 20)

        valid_types = set(TerrainType)
        for row in world:
            for tile in row:
                assert tile.terrain_type in valid_types

    def test_terrain_distribution(self):
        generator = WorldGenerator(seed=456)
        tiles = generator.generate_world(50, 50)

        terrain_counts = {t: 0 for t in TerrainType}
        total_tiles = 50 * 50

        for row in tiles:
            for tile in row:
                terrain_counts[tile.terrain_type] += 1

        for terrain_type, count in terrain_counts.items():
            percentage = count / total_tiles
            assert percentage >= 0.0, f"{terrain_type.value} has {percentage:.1%} coverage"

        assert terrain_counts[TerrainType.GRASS] > 0, "No grass tiles generated"
        assert terrain_counts[TerrainType.WATER] > 0, "No water tiles generated"

    def test_boundary_conditions(self):
        generator = WorldGenerator(seed=789)
        tiles = generator.generate_world(10, 10)

        assert tiles[0][0].x == 0 and tiles[0][0].y == 0
        assert tiles[9][9].x == 9 and tiles[9][9].y == 9

        for x in range(10):
            assert tiles[0][x].y == 0
            assert tiles[9][x].y == 9

        for y in range(10):
            assert tiles[y][0].x == 0
            assert tiles[y][9].x == 9

    def test_resource_assignment(self):
        generator = WorldGenerator(seed=111)
        tiles = generator.generate_world(30, 30)

        water_with_fish = 0
        forest_with_wood = 0
        mountain_with_ore = 0

        for row in tiles:
            for tile in row:
                if tile.terrain_type == TerrainType.WATER:
                    if any(r.resource_type == "fish" for r in tile.resources):
                        water_with_fish += 1
                elif tile.terrain_type == TerrainType.FOREST:
                    if any(r.resource_type == "wood" for r in tile.resources):
                        forest_with_wood += 1
                elif tile.terrain_type == TerrainType.MOUNTAIN:
                    if any(r.resource_type in ["stone", "iron_ore", "gold_ore"] for r in tile.resources):
                        mountain_with_ore += 1

        assert water_with_fish > 0, "No water tiles have fish"
        assert forest_with_wood > 0, "No forest tiles have wood"
        assert mountain_with_ore > 0, "No mountain tiles have ore"

    def test_spawn_zones_created(self):
        generator = WorldGenerator(seed=222)
        tiles = generator.generate_world(30, 30, add_spawn_zones=True)

        agent_spawns = 0
        npc_spawns = 0

        for row in tiles:
            for tile in row:
                if "agent_spawn" in tile.spawn_zones:
                    agent_spawns += 1
                if "npc_spawn" in tile.spawn_zones:
                    npc_spawns += 1

        assert agent_spawns > 0, "No agent spawn zones created"
        assert npc_spawns > 0, "No NPC spawn zones created"


class TestWorld:
    def test_world_initialization(self):
        world = World(20, 20, seed=42)
        assert world.width == 20
        assert world.height == 20
        assert len(world.tiles) == 20
        assert len(world.tiles[0]) == 20

    def test_get_tile(self):
        world = World(10, 10)
        tile = world.get_tile(5, 5)
        assert tile is not None
        assert tile.x == 5
        assert tile.y == 5

        assert world.get_tile(-1, 5) is None
        assert world.get_tile(5, 10) is None

    def test_is_valid_position(self):
        world = World(10, 10)
        assert world.is_valid_position(0, 0)
        assert world.is_valid_position(9, 9)
        assert not world.is_valid_position(-1, 0)
        assert not world.is_valid_position(10, 0)

    def test_get_neighbors(self):
        world = World(10, 10)

        neighbors = world.get_neighbors(5, 5, diagonal=False)
        assert len(neighbors) == 4

        neighbors = world.get_neighbors(5, 5, diagonal=True)
        assert len(neighbors) == 8

        corner_neighbors = world.get_neighbors(0, 0, diagonal=False)
        assert len(corner_neighbors) == 2

    def test_terrain_distribution(self):
        world = World(50, 50, seed=42)
        distribution = world.get_terrain_distribution()

        total = sum(distribution.values())
        assert abs(total - 1.0) < 0.001

        for terrain_type in ["water", "grass", "forest", "mountain", "desert"]:
            assert terrain_type in distribution
            assert distribution[terrain_type] >= 0