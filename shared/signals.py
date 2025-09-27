"""
Signal System for Agent Communication

This module defines signal types and structures for agent-to-agent communication,
enabling dynamic cooperation, information sharing, and coordinated behavior.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class SignalType(Enum):
    """Types of signals that agents can send to each other"""

    HELP_REQUEST = "help_request"  # Agent needs assistance
    RESOURCE_FOUND = "resource_found"  # Agent discovered resources
    ENEMY_SPOTTED = "enemy_spotted"  # Enemy detected in area
    TRADE_OFFER = "trade_offer"  # Agent wants to trade
    AREA_CLEAR = "area_clear"  # Area is safe/cleared of enemies
    GATHER_HERE = "gather_here"  # Request allies to come to location
    DANGER_WARNING = "danger_warning"  # Warning about dangerous area
    TASK_COMPLETE = "task_complete"  # Task or objective completed
    FOLLOW_ME = "follow_me"  # Request to follow/form group
    RETREAT = "retreat"  # Signal to fall back/retreat


class SignalPriority(Enum):
    """Priority levels for signal processing"""

    LOW = 1  # General information, non-urgent
    NORMAL = 2  # Standard communications
    HIGH = 3  # Important information requiring attention
    URGENT = 4  # Critical situations requiring immediate response
    EMERGENCY = 5  # Life-threatening situations, highest priority


@dataclass
class Signal:
    """Represents a signal sent between agents"""

    signal_id: str
    signal_type: SignalType
    sender_id: str

    # Target specification
    target_agents: Optional[Set[str]] = None  # Specific agents (None = broadcast)
    target_area: Optional[tuple] = None  # Geographic area (x, y, radius)

    # Signal content
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    # Signal properties
    priority: SignalPriority = SignalPriority.NORMAL
    range_limit: float = 50.0  # Maximum transmission range
    duration: float = 30.0  # How long signal remains valid

    # Metadata
    timestamp: float = field(default_factory=time.time)
    sender_position: Optional[tuple] = None  # Position when signal was sent

    def is_expired(self) -> bool:
        """Check if this signal has expired"""
        return (time.time() - self.timestamp) > self.duration

    def is_targeted_to(self, agent_id: str) -> bool:
        """Check if signal is targeted to a specific agent"""
        if self.target_agents is None:
            return True  # Broadcast signal
        return agent_id in self.target_agents

    def is_in_range_of(self, agent_x: float, agent_y: float) -> bool:
        """Check if agent is in range to receive this signal"""
        if not self.sender_position:
            return True  # No position limit

        sender_x, sender_y = self.sender_position
        distance = ((agent_x - sender_x) ** 2 + (agent_y - sender_y) ** 2) ** 0.5
        return distance <= self.range_limit

    def get_distance_from(self, agent_x: float, agent_y: float) -> float:
        """Get distance from agent to signal origin"""
        if not self.sender_position:
            return 0.0

        sender_x, sender_y = self.sender_position
        return ((agent_x - sender_x) ** 2 + (agent_y - sender_y) ** 2) ** 0.5


def create_help_request(
    sender_id: str, sender_pos: tuple, enemy_count: int = 0, help_type: str = "general"
) -> Signal:
    """Create a help request signal"""
    return Signal(
        signal_id=f"help_{sender_id}_{int(time.time())}",
        signal_type=SignalType.HELP_REQUEST,
        sender_id=sender_id,
        message=f"Need assistance: {help_type}",
        data={
            "help_type": help_type,
            "enemy_count": enemy_count,
            "urgency": "high" if enemy_count > 1 else "normal",
        },
        priority=SignalPriority.HIGH if enemy_count > 1 else SignalPriority.NORMAL,
        sender_position=sender_pos,
        range_limit=40.0,
        duration=45.0,
    )


def create_resource_found(
    sender_id: str,
    sender_pos: tuple,
    resource_type: str,
    resource_location: tuple,
    quantity: int = 1,
) -> Signal:
    """Create a resource found signal"""
    return Signal(
        signal_id=f"resource_{sender_id}_{int(time.time())}",
        signal_type=SignalType.RESOURCE_FOUND,
        sender_id=sender_id,
        message=f"Found {resource_type} at location",
        data={
            "resource_type": resource_type,
            "location": resource_location,
            "quantity": quantity,
            "estimated_value": quantity * 2,  # Simple value calculation
        },
        priority=SignalPriority.NORMAL,
        sender_position=sender_pos,
        range_limit=60.0,
        duration=120.0,  # Resources last longer
    )


def create_enemy_spotted(
    sender_id: str,
    sender_pos: tuple,
    enemy_location: tuple,
    enemy_count: int = 1,
    enemy_types: List[str] = None,
) -> Signal:
    """Create an enemy spotted signal"""
    enemy_types = enemy_types or ["unknown"]

    priority = SignalPriority.HIGH if enemy_count > 2 else SignalPriority.NORMAL

    return Signal(
        signal_id=f"enemy_{sender_id}_{int(time.time())}",
        signal_type=SignalType.ENEMY_SPOTTED,
        sender_id=sender_id,
        message=f"Enemy spotted: {enemy_count} enemies",
        data={
            "enemy_location": enemy_location,
            "enemy_count": enemy_count,
            "enemy_types": enemy_types,
            "threat_level": "high" if enemy_count > 2 else "moderate",
        },
        priority=priority,
        sender_position=sender_pos,
        range_limit=80.0,  # Wider range for warnings
        duration=60.0,
    )


def create_trade_offer(
    sender_id: str,
    sender_pos: tuple,
    offering: List[Dict[str, Any]],
    requesting: List[Dict[str, Any]],
    target_agent: Optional[str] = None,
) -> Signal:
    """Create a trade offer signal"""
    target_agents = {target_agent} if target_agent else None

    return Signal(
        signal_id=f"trade_{sender_id}_{int(time.time())}",
        signal_type=SignalType.TRADE_OFFER,
        sender_id=sender_id,
        target_agents=target_agents,
        message="Trade offer available",
        data={
            "offering": offering,
            "requesting": requesting,
            "trade_location": sender_pos,
        },
        priority=SignalPriority.LOW,
        sender_position=sender_pos,
        range_limit=25.0,  # Close range for trading
        duration=90.0,
    )


def create_area_clear(sender_id: str, sender_pos: tuple, cleared_area: tuple) -> Signal:
    """Create an area clear signal"""
    return Signal(
        signal_id=f"clear_{sender_id}_{int(time.time())}",
        signal_type=SignalType.AREA_CLEAR,
        sender_id=sender_id,
        message="Area cleared of threats",
        data={"cleared_area": cleared_area, "safety_level": "high"},  # (x, y, radius)
        priority=SignalPriority.NORMAL,
        sender_position=sender_pos,
        range_limit=100.0,  # Wide range for safety info
        duration=180.0,  # Safety info lasts longer
    )


def create_gather_signal(
    sender_id: str,
    sender_pos: tuple,
    gather_purpose: str = "general",
    max_agents: int = 5,
) -> Signal:
    """Create a gather here signal"""
    return Signal(
        signal_id=f"gather_{sender_id}_{int(time.time())}",
        signal_type=SignalType.GATHER_HERE,
        sender_id=sender_id,
        message=f"Gather for: {gather_purpose}",
        data={
            "purpose": gather_purpose,
            "gathering_point": sender_pos,
            "max_agents": max_agents,
            "current_count": 1,  # Sender counts as first
        },
        priority=SignalPriority.NORMAL,
        sender_position=sender_pos,
        range_limit=50.0,
        duration=120.0,
    )


def create_danger_warning(
    sender_id: str, sender_pos: tuple, danger_area: tuple, danger_type: str = "unknown"
) -> Signal:
    """Create a danger warning signal"""
    return Signal(
        signal_id=f"danger_{sender_id}_{int(time.time())}",
        signal_type=SignalType.DANGER_WARNING,
        sender_id=sender_id,
        message=f"Danger: {danger_type}",
        data={
            "danger_area": danger_area,  # (x, y, radius)
            "danger_type": danger_type,
            "severity": "high",
        },
        priority=SignalPriority.HIGH,
        sender_position=sender_pos,
        range_limit=100.0,  # Wide range for warnings
        duration=300.0,  # Danger warnings last long
    )


def create_retreat_signal(
    sender_id: str, sender_pos: tuple, retreat_to: Optional[tuple] = None
) -> Signal:
    """Create a retreat signal"""
    return Signal(
        signal_id=f"retreat_{sender_id}_{int(time.time())}",
        signal_type=SignalType.RETREAT,
        sender_id=sender_id,
        message="Retreat signal",
        data={"retreat_to": retreat_to, "reason": "tactical_withdrawal"},
        priority=SignalPriority.URGENT,
        sender_position=sender_pos,
        range_limit=60.0,
        duration=30.0,  # Short duration for immediate action
    )


def create_follow_me_signal(
    sender_id: str,
    sender_pos: tuple,
    destination: Optional[tuple] = None,
    purpose: str = "unknown",
) -> Signal:
    """Create a follow me signal"""
    return Signal(
        signal_id=f"follow_{sender_id}_{int(time.time())}",
        signal_type=SignalType.FOLLOW_ME,
        sender_id=sender_id,
        message=f"Follow me: {purpose}",
        data={"destination": destination, "purpose": purpose, "leader_id": sender_id},
        priority=SignalPriority.NORMAL,
        sender_position=sender_pos,
        range_limit=30.0,
        duration=180.0,
    )


def create_task_complete_signal(
    sender_id: str,
    sender_pos: tuple,
    task_type: str,
    task_location: Optional[tuple] = None,
) -> Signal:
    """Create a task complete signal"""
    return Signal(
        signal_id=f"complete_{sender_id}_{int(time.time())}",
        signal_type=SignalType.TASK_COMPLETE,
        sender_id=sender_id,
        message=f"Task completed: {task_type}",
        data={
            "task_type": task_type,
            "task_location": task_location,
            "completion_time": time.time(),
        },
        priority=SignalPriority.NORMAL,
        sender_position=sender_pos,
        range_limit=40.0,
        duration=60.0,
    )


class SignalFilter:
    """Filters signals based on agent preferences and context"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.blocked_senders: Set[str] = set()
        self.priority_threshold = SignalPriority.LOW
        self.max_signal_age = 300.0  # 5 minutes

        # Signal type preferences (0.0 = ignore, 1.0 = always accept)
        self.signal_preferences = {
            SignalType.HELP_REQUEST: 1.0,
            SignalType.RESOURCE_FOUND: 0.8,
            SignalType.ENEMY_SPOTTED: 1.0,
            SignalType.TRADE_OFFER: 0.6,
            SignalType.AREA_CLEAR: 0.7,
            SignalType.GATHER_HERE: 0.5,
            SignalType.DANGER_WARNING: 1.0,
            SignalType.TASK_COMPLETE: 0.4,
            SignalType.FOLLOW_ME: 0.3,
            SignalType.RETREAT: 1.0,
        }

    def should_receive_signal(self, signal: Signal, agent_personality=None) -> bool:
        """Determine if agent should receive this signal"""
        # Check basic filters
        if signal.sender_id in self.blocked_senders:
            return False

        if signal.is_expired():
            return False

        if signal.priority.value < self.priority_threshold.value:
            return False

        if not signal.is_targeted_to(self.agent_id):
            return False

        # Check signal type preference
        base_preference = self.signal_preferences.get(signal.signal_type, 0.5)

        # Adjust preference based on personality
        if agent_personality:
            preference = self._adjust_preference_for_personality(
                signal, base_preference, agent_personality
            )
        else:
            preference = base_preference

        # Random factor for some variation
        import random

        return random.random() < preference

    def _adjust_preference_for_personality(
        self, signal: Signal, base_preference: float, personality
    ) -> float:
        """Adjust signal preference based on agent personality"""
        adjusted = base_preference

        # Social agents more likely to respond to social signals
        if hasattr(personality, "social"):
            social_factor = personality.social / 10.0
            if signal.signal_type in [
                SignalType.GATHER_HERE,
                SignalType.FOLLOW_ME,
                SignalType.HELP_REQUEST,
            ]:
                adjusted *= 1.0 + social_factor * 0.5

        # Cooperative agents more likely to help
        if hasattr(personality, "cooperativeness"):
            coop_factor = personality.cooperativeness / 10.0
            if signal.signal_type in [SignalType.HELP_REQUEST, SignalType.GATHER_HERE]:
                adjusted *= 1.0 + coop_factor * 0.3

        # Combat-oriented agents more interested in combat signals
        if hasattr(personality, "combat"):
            combat_factor = personality.combat / 10.0
            if signal.signal_type in [
                SignalType.ENEMY_SPOTTED,
                SignalType.RETREAT,
                SignalType.DANGER_WARNING,
            ]:
                adjusted *= 1.0 + combat_factor * 0.4

        # Resource-focused agents care more about resource signals
        if hasattr(personality, "foraging") or hasattr(personality, "fishing"):
            resource_interest = 0.0
            if hasattr(personality, "foraging"):
                resource_interest += personality.foraging / 10.0
            if hasattr(personality, "fishing"):
                resource_interest += personality.fishing / 10.0

            if signal.signal_type == SignalType.RESOURCE_FOUND:
                adjusted *= 1.0 + (resource_interest / 2.0) * 0.6

        # Money-focused agents care about trade offers
        if hasattr(personality, "money"):
            money_factor = personality.money / 10.0
            if signal.signal_type == SignalType.TRADE_OFFER:
                adjusted *= 1.0 + money_factor * 0.5

        return min(1.0, max(0.0, adjusted))

    def set_signal_preference(self, signal_type: SignalType, preference: float):
        """Set preference for a specific signal type (0.0 - 1.0)"""
        self.signal_preferences[signal_type] = max(0.0, min(1.0, preference))

    def block_sender(self, sender_id: str):
        """Block signals from a specific sender"""
        self.blocked_senders.add(sender_id)

    def unblock_sender(self, sender_id: str):
        """Unblock signals from a specific sender"""
        self.blocked_senders.discard(sender_id)

    def set_priority_threshold(self, threshold: SignalPriority):
        """Set minimum priority for received signals"""
        self.priority_threshold = threshold
