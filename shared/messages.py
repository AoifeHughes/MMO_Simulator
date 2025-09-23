import json
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict

class MessageType(Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    SPAWN_AGENT = "spawn_agent"
    DESPAWN_AGENT = "despawn_agent"
    MOVE_COMMAND = "move_command"
    WORLD_STATE_UPDATE = "world_state_update"
    VISIBLE_ENTITIES_UPDATE = "visible_entities_update"
    AGENT_ACTION = "agent_action"
    PING = "ping"
    PONG = "pong"
    ERROR = "error"

@dataclass
class Message:
    type: MessageType
    payload: Dict[str, Any]
    timestamp: float

    def to_json(self) -> str:
        return json.dumps({
            'type': self.type.value,
            'payload': self.payload,
            'timestamp': self.timestamp
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        data = json.loads(json_str)
        return cls(
            type=MessageType(data['type']),
            payload=data['payload'],
            timestamp=data['timestamp']
        )

@dataclass
class AgentData:
    id: str
    x: float
    y: float
    rotation: float
    agent_type: str
    health: float = 100.0

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class WorldState:
    agents: List[AgentData]
    timestamp: float

    def to_dict(self) -> Dict:
        return {
            'agents': [agent.to_dict() for agent in self.agents],
            'timestamp': self.timestamp
        }