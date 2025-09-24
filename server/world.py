import time
import uuid
from typing import Dict, List, Optional, Tuple

from shared.collision import CollisionDetector
from shared.constants import DEFAULT_VISION_ANGLE, DEFAULT_VISION_RANGE
from shared.messages import AgentData
from world.map import WorldMap
from world.terrain_generator import TerrainType
from world.tiles import TileType
from world.vision import VisionSystem


class ServerWorld:
    def __init__(
        self,
        width: int,
        height: int,
        terrain_type: Optional[TerrainType] = None,
        seed: int = 42,
        use_perlin: bool = True,
    ):
        self.world_map = WorldMap(
            width, height, terrain_type=terrain_type, seed=seed, use_perlin=use_perlin
        )
        self.vision_system = VisionSystem(self.world_map)
        self.collision_detector = CollisionDetector(width, height)
        self.agents: Dict[str, AgentData] = {}
        self.last_update = time.time()

    def spawn_agent(
        self,
        agent_type: str,
        x: Optional[float] = None,
        y: Optional[float] = None,
        rotation: float = 0.0,
    ) -> str:
        agent_id = str(uuid.uuid4())

        if x is None or y is None:
            # Get positions of existing agents for collision avoidance
            existing_positions = [(agent.x, agent.y) for agent in self.agents.values()]
            x, y = self.collision_detector.get_safe_spawn_position(
                existing_positions, world_map=self.world_map
            )
        else:
            # Ensure provided position is within bounds and on walkable terrain
            x, y = self.collision_detector.clamp_to_bounds(x, y)

            # If the clamped position is not walkable, find a nearby walkable position
            if not self.world_map.is_walkable(int(x), int(y)):
                x, y = self.find_nearest_walkable_position(x, y)

        agent = AgentData(
            id=agent_id,
            x=x,
            y=y,
            rotation=rotation,
            agent_type=agent_type,
            health=100.0,
            vision_range=DEFAULT_VISION_RANGE,
        )

        self.agents[agent_id] = agent
        return agent_id

    def despawn_agent(self, agent_id: str) -> bool:
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False

    def move_agent(
        self,
        agent_id: str,
        new_x: float,
        new_y: float,
        rotation: float,
        velocity_x: float = 0.0,
        velocity_y: float = 0.0,
    ) -> bool:
        if agent_id not in self.agents:
            return False

        agent = self.agents[agent_id]

        # Don't allow dead agents to move
        if not agent.is_alive:
            return False
        current_pos = (agent.x, agent.y)
        intended_pos = (new_x, new_y)

        # Get positions of other agents for collision checking
        other_agents = [(a.x, a.y) for aid, a in self.agents.items() if aid != agent_id]

        # Resolve collisions and get safe position
        safe_x, safe_y = self.collision_detector.resolve_movement_collision(
            current_pos, intended_pos, other_agents
        )

        # Enhanced terrain validation
        if not self.validate_movement_path(current_pos, (safe_x, safe_y)):
            # Calculate intended movement direction to prefer corrections in that direction
            intended_direction = (safe_x - current_pos[0], safe_y - current_pos[1])
            direction_length = (intended_direction[0] ** 2 + intended_direction[1] ** 2) ** 0.5

            if direction_length > 0.01:  # Avoid division by zero for very small movements
                normalized_direction = (intended_direction[0] / direction_length, intended_direction[1] / direction_length)
            else:
                normalized_direction = None

            # Movement blocked by terrain - try to find nearby walkable position
            safe_x, safe_y = self.find_nearest_walkable_position(safe_x, safe_y, preferred_direction=normalized_direction)

            # If still not walkable, reject movement
            if not self.world_map.is_walkable(round(safe_x), round(safe_y)):
                return False

        # Apply movement cost penalty for difficult terrain
        movement_cost = self.get_movement_cost_penalty(safe_x, safe_y)

        # Reduce velocity based on terrain difficulty
        adjusted_velocity_x = velocity_x * movement_cost
        adjusted_velocity_y = velocity_y * movement_cost

        # Update agent position and velocity
        agent.x = safe_x
        agent.y = safe_y
        agent.rotation = rotation
        agent.velocity_x = adjusted_velocity_x
        agent.velocity_y = adjusted_velocity_y

        return True

    def get_visible_agents(
        self,
        agent_id: str,
        vision_range: float = DEFAULT_VISION_RANGE,
        vision_angle: float = DEFAULT_VISION_ANGLE,
    ) -> List[AgentData]:
        if agent_id not in self.agents:
            return []

        observer = self.agents[agent_id]
        origin = (observer.x, observer.y)

        entities = [
            (aid, (a.x, a.y))
            for aid, a in self.agents.items()
            if aid != agent_id and a.is_alive
        ]

        visible_ids = self.vision_system.get_entities_in_vision(
            origin, observer.rotation, vision_angle, vision_range, entities
        )

        return [self.agents[aid] for aid in visible_ids if aid in self.agents]

    def get_agent(self, agent_id: str) -> Optional[AgentData]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> List[AgentData]:
        return list(self.agents.values())

    def update_agent_health(
        self, agent_id: str, health_change: float, server=None
    ) -> bool:
        if agent_id not in self.agents:
            return False

        agent = self.agents[agent_id]
        old_health = agent.health
        agent.health = max(0, min(agent.max_health, agent.health + health_change))

        # Trigger immediate death processing if agent dies
        if agent.health <= 0 and old_health > 0 and agent.is_alive:
            agent.is_alive = False
            # If server is provided, schedule immediate death processing
            if server and hasattr(server, "schedule_immediate_death"):
                import asyncio

                asyncio.create_task(server.schedule_immediate_death(agent_id))

        return True

    def get_world_state(self) -> Dict:
        return {
            "agents": [agent.to_dict() for agent in self.agents.values()],
            "map_info": {
                "width": self.world_map.width,
                "height": self.world_map.height,
            },
            "timestamp": time.time(),
        }

    def get_terrain_in_vision(self, agent_id: str) -> Dict[Tuple[int, int], TileType]:
        """Get terrain information visible to an agent"""
        if agent_id not in self.agents:
            return {}

        agent = self.agents[agent_id]
        terrain_data = {}

        # Get tiles within vision range
        vision_range = int(agent.vision_range) + 1
        center_x, center_y = int(agent.x), int(agent.y)

        for y in range(
            max(0, center_y - vision_range),
            min(self.world_map.height, center_y + vision_range + 1),
        ):
            for x in range(
                max(0, center_x - vision_range),
                min(self.world_map.width, center_x + vision_range + 1),
            ):
                # Calculate distance from agent
                distance = ((x - agent.x) ** 2 + (y - agent.y) ** 2) ** 0.5

                if distance <= agent.vision_range:
                    tile_type = self.world_map.get_tile(x, y)
                    if tile_type is not None:
                        terrain_data[(x, y)] = tile_type

        return terrain_data

    def validate_position(self, x: float, y: float) -> bool:
        # Check both boundary and walkability
        if not self.collision_detector.is_position_valid(x, y):
            return False

        # Use int() to determine which tile the position actually occupies
        tile_x = int(x)
        tile_y = int(y)
        return self.world_map.is_walkable(tile_x, tile_y)

    def validate_movement_path(
        self, start_pos: Tuple[float, float], end_pos: Tuple[float, float]
    ) -> bool:
        """Validate that a movement path doesn't cross unwalkable terrain"""
        start_x, start_y = start_pos
        end_x, end_y = end_pos

        # Simple line-of-movement check
        distance = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5

        # Very short movements: check if the actual end position (not rounded) is valid
        if distance < 0.5:
            # For sub-tile movements, check both start and end tiles are walkable
            start_tile_x, start_tile_y = int(start_x), int(start_y)
            end_tile_x, end_tile_y = int(end_x), int(end_y)

            # If both positions are in the same walkable tile, allow movement
            if (start_tile_x == end_tile_x and start_tile_y == end_tile_y):
                return self.world_map.is_walkable(start_tile_x, start_tile_y)

            # If crossing tile boundary, both tiles must be walkable
            return (self.world_map.is_walkable(start_tile_x, start_tile_y) and
                    self.world_map.is_walkable(end_tile_x, end_tile_y))

        # For medium distances, check tile boundaries more carefully
        if distance < 2.0:
            # Use int() instead of round() to check actual tile occupancy
            end_tile_x, end_tile_y = int(end_x), int(end_y)
            return self.world_map.is_walkable(end_tile_x, end_tile_y)

        # For longer movements, check intermediate points but with tolerance
        steps = max(2, int(distance * 0.5))  # Reduced sampling density
        unwalkable_count = 0
        total_checks = 0

        for i in range(1, steps + 1):
            t = i / steps
            check_x = start_x + (end_x - start_x) * t
            check_y = start_y + (end_y - start_y) * t
            total_checks += 1

            # Use int() instead of round() for consistency with tile boundaries
            if not self.world_map.is_walkable(int(check_x), int(check_y)):
                unwalkable_count += 1

        # Allow movement if less than 30% of path is unwalkable (more tolerant)
        if total_checks > 0:
            unwalkable_ratio = unwalkable_count / total_checks
            return unwalkable_ratio < 0.3

        return True

    def find_nearest_walkable_position(
        self, x: float, y: float, max_radius: int = 3, preferred_direction: Optional[Tuple[float, float]] = None
    ) -> Tuple[float, float]:
        """
        Find the nearest walkable position to the given coordinates.
        If preferred_direction is provided, prefer positions in that direction.
        """
        # Use int() to determine which tile the position occupies
        start_x, start_y = int(x), int(y)

        # Check the current position first (with floating point precision)
        if self.world_map.is_walkable(start_x, start_y):
            return x, y

        # Collect all possible walkable positions within radius
        candidates = []

        # Search in expanding circles
        for radius in range(1, max_radius + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    # Only check the edge of the current radius for efficiency
                    if abs(dx) == radius or abs(dy) == radius:
                        check_x = start_x + dx
                        check_y = start_y + dy

                        if (
                            0 <= check_x < self.world_map.width
                            and 0 <= check_y < self.world_map.height
                            and self.world_map.is_walkable(check_x, check_y)
                        ):
                            # Calculate distance from original position
                            distance = ((check_x - x) ** 2 + (check_y - y) ** 2) ** 0.5

                            # Calculate preference score if direction provided
                            preference_score = 0
                            if preferred_direction:
                                dir_x, dir_y = preferred_direction
                                # Dot product to measure alignment with preferred direction
                                alignment = (check_x - x) * dir_x + (check_y - y) * dir_y
                                preference_score = max(0, alignment)  # Positive alignment is preferred

                            candidates.append((check_x, check_y, distance, preference_score))

            # If we found candidates at this radius, pick the best one
            if candidates:
                # Sort by preference score (descending), then by distance (ascending)
                candidates.sort(key=lambda c: (-c[3], c[2]))
                best_x, best_y, _, _ = candidates[0]

                # Return position with sub-tile precision preserved
                offset_x = x - start_x
                offset_y = y - start_y
                return float(best_x) + offset_x, float(best_y) + offset_y

        # If no walkable position found, return original
        return x, y

    def get_movement_cost_penalty(self, x: float, y: float) -> float:
        """Get movement speed multiplier based on terrain"""
        tile_x, tile_y = round(x), round(y)

        if not (
            0 <= tile_x < self.world_map.width and 0 <= tile_y < self.world_map.height
        ):
            return 0.5  # Out of bounds penalty

        movement_cost = self.world_map.get_movement_cost(tile_x, tile_y)

        # Convert movement cost to speed multiplier
        if movement_cost == float("inf"):
            return 0.0  # Completely blocked
        elif movement_cost > 2.0:
            return 0.3  # Very slow (sand, difficult terrain)
        elif movement_cost > 1.5:
            return 0.6  # Slow
        elif movement_cost > 1.1:
            return 0.8  # Slightly slow
        else:
            return 1.0  # Normal speed

    def get_world_bounds(self) -> Tuple[int, int]:
        """Get world dimensions"""
        return self.world_map.width, self.world_map.height
