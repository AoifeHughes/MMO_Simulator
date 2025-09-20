"""
Shared message definitions for client-server communication
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
import json
import time


class MessageType(Enum):
    """Types of messages in the protocol"""
    # Client -> Server
    CONNECT = "CONNECT"
    DISCONNECT = "DISCONNECT"
    ACTION = "ACTION"
    QUERY = "QUERY"
    HEARTBEAT = "HEARTBEAT"

    # Server -> Client
    WELCOME = "WELCOME"
    WORLD_UPDATE = "WORLD_UPDATE"
    ACTION_RESULT = "ACTION_RESULT"
    QUERY_RESULT = "QUERY_RESULT"
    EVENT = "EVENT"
    ERROR = "ERROR"
    PING = "PING"


class ActionType(Enum):
    """Types of actions clients can perform"""
    MOVE = "MOVE"
    ATTACK = "ATTACK"
    INTERACT = "INTERACT"
    USE_ABILITY = "USE_ABILITY"
    USE_ITEM = "USE_ITEM"
    PICKUP = "PICKUP"
    DROP = "DROP"
    TRADE = "TRADE"
    CHAT = "CHAT"


class QueryType(Enum):
    """Types of queries clients can make"""
    GET_STATS = "GET_STATS"
    GET_INVENTORY = "GET_INVENTORY"
    GET_SURROUNDINGS = "GET_SURROUNDINGS"
    GET_ENTITY_INFO = "GET_ENTITY_INFO"
    GET_MAP_INFO = "GET_MAP_INFO"


class EventType(Enum):
    """Types of events broadcast to clients"""
    ENTITY_SPAWNED = "ENTITY_SPAWNED"
    ENTITY_DESPAWNED = "ENTITY_DESPAWNED"
    ENTITY_MOVED = "ENTITY_MOVED"
    COMBAT = "COMBAT"
    CHAT = "CHAT"
    LEVEL_UP = "LEVEL_UP"
    DEATH = "DEATH"
    ITEM_DROPPED = "ITEM_DROPPED"
    ZONE_CHANGE = "ZONE_CHANGE"


@dataclass
class Message:
    """Base message class"""
    type: MessageType
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0

    def to_json(self) -> str:
        """Convert message to JSON string"""
        data = asdict(self)
        data['type'] = self.type.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """Create message from JSON string"""
        data = json.loads(json_str)
        data['type'] = MessageType(data['type'])
        return cls(**data)


@dataclass
class ConnectMessage(Message):
    """Client connection request"""
    type: MessageType = MessageType.CONNECT
    agent_name: str = ""
    agent_class: str = "Adventurer"
    version: str = "1.0.0"


@dataclass
class WelcomeMessage(Message):
    """Server welcome response"""
    type: MessageType = MessageType.WELCOME
    agent_id: str = ""
    server_version: str = "1.0.0"
    world_info: Dict[str, Any] = field(default_factory=dict)
    initial_position: Tuple[float, float] = (0, 0)
    vision_range: float = 100.0


@dataclass
class ActionMessage(Message):
    """Client action request"""
    type: MessageType = MessageType.ACTION
    action: ActionType = ActionType.MOVE
    data: Dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""


@dataclass
class ActionResultMessage(Message):
    """Server action response"""
    type: MessageType = MessageType.ACTION_RESULT
    action: ActionType = ActionType.MOVE
    success: bool = False
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class QueryMessage(Message):
    """Client query request"""
    type: MessageType = MessageType.QUERY
    query: QueryType = QueryType.GET_SURROUNDINGS
    params: Dict[str, Any] = field(default_factory=dict)
    agent_id: str = ""


@dataclass
class QueryResultMessage(Message):
    """Server query response"""
    type: MessageType = MessageType.QUERY_RESULT
    query: QueryType = QueryType.GET_SURROUNDINGS
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorldUpdateMessage(Message):
    """Server world state update"""
    type: MessageType = MessageType.WORLD_UPDATE
    tick: int = 0
    visible_entities: List[Dict[str, Any]] = field(default_factory=list)
    removed_entities: List[str] = field(default_factory=list)
    terrain_updates: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class EventMessage(Message):
    """Server event broadcast"""
    type: MessageType = MessageType.EVENT
    event: EventType = EventType.ENTITY_MOVED
    data: Dict[str, Any] = field(default_factory=dict)
    position: Optional[Tuple[float, float]] = None


@dataclass
class EntityView:
    """Limited view of an entity for clients"""
    id: str
    name: str
    entity_type: str  # 'agent', 'npc', 'enemy', 'object'
    position: Tuple[float, float]
    health_percentage: float  # 0-100, not exact values
    level: int
    state: str  # 'idle', 'moving', 'combat', etc.
    velocity: Optional[Tuple[float, float]] = None
    equipment_visible: Optional[Dict[str, str]] = None  # Visible equipment only

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class TerrainView:
    """View of terrain for clients"""
    position: Tuple[float, float]
    size: Tuple[float, float]
    terrain_type: str
    walkable: bool
    hazard: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Protocol:
    """Protocol utilities"""

    DELIMITER = b'\n'
    MAX_MESSAGE_SIZE = 65536  # 64KB max message size

    @staticmethod
    def encode_message(message: Message) -> bytes:
        """Encode message for transmission"""
        # Convert message to dictionary with enum serialization
        data = asdict(message)

        # Convert enums to strings
        if 'type' in data and hasattr(data['type'], 'value'):
            data['type'] = data['type'].value
        if 'action' in data and hasattr(data['action'], 'value'):
            data['action'] = data['action'].value
        if 'query' in data and hasattr(data['query'], 'value'):
            data['query'] = data['query'].value
        if 'event' in data and hasattr(data['event'], 'value'):
            data['event'] = data['event'].value

        json_str = json.dumps(data)
        return json_str.encode('utf-8') + Protocol.DELIMITER

    @staticmethod
    def decode_message(data: bytes) -> Optional[Message]:
        """Decode received message"""
        try:
            json_str = data.decode('utf-8').strip()
            if not json_str:
                return None

            parsed = json.loads(json_str)
            msg_type = MessageType(parsed['type'])

            # Route to appropriate message class
            message_classes = {
                MessageType.CONNECT: ConnectMessage,
                MessageType.WELCOME: WelcomeMessage,
                MessageType.ACTION: ActionMessage,
                MessageType.ACTION_RESULT: ActionResultMessage,
                MessageType.QUERY: QueryMessage,
                MessageType.QUERY_RESULT: QueryResultMessage,
                MessageType.WORLD_UPDATE: WorldUpdateMessage,
                MessageType.EVENT: EventMessage,
                MessageType.HEARTBEAT: HeartbeatMessage,
            }

            msg_class = message_classes.get(msg_type, Message)

            # Handle enum conversions
            if 'action' in parsed and isinstance(parsed['action'], str):
                parsed['action'] = ActionType(parsed['action'])
            if 'query' in parsed and isinstance(parsed['query'], str):
                parsed['query'] = QueryType(parsed['query'])
            if 'event' in parsed and isinstance(parsed['event'], str):
                parsed['event'] = EventType(parsed['event'])

            parsed['type'] = msg_type
            return msg_class(**parsed)

        except Exception as e:
            print(f"Error decoding message: {e}")
            return None


@dataclass
class HeartbeatMessage(Message):
    """Client heartbeat message"""
    type: MessageType = MessageType.HEARTBEAT
    agent_id: Optional[str] = None


@dataclass
class ErrorMessage(Message):
    """Error message"""
    type: MessageType = MessageType.ERROR
    error: str = ""


@dataclass
class ClientInfo:
    """Server-side client information"""
    id: str
    name: str
    agent_class: str
    connection_time: float
    last_heartbeat: float
    position: Tuple[float, float]
    vision_range: float
    rate_limit_tokens: int = 10
    last_action_time: float = 0