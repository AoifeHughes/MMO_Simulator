"""
Simplified Message System

This reduces the complex message system to core essentials while preserving
client-side decision making capabilities.

Key simplifications:
- Reduced from 14+ message types to 6 core types
- Single TCP protocol (no UDP complexity)
- Clear request-response patterns
- Eliminated complex position sync messages
"""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SimpleMessageType(Enum):
    """Simplified core message types"""

    # Connection management
    CONNECT = "connect"
    DISCONNECT = "disconnect"

    # World state
    WORLD_UPDATE = "world_update"  # Periodic world state from server

    # Actions
    ACTION_REQUEST = "action_request"  # Client requests action
    ACTION_RESPONSE = "action_response"  # Server responds to action

    # Events
    GAME_EVENT = "game_event"  # Deaths, respawns, damage, etc.


@dataclass
class SimpleMessage:
    """Simplified message structure"""

    type: SimpleMessageType
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0  # For ordering if needed

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type.value,
                "payload": self.payload,
                "timestamp": self.timestamp,
                "sequence": self.sequence,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SimpleMessage":
        data = json.loads(json_str)
        return cls(
            type=SimpleMessageType(data["type"]),
            payload=data["payload"],
            timestamp=data.get("timestamp", time.time()),
            sequence=data.get("sequence", 0),
        )


# Message creation helpers
def create_connect_message(agent_type: str) -> SimpleMessage:
    """Create connection request"""
    return SimpleMessage(
        type=SimpleMessageType.CONNECT, payload={"agent_type": agent_type}
    )


def create_disconnect_message() -> SimpleMessage:
    """Create disconnect message"""
    return SimpleMessage(type=SimpleMessageType.DISCONNECT, payload={})


def create_world_update_message(agents: List[Dict], world_info: Dict) -> SimpleMessage:
    """Create world state update from server"""
    return SimpleMessage(
        type=SimpleMessageType.WORLD_UPDATE,
        payload={
            "agents": agents,
            "world_info": world_info,
            "server_time": time.time(),
        },
    )


def create_action_request_message(
    action_type: str, parameters: Dict[str, Any], agent_id: str, request_id: str = None
) -> SimpleMessage:
    """Create action request from client"""
    if request_id is None:
        request_id = str(int(time.time() * 1000) % 100000)  # Simple ID

    return SimpleMessage(
        type=SimpleMessageType.ACTION_REQUEST,
        payload={
            "action_type": action_type,
            "parameters": parameters,
            "agent_id": agent_id,
            "request_id": request_id,
        },
    )


def create_action_response_message(
    request_id: str, success: bool, message: str, result_data: Dict = None
) -> SimpleMessage:
    """Create action response from server"""
    payload = {"request_id": request_id, "success": success, "message": message}
    if result_data:
        payload["result"] = result_data

    return SimpleMessage(type=SimpleMessageType.ACTION_RESPONSE, payload=payload)


def create_game_event_message(
    event_type: str, event_data: Dict[str, Any]
) -> SimpleMessage:
    """Create game event message"""
    return SimpleMessage(
        type=SimpleMessageType.GAME_EVENT,
        payload={"event_type": event_type, "data": event_data},
    )


# Common action types (simplified)
class SimpleActionType:
    """Simplified action types for client requests"""

    MOVE_TO = "move_to"
    ATTACK = "attack"
    FISH = "fish"
    HARVEST_WOOD = "harvest_wood"
    USE_ITEM = "use_item"
    CRAFT_ITEM = "craft_item"
    STOP = "stop"


# Common event types
class SimpleEventType:
    """Simplified event types for server notifications"""

    AGENT_DEATH = "agent_death"
    AGENT_RESPAWN = "agent_respawn"
    DAMAGE_DEALT = "damage_dealt"
    ITEM_PICKED_UP = "item_picked_up"
    CRAFT_COMPLETED = "craft_completed"
