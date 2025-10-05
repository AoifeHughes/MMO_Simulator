from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
from opensimplex import OpenSimplex
import random

from .terrain import TerrainType
from .tile import Tile, ResourceDeposit


class WorldGenerator:
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed if seed is not None else random.randint(0, 1000000)
        self.noise = OpenSimplex(seed=self.seed)
        random.seed(self.seed)
        np.random.seed(self.seed)

    def generate_perlin_noise(
        self, width: int, height: int, octaves: int = 4, scale: float = 0.05
    ) -> np.ndarray:
        noise_array = np.zeros((height, width))

        for y in range(height):
            for x in range(width):
                value = 0
                amplitude = 1
                frequency = scale

                for _ in range(octaves):
                    value += self.noise.noise2(
                        x * frequency, y * frequency
                    ) * amplitude
                    amplitude *= 0.5
                    frequency *= 2

                noise_array[y, x] = value

        noise_array = (noise_array - noise_array.min()) / (
            noise_array.max() - noise_array.min()
        )
        return noise_array

    def map_noise_to_terrain(self, noise_array: np.ndarray) -> List[List[Tile]]:
        height, width = noise_array.shape
        tiles = []

        moisture_noise = self.generate_perlin_noise(
            width, height, octaves=3, scale=0.03
        )
        temperature_noise = self.generate_perlin_noise(
            width, height, octaves=2, scale=0.02
        )

        for y in range(height):
            row = []
            for x in range(width):
                elevation = noise_array[y, x]
                moisture = moisture_noise[y, x]
                temperature = temperature_noise[y, x]

                terrain_type = self._determine_terrain(elevation, moisture, temperature)
                tile = Tile(x, y, terrain_type)

                self._add_resources_to_tile(tile)

                row.append(tile)
            tiles.append(row)

        return tiles

    def _determine_terrain(
        self, elevation: float, moisture: float, temperature: float
    ) -> TerrainType:
        if elevation < 0.3:
            return TerrainType.WATER
        elif elevation > 0.8:
            return TerrainType.MOUNTAIN
        elif temperature > 0.6 and moisture < 0.4:
            return TerrainType.DESERT
        elif moisture > 0.5 and elevation < 0.7:
            return TerrainType.FOREST
        else:
            return TerrainType.GRASS

    def _add_resources_to_tile(self, tile: Tile) -> None:
        if tile.terrain_type == TerrainType.WATER:
            if random.random() < 0.3:
                tile.add_resource(ResourceDeposit("fish", 20))

        elif tile.terrain_type == TerrainType.FOREST:
            if random.random() < 0.5:  # Balanced probability for realistic distribution
                tile.add_resource(ResourceDeposit("wood", 30))
            if random.random() < 0.3:
                tile.add_resource(ResourceDeposit("berries", 10))

        elif tile.terrain_type == TerrainType.MOUNTAIN:
            if random.random() < 0.4:  # Balanced probability for realistic distribution
                tile.add_resource(ResourceDeposit("stone", 50))
            if random.random() < 0.2:
                tile.add_resource(ResourceDeposit("iron_ore", 15))
            if random.random() < 0.05:
                tile.add_resource(ResourceDeposit("gold_ore", 5))

        elif tile.terrain_type == TerrainType.GRASS:
            if random.random() < 0.2:  # Balanced probability for realistic distribution
                tile.add_resource(ResourceDeposit("herbs", 15))

    def generate_world(
        self, width: int, height: int, add_spawn_zones: bool = True
    ) -> List[List[Tile]]:
        elevation_noise = self.generate_perlin_noise(width, height)
        tiles = self.map_noise_to_terrain(elevation_noise)

        if add_spawn_zones:
            self._add_spawn_zones(tiles)

        return tiles

    def _add_spawn_zones(self, tiles: List[List[Tile]]) -> None:
        height = len(tiles)
        width = len(tiles[0]) if height > 0 else 0

        if width == 0 or height == 0:
            return

        safe_spots = []
        for y in range(height):
            for x in range(width):
                if tiles[y][x].can_pass():
                    safe_spots.append((x, y))

        if not safe_spots:
            return

        num_agent_spawns = min(5, len(safe_spots) // 10)
        agent_spawns = random.sample(safe_spots, min(num_agent_spawns, len(safe_spots)))
        for x, y in agent_spawns:
            tiles[y][x].add_spawn_zone("agent_spawn")

        remaining_spots = [s for s in safe_spots if s not in agent_spawns]
        if remaining_spots:
            num_npc_spawns = min(10, len(remaining_spots) // 5)
            npc_spawns = random.sample(remaining_spots, min(num_npc_spawns, len(remaining_spots)))
            for x, y in npc_spawns:
                tiles[y][x].add_spawn_zone("npc_spawn")