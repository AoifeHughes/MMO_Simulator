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
    PARTY_INVITE = "party_invite"         # Invite to party

    # World Interaction
    INTERACT_OBJECT = "interact_object"   # Use environmental object
    PICK_UP_ITEM = "pick_up_item"         # Collect item from ground

    # Inventory Actions
    QUERY_INVENTORY = "query_inventory"   # Get inventory state
    EQUIP_ITEM = "equip_item"            # Equip item from inventory
    UNEQUIP_ITEM = "unequip_item"        # Unequip item to inventory
    DROP_ITEM = "drop_item"              # Drop item from inventory

    # Special Actions
    FISH = "fish"                        # Use fishing rod at water
    HARVEST_WOOD = "harvest_wood"        # Harvest wood from forest tiles
    CRAFT_ITEM = "craft_item"           # Craft an item using recipe

    # Trading Actions
    TRADE_REQUEST = "trade_request"      # Request a trade with another agent
    TRADE_ACCEPT = "trade_accept"       # Accept a trade offer
    TRADE_DECLINE = "trade_decline"     # Decline a trade offer
    ADVERTISE_TRADE = "advertise_trade"  # Advertise items for trade publicly
    SEARCH_TRADES = "search_trades"      # Search for available trade advertisements
    NEGOTIATE_TRADE = "negotiate_trade"  # Counter-offer in trade negotiation
    CANCEL_TRADE_AD = "cancel_trade_ad"  # Cancel a trade advertisement

    # Exploration Actions
    EXPLORATION_REPORT = "exploration_report"  # Report exploration progress

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

    def __hash__(self) -> int:
        """Make ActionRequest hashable based on action_id"""
        return hash(self.action_id)

    def __eq__(self, other) -> bool:
        """Equality based on action_id"""
        if not isinstance(other, ActionRequest):
            return False
        return self.action_id == other.action_id


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


def harvest_wood_params(x: float, y: float) -> Dict[str, Any]:
    """Parameters for HARVEST_WOOD action"""
    return {
        "target_x": x,
        "target_y": y,
    }


def craft_item_params(recipe_name: str, x: float = 0.0, y: float = 0.0) -> Dict[str, Any]:
    """Parameters for CRAFT_ITEM action"""
    return {
        "recipe_name": recipe_name,
        "target_x": x,
        "target_y": y,
    }


def trade_request_params(target_agent_id: str, offering_items: List[Dict], requesting_items: List[Dict]) -> Dict[str, Any]:
    """Parameters for TRADE_REQUEST action"""
    return {
        "target_agent_id": target_agent_id,
        "offering_items": offering_items,
        "requesting_items": requesting_items,
    }


def trade_accept_params(trade_id: str) -> Dict[str, Any]:
    """Parameters for TRADE_ACCEPT action"""
    return {
        "trade_id": trade_id,
    }


def trade_decline_params(trade_id: str) -> Dict[str, Any]:
    """Parameters for TRADE_DECLINE action"""
    return {
        "trade_id": trade_id,
    }


def advertise_trade_params(offering_items: List[Dict], requesting_items: List[Dict],
                          duration: float = 300.0, max_distance: float = 50.0) -> Dict[str, Any]:
    """Parameters for ADVERTISE_TRADE action"""
    return {
        "offering_items": offering_items,
        "requesting_items": requesting_items,
        "duration": duration,
        "max_distance": max_distance,
    }


def search_trades_params(desired_items: Optional[List[Dict]] = None,
                        available_items: Optional[List[Dict]] = None,
                        max_distance: float = 50.0) -> Dict[str, Any]:
    """Parameters for SEARCH_TRADES action"""
    return {
        "desired_items": desired_items or [],
        "available_items": available_items or [],
        "max_distance": max_distance,
    }


def negotiate_trade_params(trade_id: str, counter_offer: Dict[str, Any]) -> Dict[str, Any]:
    """Parameters for NEGOTIATE_TRADE action"""
    return {
        "trade_id": trade_id,
        "counter_offer": counter_offer,
    }


def cancel_trade_ad_params(ad_id: str) -> Dict[str, Any]:
    """Parameters for CANCEL_TRADE_AD action"""
    return {
        "ad_id": ad_id,
    }


# Action creation helpers
def create_harvest_wood_action(x: float = 0.0, y: float = 0.0) -> ActionRequest:
    """Create a harvest wood action"""
    return ActionRequest(
        action_type=ActionType.HARVEST_WOOD,
        parameters={"target_x": x, "target_y": y}
    )


def create_craft_item_action(recipe_name: str, x: float = 0.0, y: float = 0.0) -> ActionRequest:
    """Create a craft item action"""
    return ActionRequest(
        action_type=ActionType.CRAFT_ITEM,
        parameters=craft_item_params(recipe_name, x, y)
    )


def create_trade_request_action(target_agent_id: str, offering_items: List[Dict], requesting_items: List[Dict]) -> ActionRequest:
    """Create a trade request action"""
    return ActionRequest(
        action_type=ActionType.TRADE_REQUEST,
        parameters=trade_request_params(target_agent_id, offering_items, requesting_items)
    )


def create_trade_accept_action(trade_id: str) -> ActionRequest:
    """Create a trade accept action"""
    return ActionRequest(
        action_type=ActionType.TRADE_ACCEPT,
        parameters=trade_accept_params(trade_id)
    )


def create_trade_decline_action(trade_id: str) -> ActionRequest:
    """Create a trade decline action"""
    return ActionRequest(
        action_type=ActionType.TRADE_DECLINE,
        parameters=trade_decline_params(trade_id)
    )


def create_advertise_trade_action(offering_items: List[Dict], requesting_items: List[Dict],
                                 duration: float = 300.0, max_distance: float = 50.0) -> ActionRequest:
    """Create a trade advertisement action"""
    return ActionRequest(
        action_type=ActionType.ADVERTISE_TRADE,
        parameters=advertise_trade_params(offering_items, requesting_items, duration, max_distance)
    )


def create_search_trades_action(desired_items: Optional[List[Dict]] = None,
                               available_items: Optional[List[Dict]] = None,
                               max_distance: float = 50.0) -> ActionRequest:
    """Create a search trades action"""
    return ActionRequest(
        action_type=ActionType.SEARCH_TRADES,
        parameters=search_trades_params(desired_items, available_items, max_distance)
    )


def create_negotiate_trade_action(trade_id: str, counter_offer: Dict[str, Any]) -> ActionRequest:
    """Create a trade negotiation action"""
    return ActionRequest(
        action_type=ActionType.NEGOTIATE_TRADE,
        parameters=negotiate_trade_params(trade_id, counter_offer)
    )


def create_cancel_trade_ad_action(ad_id: str) -> ActionRequest:
    """Create a cancel trade advertisement action"""
    return ActionRequest(
        action_type=ActionType.CANCEL_TRADE_AD,
        parameters=cancel_trade_ad_params(ad_id)
    )