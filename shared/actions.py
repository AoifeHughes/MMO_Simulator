"""
Unified Action System for Client-Server Communication

This module defines the core action framework that enables:
- Unified request-response pattern for all client actions
- Server-authoritative validation with client prediction
- Scalable action type system
- Rollback support for network issues
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ActionType(Enum):
    """All possible action types in the game"""
    # Movement Actions
    MOVE_TO = "move_to"                    # Move to absolute position
    MOVE_DIRECTION = "move_direction"      # Move in direction for duration
    STOP_MOVEMENT = "stop_movement"        # Halt current movement
    TELEPORT = "teleport"                  # Instant position change

    # Combat Actions
    ATTACK_TARGET = "attack_target"        # Attack specific target
    CAST_SPELL = "cast_spell"             # Cast spell with targeting
    USE_ITEM = "use_item"                 # Consume item for effect
    BLOCK = "block"                       # Defensive action

    # Social Actions
    CHAT_MESSAGE = "chat_message"         # Send chat message
    TRADE_REQUEST = "trade_request"       # Initiate trade
    PARTY_INVITE = "party_invite"         # Invite to party

    # World Interaction
    INTERACT_OBJECT = "interact_object"   # Use environmental object
    PICK_UP_ITEM = "pick_up_item"         # Collect item from ground
    CRAFT_ITEM = "craft_item"             # Create item from resources

    # Inventory Actions
    QUERY_INVENTORY = "query_inventory"   # Get inventory state
    EQUIP_ITEM = "equip_item"            # Equip item from inventory
    UNEQUIP_ITEM = "unequip_item"        # Unequip item to inventory
    DROP_ITEM = "drop_item"              # Drop item from inventory

    # Special Actions
    FISH = "fish"                        # Use fishing rod at water

    # System Actions
    PING = "ping"                         # Network latency test
    HEARTBEAT = "heartbeat"               # Keep connection alive


class ActionResult(Enum):
    """Result of server action validation"""
    APPROVED = "approved"      # Action approved as requested
    REJECTED = "rejected"      # Action rejected, no changes made
    MODIFIED = "modified"      # Action approved but modified by server
    PENDING = "pending"        # Action queued for processing
    ERROR = "error"           # Server error processing action


class ActionPriority(Enum):
    """Action priority for server processing"""
    CRITICAL = 0    # Emergency actions (death, respawn)
    HIGH = 1       # Combat actions
    NORMAL = 2     # Movement, interactions
    LOW = 3        # Chat, social actions
    BACKGROUND = 4 # Analytics, logging


@dataclass
class ActionRequest:
    """Client request for server to validate and execute an action"""

    # Core identification
    action_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = ""
    action_type: ActionType = ActionType.PING

    # Action data
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Timing and prediction
    client_timestamp: float = field(default_factory=time.time)
    client_sequence: int = 0  # For ordering actions

    # Server processing hints
    priority: ActionPriority = ActionPriority.NORMAL
    timeout_seconds: float = 5.0
    retry_count: int = 0
    max_retries: int = 3

    # Client prediction data
    predicted_result: Optional[Dict[str, Any]] = None
    rollback_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "action_type": self.action_type.value,
            "parameters": self.parameters,
            "client_timestamp": self.client_timestamp,
            "client_sequence": self.client_sequence,
            "priority": self.priority.value,
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "predicted_result": self.predicted_result,
            "rollback_data": self.rollback_data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRequest":
        """Create from dictionary (JSON deserialization)"""
        return cls(
            action_id=data.get("action_id", str(uuid.uuid4())[:8]),
            agent_id=data.get("agent_id", ""),
            action_type=ActionType(data.get("action_type", "ping")),
            parameters=data.get("parameters", {}),
            client_timestamp=data.get("client_timestamp", time.time()),
            client_sequence=data.get("client_sequence", 0),
            priority=ActionPriority(data.get("priority", 2)),
            timeout_seconds=data.get("timeout_seconds", 5.0),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            predicted_result=data.get("predicted_result"),
            rollback_data=data.get("rollback_data"),
        )


@dataclass
class ActionResponse:
    """Server response to client action request"""

    # Reference to original request
    action_id: str = ""
    agent_id: str = ""
    action_type: ActionType = ActionType.PING

    # Server result
    result: ActionResult = ActionResult.ERROR
    message: str = ""  # Human-readable result description

    # Timing
    server_timestamp: float = field(default_factory=time.time)
    processing_time_ms: float = 0.0

    # Result data
    approved_parameters: Optional[Dict[str, Any]] = None  # What server actually executed
    side_effects: List[Dict[str, Any]] = field(default_factory=list)  # Additional effects

    # Error details
    error_code: Optional[str] = None
    retry_after_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "action_type": self.action_type.value,
            "result": self.result.value,
            "message": self.message,
            "server_timestamp": self.server_timestamp,
            "processing_time_ms": self.processing_time_ms,
            "approved_parameters": self.approved_parameters,
            "side_effects": self.side_effects,
            "error_code": self.error_code,
            "retry_after_seconds": self.retry_after_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionResponse":
        """Create from dictionary (JSON deserialization)"""
        return cls(
            action_id=data.get("action_id", ""),
            agent_id=data.get("agent_id", ""),
            action_type=ActionType(data.get("action_type", "ping")),
            result=ActionResult(data.get("result", "error")),
            message=data.get("message", ""),
            server_timestamp=data.get("server_timestamp", time.time()),
            processing_time_ms=data.get("processing_time_ms", 0.0),
            approved_parameters=data.get("approved_parameters"),
            side_effects=data.get("side_effects", []),
            error_code=data.get("error_code"),
            retry_after_seconds=data.get("retry_after_seconds"),
        )


@dataclass
class ActionBatch:
    """Multiple actions submitted together for efficiency"""

    batch_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent_id: str = ""
    actions: List[ActionRequest] = field(default_factory=list)
    client_timestamp: float = field(default_factory=time.time)

    # Batch processing options
    atomic: bool = False  # All actions succeed or all fail
    max_parallel: int = 10  # Max actions to process in parallel

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "batch_id": self.batch_id,
            "agent_id": self.agent_id,
            "actions": [action.to_dict() for action in self.actions],
            "client_timestamp": self.client_timestamp,
            "atomic": self.atomic,
            "max_parallel": self.max_parallel,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionBatch":
        """Create from dictionary (JSON deserialization)"""
        return cls(
            batch_id=data.get("batch_id", str(uuid.uuid4())[:8]),
            agent_id=data.get("agent_id", ""),
            actions=[ActionRequest.from_dict(a) for a in data.get("actions", [])],
            client_timestamp=data.get("client_timestamp", time.time()),
            atomic=data.get("atomic", False),
            max_parallel=data.get("max_parallel", 10),
        )


# Commonly used action parameter helpers

def move_to_params(x: float, y: float, speed_multiplier: float = 1.0) -> Dict[str, Any]:
    """Parameters for MOVE_TO action"""
    return {
        "target_x": x,
        "target_y": y,
        "speed_multiplier": speed_multiplier,
    }


def attack_target_params(target_id: str, attack_name: str = "punch") -> Dict[str, Any]:
    """Parameters for ATTACK_TARGET action"""
    return {
        "target_id": target_id,
        "attack_name": attack_name,
    }


def cast_spell_params(spell_name: str, target_x: float = None, target_y: float = None,
                      target_id: str = None) -> Dict[str, Any]:
    """Parameters for CAST_SPELL action"""
    params = {"spell_name": spell_name}
    if target_x is not None and target_y is not None:
        params.update({"target_x": target_x, "target_y": target_y})
    if target_id is not None:
        params["target_id"] = target_id
    return params


def use_item_params(item_id: str, target_id: str = None) -> Dict[str, Any]:
    """Parameters for USE_ITEM action"""
    params = {"item_id": item_id}
    if target_id is not None:
        params["target_id"] = target_id
    return params


def chat_message_params(message: str, channel: str = "general") -> Dict[str, Any]:
    """Parameters for CHAT_MESSAGE action"""
    return {
        "message": message,
        "channel": channel,
    }


def equip_item_params(item_id: str) -> Dict[str, Any]:
    """Parameters for EQUIP_ITEM action"""
    return {
        "item_id": item_id,
    }


def unequip_item_params(slot: str) -> Dict[str, Any]:
    """Parameters for UNEQUIP_ITEM action"""
    return {
        "slot": slot,  # e.g., "main_hand", "off_hand"
    }


def drop_item_params(item_id: str, quantity: int = 1) -> Dict[str, Any]:
    """Parameters for DROP_ITEM action"""
    return {
        "item_id": item_id,
        "quantity": quantity,
    }


def fish_params(x: float = None, y: float = None) -> Dict[str, Any]:
    """Parameters for FISH action"""
    params = {}
    if x is not None and y is not None:
        params.update({"target_x": x, "target_y": y})
    return params