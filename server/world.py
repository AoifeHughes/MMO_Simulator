from typing import Dict, List, Tuple, Optional
from world.map import WorldMap
from world.vision import VisionSystem
from shared.messages import AgentData
from shared.constants import DEFAULT_VISION_RANGE, DEFAULT_VISION_ANGLE
import uuid
import time

class ServerWorld:
    def __init__(self, width: int, height: int):
        self.world_map = WorldMap(width, height)
        self.vision_system = VisionSystem(self.world_map)
        self.agents: Dict[str, AgentData] = {}
        self.last_update = time.time()

    def spawn_agent(self, agent_type: str, x: Optional[float] = None,
                   y: Optional[float] = None) -> str:
        agent_id = str(uuid.uuid4())

        if x is None or y is None:
            spawn_x, spawn_y = self.world_map.get_random_walkable_position()
            x = float(spawn_x)
            y = float(spawn_y)

        agent = AgentData(
            id=agent_id,
            x=x,
            y=y,
            rotation=0.0,
            agent_type=agent_type,
            health=100.0
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

        tile_x = int(new_x)
        tile_y = int(new_y)

        if not self.world_map.is_walkable(tile_x, tile_y):
            return False

        agent = self.agents[agent_id]
        agent.x = new_x
        agent.y = new_y
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

    def validate_position(self, x: float, y: float) -> bool:
        tile_x = int(x)
        tile_y = int(y)
        return self.world_map.is_walkable(tile_x, tile_y)