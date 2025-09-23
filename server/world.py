from typing import Dict, List, Tuple, Optional
from world.map import WorldMap
from world.vision import VisionSystem
from world.tiles import TileType
from shared.messages import AgentData
from shared.constants import DEFAULT_VISION_RANGE, DEFAULT_VISION_ANGLE
from shared.collision import CollisionDetector
import uuid
import time

class ServerWorld:
    def __init__(self, width: int, height: int):
        self.world_map = WorldMap(width, height)
        self.vision_system = VisionSystem(self.world_map)
        self.collision_detector = CollisionDetector(width, height)
        self.agents: Dict[str, AgentData] = {}
        self.last_update = time.time()

    def spawn_agent(self, agent_type: str, x: Optional[float] = None,
                   y: Optional[float] = None) -> str:
        agent_id = str(uuid.uuid4())

        if x is None or y is None:
            # Get positions of existing agents for collision avoidance
            existing_positions = [(agent.x, agent.y) for agent in self.agents.values()]
            x, y = self.collision_detector.get_safe_spawn_position(existing_positions)
        else:
            # Ensure provided position is within bounds
            x, y = self.collision_detector.clamp_to_bounds(x, y)

        agent = AgentData(
            id=agent_id,
            x=x,
            y=y,
            rotation=0.0,
            agent_type=agent_type,
            health=100.0,
            vision_range=DEFAULT_VISION_RANGE
        )

        self.agents[agent_id] = agent
        return agent_id

    def despawn_agent(self, agent_id: str) -> bool:
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False

    def move_agent(self, agent_id: str, new_x: float, new_y: float,
                  rotation: float) -> bool:
        if agent_id not in self.agents:
            return False

        agent = self.agents[agent_id]
        current_pos = (agent.x, agent.y)
        intended_pos = (new_x, new_y)

        # Get positions of other agents for collision checking
        other_agents = [(a.x, a.y) for aid, a in self.agents.items() if aid != agent_id]

        # Resolve collisions and get safe position
        safe_x, safe_y = self.collision_detector.resolve_movement_collision(
            current_pos, intended_pos, other_agents
        )

        # Additional check for tile walkability
        tile_x = int(safe_x)
        tile_y = int(safe_y)

        if not self.world_map.is_walkable(tile_x, tile_y):
            # If the resolved position is not walkable, keep current position
            return False

        # Update agent position
        agent.x = safe_x
        agent.y = safe_y
        agent.rotation = rotation

        return True

    def get_visible_agents(self, agent_id: str, vision_range: float = DEFAULT_VISION_RANGE,
                          vision_angle: float = DEFAULT_VISION_ANGLE) -> List[AgentData]:
        if agent_id not in self.agents:
            return []

        observer = self.agents[agent_id]
        origin = (observer.x, observer.y)

        entities = [(aid, (a.x, a.y)) for aid, a in self.agents.items()
                   if aid != agent_id]

        visible_ids = self.vision_system.get_entities_in_vision(
            origin, observer.rotation, vision_angle, vision_range, entities
        )

        return [self.agents[aid] for aid in visible_ids if aid in self.agents]

    def get_agent(self, agent_id: str) -> Optional[AgentData]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> List[AgentData]:
        return list(self.agents.values())

    def update_agent_health(self, agent_id: str, health_change: float) -> bool:
        if agent_id not in self.agents:
            return False

        agent = self.agents[agent_id]
        agent.health = max(0, min(100, agent.health + health_change))

        if agent.health <= 0:
            self.despawn_agent(agent_id)

        return True

    def get_world_state(self) -> Dict:
        return {
            'agents': [agent.to_dict() for agent in self.agents.values()],
            'map_info': {
                'width': self.world_map.width,
                'height': self.world_map.height
            },
            'timestamp': time.time()
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

        for y in range(max(0, center_y - vision_range),
                      min(self.world_map.height, center_y + vision_range + 1)):
            for x in range(max(0, center_x - vision_range),
                          min(self.world_map.width, center_x + vision_range + 1)):

                # Calculate distance from agent
                distance = ((x - agent.x)**2 + (y - agent.y)**2)**0.5

                if distance <= agent.vision_range:
                    tile_type = self.world_map.get_tile(x, y)
                    if tile_type is not None:
                        terrain_data[(x, y)] = tile_type

        return terrain_data

    def validate_position(self, x: float, y: float) -> bool:
        # Check both boundary and walkability
        if not self.collision_detector.is_position_valid(x, y):
            return False

        tile_x = int(x)
        tile_y = int(y)
        return self.world_map.is_walkable(tile_x, tile_y)

    def get_world_bounds(self) -> Tuple[int, int]:
        """Get world dimensions"""
        return self.world_map.width, self.world_map.height