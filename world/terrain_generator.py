"""
Terrain generator using Perlin noise for creating varied, realistic maps.
Uses fixed seeds for reproducibility.
"""

import random
from enum import Enum
from typing import List

import noise

from world.tiles import TileType


class TerrainType(Enum):
    """Different terrain generation types for various scenarios"""

    GRASSLAND = "grassland"  # Mostly flat grassland with some features
    ARCHIPELAGO = "archipelago"  # Islands and water
    MOUNTAIN = "mountain"  # Mountainous terrain with valleys
    DESERT = "desert"  # Desert with oases
    FOREST = "forest"  # Dense forest with clearings
    MIXED = "mixed"  # Varied biomes


class TerrainGenerator:
    """Generates terrain using Perlin noise with fixed seeds"""

    def __init__(
        self,
        width: int,
        height: int,
        seed: int = 42,
        terrain_type: TerrainType = TerrainType.MIXED,
    ):
        self.width = width
        self.height = height
        self.seed = seed
        self.terrain_type = terrain_type

        # Configure noise parameters based on terrain type
        self.configure_terrain_params()

    def configure_terrain_params(self):
        """Set parameters based on terrain type"""
        if self.terrain_type == TerrainType.GRASSLAND:
            self.scale = 0.05
            self.octaves = 3
            self.persistence = 0.5
            self.lacunarity = 2.0
            self.water_threshold = -0.4  # More water in grassland
            self.sand_threshold = -0.3
            self.grass_threshold = 0.3
            self.stone_threshold = 0.5
            self.mountain_threshold = 0.7

        elif self.terrain_type == TerrainType.ARCHIPELAGO:
            self.scale = 0.03
            self.octaves = 4
            self.persistence = 0.6
            self.lacunarity = 2.5
            self.water_threshold = 0.0  # More water
            self.sand_threshold = 0.15
            self.grass_threshold = 0.4
            self.stone_threshold = 0.6
            self.mountain_threshold = 0.8

        elif self.terrain_type == TerrainType.MOUNTAIN:
            self.scale = 0.04
            self.octaves = 5
            self.persistence = 0.7
            self.lacunarity = 2.0
            self.water_threshold = -0.7
            self.sand_threshold = -0.6
            self.grass_threshold = 0.1
            self.stone_threshold = 0.3  # More stone/mountains
            self.mountain_threshold = 0.5

        elif self.terrain_type == TerrainType.DESERT:
            self.scale = 0.06
            self.octaves = 3
            self.persistence = 0.4
            self.lacunarity = 2.0
            self.water_threshold = -0.8  # Very little water
            self.sand_threshold = 0.5  # Lots of sand
            self.grass_threshold = 0.7
            self.stone_threshold = 0.8
            self.mountain_threshold = 0.9

        elif self.terrain_type == TerrainType.FOREST:
            self.scale = 0.08
            self.octaves = 3
            self.persistence = 0.5
            self.lacunarity = 2.0
            self.water_threshold = -0.3  # More water in forests
            self.sand_threshold = -0.2
            self.grass_threshold = 0.6  # More grass/forest
            self.stone_threshold = 0.8
            self.mountain_threshold = 0.9

        else:  # MIXED
            self.scale = 0.05
            self.octaves = 4
            self.persistence = 0.5
            self.lacunarity = 2.0
            self.water_threshold = -0.2  # More water in mixed terrain
            self.sand_threshold = -0.1
            self.grass_threshold = 0.3
            self.stone_threshold = 0.5
            self.mountain_threshold = 0.7

    def generate_elevation_map(self) -> List[List[float]]:
        """Generate elevation map using Perlin noise"""
        elevation_map = []

        for y in range(self.height):
            row = []
            for x in range(self.width):
                # Generate Perlin noise value
                value = noise.pnoise2(
                    x * self.scale,
                    y * self.scale,
                    octaves=self.octaves,
                    persistence=self.persistence,
                    lacunarity=self.lacunarity,
                    repeatx=self.width,
                    repeaty=self.height,
                    base=self.seed,
                )

                # Add edge falloff for island-like generation
                if self.terrain_type == TerrainType.ARCHIPELAGO:
                    # Calculate distance from center
                    cx = self.width / 2
                    cy = self.height / 2
                    dx = abs(x - cx) / cx
                    dy = abs(y - cy) / cy
                    distance = max(dx, dy)

                    # Apply falloff
                    falloff = max(0, 1 - distance**2)
                    value = value * falloff - (1 - falloff) * 0.5

                row.append(value)
            elevation_map.append(row)

        return elevation_map

    def generate_moisture_map(self) -> List[List[float]]:
        """Generate moisture map for biome variation"""
        moisture_map = []

        # Use different seed for moisture
        moisture_seed = self.seed + 1000

        for y in range(self.height):
            row = []
            for x in range(self.width):
                value = noise.pnoise2(
                    x * self.scale * 1.5,  # Different scale for variety
                    y * self.scale * 1.5,
                    octaves=2,
                    persistence=0.6,
                    lacunarity=2.0,
                    repeatx=self.width,
                    repeaty=self.height,
                    base=moisture_seed,
                )
                row.append(value)
            moisture_map.append(row)

        return moisture_map

    def elevation_to_tile(
        self, elevation: float, moisture: float, x: int, y: int
    ) -> TileType:
        """Convert elevation and moisture values to tile type"""

        # Water bodies
        if elevation < self.water_threshold:
            return TileType.WATER

        # Beach/Sand near water
        if elevation < self.sand_threshold:
            return TileType.SAND

        # Low elevation - grass or dirt based on moisture
        if elevation < self.grass_threshold:
            if self.terrain_type == TerrainType.DESERT:
                return TileType.SAND if moisture < 0 else TileType.DIRT
            elif self.terrain_type == TerrainType.FOREST:
                # Add trees (represented as wood tiles) in forests
                if moisture > 0.2 and random.random() < 0.3:
                    return TileType.WOOD
            return TileType.GRASS if moisture > -0.2 else TileType.DIRT

        # Mid elevation - grass or stone
        if elevation < self.stone_threshold:
            if self.terrain_type == TerrainType.FOREST and moisture > 0:
                return TileType.WOOD if random.random() < 0.2 else TileType.GRASS
            return TileType.GRASS if moisture > 0 else TileType.STONE

        # High elevation - stone or mountain peaks
        if elevation < self.mountain_threshold:
            return TileType.STONE

        # Mountain peaks - mostly stone, some walls for impassable terrain
        if random.random() < 0.3:
            return TileType.WALL  # Impassable mountain peaks
        return TileType.STONE

    def add_features(self, tiles: List[List[TileType]]):
        """Add special features like paths, structures, etc."""
        random.seed(self.seed + 2000)

        # Add guaranteed water bodies for most terrain types
        if (
            self.terrain_type != TerrainType.ARCHIPELAGO
        ):  # Archipelago already has lots of water
            self.add_water_bodies(tiles)

        # Add some paths in grassland and mixed terrains
        if self.terrain_type in [TerrainType.GRASSLAND, TerrainType.MIXED]:
            self.add_paths(tiles)

        # Add oases in deserts (these will be in addition to regular water bodies)
        if self.terrain_type == TerrainType.DESERT:
            self.add_oases(tiles)

        # Add rivers connecting water bodies
        if self.terrain_type in [
            TerrainType.MIXED,
            TerrainType.FOREST,
            TerrainType.MOUNTAIN,
        ]:
            self.add_rivers(tiles)

        # Add bridges over water
        self.add_bridges(tiles)

        random.seed()  # Reset random seed

    def add_paths(self, tiles: List[List[TileType]]):
        """Add dirt paths through the terrain"""
        # Create a few random paths
        num_paths = random.randint(1, 3)

        for _ in range(num_paths):
            # Random start and end points on edges
            if random.random() < 0.5:
                # Horizontal path
                y = random.randint(self.height // 4, 3 * self.height // 4)
                for x in range(self.width):
                    if tiles[y][x] in [TileType.GRASS, TileType.SAND]:
                        tiles[y][x] = TileType.DIRT
                        # Make path wider
                        if y > 0 and tiles[y - 1][x] == TileType.GRASS:
                            tiles[y - 1][x] = TileType.DIRT
                        if y < self.height - 1 and tiles[y + 1][x] == TileType.GRASS:
                            tiles[y + 1][x] = TileType.DIRT
            else:
                # Vertical path
                x = random.randint(self.width // 4, 3 * self.width // 4)
                for y in range(self.height):
                    if tiles[y][x] in [TileType.GRASS, TileType.SAND]:
                        tiles[y][x] = TileType.DIRT
                        # Make path wider
                        if x > 0 and tiles[y][x - 1] == TileType.GRASS:
                            tiles[y][x - 1] = TileType.DIRT
                        if x < self.width - 1 and tiles[y][x + 1] == TileType.GRASS:
                            tiles[y][x + 1] = TileType.DIRT

    def add_oases(self, tiles: List[List[TileType]]):
        """Add oases to desert terrain"""
        num_oases = random.randint(2, 5)

        for _ in range(num_oases):
            cx = random.randint(10, self.width - 10)
            cy = random.randint(10, self.height - 10)
            radius = random.randint(3, 6)

            for y in range(max(0, cy - radius), min(self.height, cy + radius)):
                for x in range(max(0, cx - radius), min(self.width, cx + radius)):
                    dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                    if dist < radius / 2:
                        tiles[y][x] = TileType.WATER
                    elif dist < radius:
                        tiles[y][x] = TileType.GRASS

    def add_water_bodies(self, tiles: List[List[TileType]]):
        """Add guaranteed lakes and water bodies"""
        if self.terrain_type == TerrainType.DESERT:
            # Small oases-like water bodies for desert
            num_bodies = random.randint(1, 2)
            min_size, max_size = 2, 4
        elif self.terrain_type == TerrainType.GRASSLAND:
            # Ponds and small lakes for grassland
            num_bodies = random.randint(2, 4)
            min_size, max_size = 3, 6
        elif self.terrain_type == TerrainType.FOREST:
            # Forest ponds and streams
            num_bodies = random.randint(3, 5)
            min_size, max_size = 2, 5
        elif self.terrain_type == TerrainType.MOUNTAIN:
            # Mountain lakes
            num_bodies = random.randint(2, 3)
            min_size, max_size = 4, 7
        else:  # MIXED
            # Varied water bodies
            num_bodies = random.randint(3, 6)
            min_size, max_size = 3, 8

        # Generate lakes
        for _ in range(num_bodies):
            # Skip if map is too small for water bodies of this size
            if max_size * 2 >= min(self.width, self.height):
                continue

            # Try to place a water body
            attempts = 20
            for _ in range(attempts):
                cx = random.randint(max_size, self.width - max_size)
                cy = random.randint(max_size, self.height - max_size)

                # Check if area is suitable (not too much water already)
                existing_water = sum(
                    1
                    for dy in range(-max_size, max_size + 1)
                    for dx in range(-max_size, max_size + 1)
                    if (
                        0 <= cy + dy < self.height
                        and 0 <= cx + dx < self.width
                        and tiles[cy + dy][cx + dx] == TileType.WATER
                    )
                )

                if existing_water < 5:  # Not too crowded
                    self.create_lake(tiles, cx, cy, random.randint(min_size, max_size))
                    break

    def create_lake(self, tiles: List[List[TileType]], cx: int, cy: int, size: int):
        """Create a natural-looking lake"""
        # Create irregular shape using multiple circles
        num_circles = random.randint(1, 3)

        for _ in range(num_circles):
            # Offset center slightly for irregular shape
            offset_x = random.randint(-size // 2, size // 2)
            offset_y = random.randint(-size // 2, size // 2)
            circle_cx = max(0, min(self.width - 1, cx + offset_x))
            circle_cy = max(0, min(self.height - 1, cy + offset_y))
            circle_size = random.randint(size // 2, size)

            # Create circular water body
            for y in range(
                max(0, circle_cy - circle_size),
                min(self.height, circle_cy + circle_size + 1),
            ):
                for x in range(
                    max(0, circle_cx - circle_size),
                    min(self.width, circle_cx + circle_size + 1),
                ):
                    dist = ((x - circle_cx) ** 2 + (y - circle_cy) ** 2) ** 0.5

                    # Create water with some randomness for natural edges
                    if dist < circle_size * 0.6:
                        tiles[y][x] = TileType.WATER
                    elif dist < circle_size * 0.8 and random.random() < 0.7:
                        tiles[y][x] = TileType.WATER
                    elif dist < circle_size and random.random() < 0.3:
                        tiles[y][x] = TileType.WATER

                    # Add sand/beach around water
                    elif dist < circle_size * 1.2 and random.random() < 0.4:
                        if tiles[y][x] not in [
                            TileType.WATER,
                            TileType.STONE,
                            TileType.WALL,
                        ]:
                            tiles[y][x] = TileType.SAND

    def add_rivers(self, tiles: List[List[TileType]]):
        """Add rivers connecting water bodies"""
        # Find existing water bodies
        water_centers = []

        # Simple water body detection - find clusters
        for y in range(5, self.height - 5):
            for x in range(5, self.width - 5):
                if tiles[y][x] == TileType.WATER:
                    # Count nearby water
                    water_count = sum(
                        1
                        for dy in range(-2, 3)
                        for dx in range(-2, 3)
                        if tiles[y + dy][x + dx] == TileType.WATER
                    )
                    if water_count > 8:  # This is likely a lake center
                        # Check if we already have a center nearby
                        too_close = any(
                            abs(x - wx) + abs(y - wy) < 10 for wx, wy in water_centers
                        )
                        if not too_close:
                            water_centers.append((x, y))

        # Connect some water bodies with rivers
        if len(water_centers) >= 2:
            num_rivers = min(2, len(water_centers) - 1)

            for i in range(num_rivers):
                start_x, start_y = water_centers[i]
                end_x, end_y = water_centers[i + 1]

                # Create a winding river
                self.create_river(tiles, start_x, start_y, end_x, end_y)

    def create_river(
        self,
        tiles: List[List[TileType]],
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
    ):
        """Create a winding river between two points"""
        current_x, current_y = start_x, start_y

        # Add some randomness to path
        steps = max(abs(end_x - start_x), abs(end_y - start_y))

        for step in range(steps):
            # Progress toward target with some wandering
            if current_x < end_x:
                current_x += random.choice([0, 1, 1])  # Bias toward target
            elif current_x > end_x:
                current_x += random.choice([-1, -1, 0])

            if current_y < end_y:
                current_y += random.choice([0, 1, 1])
            elif current_y > end_y:
                current_y += random.choice([-1, -1, 0])

            # Add some perpendicular wandering
            current_x += random.randint(-1, 1)
            current_y += random.randint(-1, 1)

            # Keep in bounds
            current_x = max(1, min(self.width - 2, current_x))
            current_y = max(1, min(self.height - 2, current_y))

            # Create river (1-2 tiles wide)
            if 0 <= current_y < self.height and 0 <= current_x < self.width:
                tiles[current_y][current_x] = TileType.WATER

                # Randomly add width
                if random.random() < 0.3:
                    for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                        nx, ny = current_x + dx, current_y + dy
                        if 0 <= ny < self.height and 0 <= nx < self.width:
                            if tiles[ny][nx] not in [TileType.STONE, TileType.WALL]:
                                tiles[ny][nx] = TileType.WATER

    def add_bridges(self, tiles: List[List[TileType]]):
        """Add bridges over narrow water passages"""
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                # Check for water tiles that could use a bridge
                if tiles[y][x] == TileType.WATER:
                    # Check if there's land on opposite sides (horizontal bridge)
                    if (
                        tiles[y][x - 1] != TileType.WATER
                        and tiles[y][x + 1] != TileType.WATER
                        and tiles[y - 1][x] == TileType.WATER
                        and tiles[y + 1][x] == TileType.WATER
                    ):
                        if random.random() < 0.3:  # Don't bridge everything
                            tiles[y][x] = TileType.BRIDGE
                    # Check for vertical bridge
                    elif (
                        tiles[y - 1][x] != TileType.WATER
                        and tiles[y + 1][x] != TileType.WATER
                        and tiles[y][x - 1] == TileType.WATER
                        and tiles[y][x + 1] == TileType.WATER
                    ):
                        if random.random() < 0.3:
                            tiles[y][x] = TileType.BRIDGE

    def generate(self) -> List[List[TileType]]:
        """Generate the complete terrain map"""
        # Generate base maps
        elevation_map = self.generate_elevation_map()
        moisture_map = self.generate_moisture_map()

        # Reset random seed for consistent tile generation
        random.seed(self.seed)

        # Convert to tiles
        tiles = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                tile = self.elevation_to_tile(
                    elevation_map[y][x], moisture_map[y][x], x, y
                )
                row.append(tile)
            tiles.append(row)

        # Add special features
        self.add_features(tiles)

        # Reset random seed
        random.seed()

        return tiles


def generate_terrain(
    width: int,
    height: int,
    seed: int = 42,
    terrain_type: TerrainType = TerrainType.MIXED,
) -> List[List[TileType]]:
    """Convenience function to generate terrain"""
    generator = TerrainGenerator(width, height, seed, terrain_type)
    return generator.generate()
