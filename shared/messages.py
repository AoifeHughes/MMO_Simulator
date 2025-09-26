import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class MessageType(Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SPAWN_AGENT = "spawn_agent"
    DESPAWN_AGENT = "despawn_agent"
    MOVE_COMMAND = "move_command"
    WORLD_STATE_UPDATE = "world_state_update"
    VISIBLE_ENTITIES_UPDATE = "visible_entities_update"
    AGENT_ACTION = "agent_action"
    DAMAGE_DEALT = "damage_dealt"
    AGENT_DEATH = "agent_death"
    AGENT_RESPAWN = "agent_respawn"
    GAME_DATA_UPDATE = "game_data_update"  # Send game mechanics data to client
    ACTION_REQUEST = "action_request"     # Client requests single action from server
    ACTION_RESPONSE = "action_response"   # Server responds to single action request
    ACTION_BATCH = "action_batch"         # Client requests multiple actions (batch)
    ACTION_BATCH_RESPONSE = "action_batch_response"  # Server responds to batch
    POSITION_SYNC = "position_sync"           # Server broadcasts authoritative positions
    POSITION_UPDATE = "position_update"       # Client reports movement to server
    POSITION_QUERY = "position_query"         # Client requests fresh position from server
    POSITION_RESPONSE = "position_response"   # Server responds with fresh position data
    ENVIRONMENT_QUERY = "environment_query"   # Client requests environment scan from server
    ENVIRONMENT_RESPONSE = "environment_response"  # Server responds with environment data
    PING = "ping"
    PONG = "pong"
    ERROR = "error"


@dataclass
class Message:
    type: MessageType
    payload: Dict[str, Any]
    timestamp: float

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type.value,
                "payload": self.payload,
                "timestamp": self.timestamp,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        data = json.loads(json_str)
        return cls(
            type=MessageType(data["type"]),
            payload=data["payload"],
            timestamp=data["timestamp"],
        )


@dataclass
class AgentData:
    id: str
    x: float
    y: float
    rotation: float
    agent_type: str
    health: float = 100.0
    max_health: float = 100.0
    vision_range: float = 10.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    is_alive: bool = True
    last_damage_time: float = 0.0
    respawn_time: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class WorldState:
    agents: List[AgentData]
    timestamp: float

    def to_dict(self) -> Dict:
        return {
            "agents": [agent.to_dict() for agent in self.agents],
            "timestamp": self.timestamp,
        }
