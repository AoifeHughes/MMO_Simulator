from __future__ import annotations
from typing import List, Tuple, Optional, Set, Dict, TYPE_CHECKING
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
import math

if TYPE_CHECKING:
    from ..core.world import World


class PathfindingMap:
    def __init__(self, world: World, known_tiles: Optional[Set[Tuple[int, int]]] = None):
        self.world = world
        self.known_tiles = known_tiles
        self._grid = None
        self._create_grid()

    def _create_grid(self) -> None:
        matrix = []
        for y in range(self.world.height):
            row = []
            for x in range(self.world.width):
                if self.known_tiles and (x, y) not in self.known_tiles:
                    row.append(0)
                else:
                    tile = self.world.get_tile(x, y)
                    if tile and tile.can_pass():
                        row.append(1)
                    else:
                        row.append(0)
            matrix.append(row)

        self._grid = Grid(matrix=matrix)

    def get_grid(self) -> Grid:
        if self._grid is None:
            self._create_grid()
        return self._grid

    def refresh(self) -> None:
        self._create_grid()


class Pathfinder:
    def __init__(self, diagonal_movement: bool = True):
        self.diagonal_movement = DiagonalMovement.always if diagonal_movement else DiagonalMovement.never
        self.finder = AStarFinder(diagonal_movement=self.diagonal_movement)
        self._path_cache: Dict[Tuple, List[Tuple[int, int]]] = {}
        self._cache_max_size = 100

    def find_path(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        world: World,
        known_tiles: Optional[Set[Tuple[int, int]]] = None
    ) -> List[Tuple[int, int]]:
        cache_key = (start, goal, id(world), id(known_tiles))

        if cache_key in self._path_cache:
            return self._path_cache[cache_key].copy()

        path_map = PathfindingMap(world, known_tiles)
        grid = path_map.get_grid()

        start_node = grid.node(start[0], start[1])
        goal_node = grid.node(goal[0], goal[1])

        if not start_node.walkable or not goal_node.walkable:
            return []

        path, _ = self.finder.find_path(start_node, goal_node, grid)

        path_coords = [(node.x, node.y) for node in path]

        if len(self._path_cache) >= self._cache_max_size:
            self._path_cache.clear()

        self._path_cache[cache_key] = path_coords.copy()

        return path_coords

    def find_path_to_nearest(
        self,
        start: Tuple[int, int],
        targets: List[Tuple[int, int]],
        world: World,
        known_tiles: Optional[Set[Tuple[int, int]]] = None
    ) -> Tuple[Optional[Tuple[int, int]], List[Tuple[int, int]]]:
        best_target = None
        best_path = []
        shortest_distance = float('inf')

        for target in targets:
            path = self.find_path(start, target, world, known_tiles)
            if path and len(path) < shortest_distance:
                best_target = target
                best_path = path
                shortest_distance = len(path)

        return best_target, best_path

    def can_reach(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        world: World,
        known_tiles: Optional[Set[Tuple[int, int]]] = None
    ) -> bool:
        path = self.find_path(start, goal, world, known_tiles)
        return len(path) > 1

    def get_next_step(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        world: World,
        known_tiles: Optional[Set[Tuple[int, int]]] = None
    ) -> Optional[Tuple[int, int]]:
        path = self.find_path(start, goal, world, known_tiles)
        if len(path) > 1:
            return path[1]
        return None

    def distance_heuristic(self, pos1: Tuple[int, int], pos2: Tuple[int, int]) -> float:
        if self.diagonal_movement == DiagonalMovement.never:
            return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])
        else:
            return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def clear_cache(self) -> None:
        self._path_cache.clear()

    def get_cache_size(self) -> int:
        return len(self._path_cache)