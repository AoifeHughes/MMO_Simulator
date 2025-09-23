import heapq
import math
from typing import Dict, List, Optional, Set, Tuple

from client.agent_map import AgentMap


class PathNode:
    """Node representing a position in the pathfinding graph"""

    def __init__(
        self, x: int, y: int, cost: float = 0.0, parent: Optional["PathNode"] = None
    ):
        self.x = x
        self.y = y
        self.cost = cost  # Total cost from start to this node
        self.parent = parent

    def __lt__(self, other: "PathNode") -> bool:
        return self.cost < other.cost

    def __eq__(self, other: "PathNode") -> bool:
        return self.x == other.x and self.y == other.y

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def get_position(self) -> Tuple[int, int]:
        return (self.x, self.y)


class Pathfinder:
    """Dijkstra's algorithm implementation for agent pathfinding"""

    def __init__(self):
        self.directions = [
            (-1, -1),
            (-1, 0),
            (-1, 1),  # Northwest, North, Northeast
            (0, -1),
            (0, 1),  # West, East
            (1, -1),
            (1, 0),
            (1, 1),  # Southwest, South, Southeast
        ]

    def find_path(
        self, agent_map: AgentMap, start: Tuple[float, float], goal: Tuple[float, float]
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Find optimal path from start to goal using Dijkstra's algorithm
        Returns list of waypoints as (x, y) coordinates, or None if no path exists
        """
        # Convert float coordinates to tile coordinates
        start_tile = (int(start[0]), int(start[1]))
        goal_tile = (int(goal[0]), int(goal[1]))

        # Check if start and goal are valid
        if not agent_map.is_valid_position(start_tile[0], start_tile[1]):
            return None
        if not agent_map.is_valid_position(goal_tile[0], goal_tile[1]):
            return None

        # If goal is unknown or unwalkable, return None
        if not agent_map.is_tile_known(goal_tile[0], goal_tile[1]):
            return None
        if not agent_map.is_walkable(goal_tile[0], goal_tile[1]):
            return None

        # If start and goal are the same, return direct path
        if start_tile == goal_tile:
            return [start, goal]

        # Initialize Dijkstra's algorithm
        open_set = []  # Priority queue of nodes to explore
        closed_set: Set[Tuple[int, int]] = set()  # Already explored nodes
        cost_so_far: Dict[Tuple[int, int], float] = {}

        # Start node
        start_node = PathNode(start_tile[0], start_tile[1], 0.0)
        heapq.heappush(open_set, start_node)
        cost_so_far[start_tile] = 0.0

        while open_set:
            current = heapq.heappop(open_set)
            current_pos = current.get_position()

            # If we reached the goal, reconstruct path
            if current_pos == goal_tile:
                return self._reconstruct_path(current, start, goal)

            # Mark current node as explored
            closed_set.add(current_pos)

            # Explore neighbors
            for dx, dy in self.directions:
                neighbor_x = current.x + dx
                neighbor_y = current.y + dy
                neighbor_pos = (neighbor_x, neighbor_y)

                # Skip if out of bounds or already explored
                if not agent_map.is_valid_position(neighbor_x, neighbor_y):
                    continue
                if neighbor_pos in closed_set:
                    continue

                # Skip if tile is unknown or unwalkable
                if not agent_map.is_tile_known(neighbor_x, neighbor_y):
                    continue
                if not agent_map.is_walkable(neighbor_x, neighbor_y):
                    continue

                # Calculate movement cost
                movement_cost = agent_map.get_movement_cost(neighbor_x, neighbor_y)
                if movement_cost == float("inf"):
                    continue

                # Calculate distance cost (diagonal movement costs more)
                distance_cost = math.sqrt(dx * dx + dy * dy)
                new_cost = current.cost + (movement_cost * distance_cost)

                # Check if this path to neighbor is better
                if (
                    neighbor_pos not in cost_so_far
                    or new_cost < cost_so_far[neighbor_pos]
                ):
                    cost_so_far[neighbor_pos] = new_cost
                    neighbor_node = PathNode(neighbor_x, neighbor_y, new_cost, current)
                    heapq.heappush(open_set, neighbor_node)

        # No path found
        return None

    def _reconstruct_path(
        self, goal_node: PathNode, start: Tuple[float, float], goal: Tuple[float, float]
    ) -> List[Tuple[float, float]]:
        """Reconstruct path from goal node back to start"""
        path_tiles = []
        current = goal_node

        # Build path from goal to start
        while current is not None:
            path_tiles.append((current.x, current.y))
            current = current.parent

        # Reverse to get start to goal
        path_tiles.reverse()

        # Convert tile coordinates back to world coordinates
        path = []
        for i, (tile_x, tile_y) in enumerate(path_tiles):
            if i == 0:
                # First waypoint is the exact start position
                path.append(start)
            elif i == len(path_tiles) - 1:
                # Last waypoint is the exact goal position
                path.append(goal)
            else:
                # Intermediate waypoints are tile centers
                path.append((tile_x + 0.5, tile_y + 0.5))

        return path

    def find_path_to_nearest_frontier(
        self, agent_map: AgentMap, start: Tuple[float, float]
    ) -> Optional[List[Tuple[float, float]]]:
        """
        Find path to the nearest exploration frontier (unknown tile adjacent to known tiles)
        Useful for exploration agents
        """
        frontiers = agent_map.get_exploration_frontiers()
        if not frontiers:
            return None

        # Find the closest frontier tile
        start_tile = (int(start[0]), int(start[1]))
        best_frontier = None
        best_distance = float("inf")

        for frontier_x, frontier_y in frontiers:
            distance = math.sqrt(
                (frontier_x - start_tile[0]) ** 2 + (frontier_y - start_tile[1]) ** 2
            )
            if distance < best_distance:
                best_distance = distance
                best_frontier = (frontier_x, frontier_y)

        if best_frontier is None:
            return None

        # Find a walkable tile adjacent to the frontier
        frontier_x, frontier_y = best_frontier
        target_positions = []

        # Check all positions adjacent to the frontier
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                adj_x, adj_y = frontier_x + dx, frontier_y + dy
                if (
                    agent_map.is_valid_position(adj_x, adj_y)
                    and agent_map.is_tile_known(adj_x, adj_y)
                    and agent_map.is_walkable(adj_x, adj_y)
                ):
                    target_positions.append((adj_x + 0.5, adj_y + 0.5))

        # Try to find a path to one of the adjacent positions
        for target in target_positions:
            path = self.find_path(agent_map, start, target)
            if path is not None:
                return path

        return None

    def simplify_path(
        self, path: List[Tuple[float, float]], max_waypoints: int = 10
    ) -> List[Tuple[float, float]]:
        """
        Simplify path by reducing the number of waypoints while maintaining general direction
        Useful for smoother agent movement
        """
        if not path or len(path) <= max_waypoints:
            return path

        # Always keep start and end points
        simplified = [path[0]]

        # Calculate step size for intermediate waypoints
        step = max(1, len(path) // (max_waypoints - 1))

        # Add intermediate waypoints
        for i in range(step, len(path) - 1, step):
            simplified.append(path[i])

        # Always include the final destination
        if path[-1] not in simplified:
            simplified.append(path[-1])

        return simplified

    def get_next_waypoint(
        self,
        path: List[Tuple[float, float]],
        current_pos: Tuple[float, float],
        waypoint_threshold: float = 0.5,
    ) -> Optional[Tuple[float, float]]:
        """
        Get the next waypoint from a path that the agent should move toward
        Returns None if path is complete
        """
        if not path:
            return None

        # Find the first waypoint that's far enough away
        for waypoint in path:
            distance = math.sqrt(
                (waypoint[0] - current_pos[0]) ** 2
                + (waypoint[1] - current_pos[1]) ** 2
            )
            if distance > waypoint_threshold:
                return waypoint

        # If all waypoints are close, return the last one
        return path[-1] if path else None
