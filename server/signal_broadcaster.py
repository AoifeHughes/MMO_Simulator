"""
Server-Side Signal Broadcasting System

This module handles the server-side processing and distribution of signals between agents,
ensuring proper range checking, filtering, and delivery of agent communications.
"""

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from shared.signals import Signal, SignalPriority, SignalType

logger = logging.getLogger(__name__)


class SignalBroadcaster:
    """
    Server-side signal broadcasting system that manages agent communications.

    Handles signal routing, range checking, filtering, and delivery to ensure
    efficient and realistic agent communication.
    """

    def __init__(self, server):
        self.server = server
        self.active_signals: Dict[str, Signal] = {}
        self.signal_history: List[Signal] = []
        self.max_history_size = 1000

        # Performance tracking
        self.signals_sent = 0
        self.signals_delivered = 0
        self.last_cleanup_time = time.time()
        self.cleanup_interval = 30.0  # Clean up every 30 seconds

        # Rate limiting
        self.agent_signal_counts: Dict[str, List[float]] = defaultdict(list)
        self.max_signals_per_minute = 10
        self.spam_penalty_duration = 60.0

    def broadcast_signal(self, signal: Signal) -> bool:
        """
        Broadcast a signal from an agent to appropriate recipients.

        Args:
            signal: The signal to broadcast

        Returns:
            True if signal was accepted and broadcast, False if rejected
        """
        # Validate signal
        if not self._validate_signal(signal):
            return False

        # Check rate limiting
        if not self._check_rate_limit(signal.sender_id):
            logger.warning(
                f"Signal from {signal.sender_id} rejected due to rate limiting"
            )
            return False

        # Store signal
        self.active_signals[signal.signal_id] = signal
        self.signal_history.append(signal)

        # Trim history if needed
        if len(self.signal_history) > self.max_history_size:
            self.signal_history = self.signal_history[-self.max_history_size :]

        # Find and notify recipients
        recipients = self._find_recipients(signal)
        delivered_count = 0

        for recipient_id in recipients:
            if self._deliver_signal_to_agent(signal, recipient_id):
                delivered_count += 1

        # Update statistics
        self.signals_sent += 1
        self.signals_delivered += delivered_count

        logger.debug(
            f"Signal {signal.signal_id} broadcast to {delivered_count} recipients"
        )
        return True

    def process_signals(self):
        """Process and maintain signals (called periodically by server)"""
        current_time = time.time()

        # Clean up expired signals
        if current_time - self.last_cleanup_time > self.cleanup_interval:
            self._cleanup_expired_signals()
            self._cleanup_rate_limiting()
            self.last_cleanup_time = current_time

    def get_signals_for_agent(
        self, agent_id: str, agent_position: tuple
    ) -> List[Signal]:
        """Get all signals visible to a specific agent"""
        visible_signals = []
        agent_x, agent_y = agent_position

        for signal in self.active_signals.values():
            if self._can_agent_receive_signal(agent_id, signal, agent_x, agent_y):
                visible_signals.append(signal)

        # Sort by priority and recency
        visible_signals.sort(
            key=lambda s: (s.priority.value, -s.timestamp), reverse=True
        )

        return visible_signals

    def remove_signal(self, signal_id: str) -> bool:
        """Remove a specific signal"""
        if signal_id in self.active_signals:
            del self.active_signals[signal_id]
            return True
        return False

    def get_broadcast_statistics(self) -> Dict[str, Any]:
        """Get broadcasting statistics"""
        return {
            "active_signals": len(self.active_signals),
            "signals_sent": self.signals_sent,
            "signals_delivered": self.signals_delivered,
            "delivery_rate": self.signals_delivered / max(1, self.signals_sent),
            "signal_types": self._get_signal_type_counts(),
            "top_senders": self._get_top_senders(),
        }

    def _validate_signal(self, signal: Signal) -> bool:
        """Validate a signal before broadcasting"""
        # Check if sender exists
        if not self._agent_exists(signal.sender_id):
            logger.warning(f"Signal from non-existent agent: {signal.sender_id}")
            return False

        # Check signal content
        if not signal.signal_id or not signal.message:
            logger.warning(f"Invalid signal content from {signal.sender_id}")
            return False

        # Check if signal already exists
        if signal.signal_id in self.active_signals:
            logger.warning(f"Duplicate signal ID: {signal.signal_id}")
            return False

        return True

    def _check_rate_limit(self, agent_id: str) -> bool:
        """Check if agent is within rate limits"""
        current_time = time.time()
        agent_signals = self.agent_signal_counts[agent_id]

        # Remove old signals (outside the minute window)
        cutoff_time = current_time - 60.0
        self.agent_signal_counts[agent_id] = [
            timestamp for timestamp in agent_signals if timestamp > cutoff_time
        ]

        # Check if under limit
        if len(self.agent_signal_counts[agent_id]) >= self.max_signals_per_minute:
            return False

        # Add current signal
        self.agent_signal_counts[agent_id].append(current_time)
        return True

    def _find_recipients(self, signal: Signal) -> Set[str]:
        """Find all agents that should receive this signal"""
        recipients = set()

        # Get all agents from server
        all_agents = self._get_all_agents()

        for agent_id, agent_position in all_agents.items():
            # Skip sender
            if agent_id == signal.sender_id:
                continue

            # Check if agent can receive this signal
            if self._can_agent_receive_signal(agent_id, signal, *agent_position):
                recipients.add(agent_id)

        return recipients

    def _can_agent_receive_signal(
        self, agent_id: str, signal: Signal, agent_x: float, agent_y: float
    ) -> bool:
        """Check if an agent can receive a specific signal"""
        # Check if signal is targeted appropriately
        if not signal.is_targeted_to(agent_id):
            return False

        # Check range
        if not signal.is_in_range_of(agent_x, agent_y):
            return False

        # Check if signal is expired
        if signal.is_expired():
            return False

        return True

    def _deliver_signal_to_agent(self, signal: Signal, recipient_id: str) -> bool:
        """Deliver a signal to a specific agent"""
        try:
            # Get agent from server
            agent = self._get_agent(recipient_id)
            if not agent:
                return False

            # Check if agent has signal processing capability
            if hasattr(agent, "receive_signal"):
                agent.receive_signal(signal)
                return True
            elif hasattr(agent, "signal_queue"):
                # Alternative: add to signal queue
                agent.signal_queue.append(signal)
                return True
            else:
                # Agent doesn't support signals
                return False

        except Exception as e:
            logger.error(f"Error delivering signal to {recipient_id}: {e}")
            return False

    def _cleanup_expired_signals(self):
        """Remove expired signals"""
        current_time = time.time()
        expired_signals = []

        for signal_id, signal in self.active_signals.items():
            if signal.is_expired():
                expired_signals.append(signal_id)

        for signal_id in expired_signals:
            del self.active_signals[signal_id]

        if expired_signals:
            logger.debug(f"Cleaned up {len(expired_signals)} expired signals")

    def _cleanup_rate_limiting(self):
        """Clean up old rate limiting data"""
        current_time = time.time()
        cutoff_time = current_time - 120.0  # Keep 2 minutes of history

        for agent_id in list(self.agent_signal_counts.keys()):
            agent_signals = self.agent_signal_counts[agent_id]
            recent_signals = [
                timestamp for timestamp in agent_signals if timestamp > cutoff_time
            ]

            if recent_signals:
                self.agent_signal_counts[agent_id] = recent_signals
            else:
                del self.agent_signal_counts[agent_id]

    def _agent_exists(self, agent_id: str) -> bool:
        """Check if an agent exists on the server"""
        try:
            if hasattr(self.server, "world") and hasattr(
                self.server.world, "get_agent"
            ):
                return self.server.world.get_agent(agent_id) is not None
            elif hasattr(self.server, "agent_registry"):
                return self.server.agent_registry.has_agent(agent_id)
            else:
                return True  # Assume exists if we can't check
        except Exception:
            return True  # Assume exists if check fails

    def _get_all_agents(self) -> Dict[str, tuple]:
        """Get all agents and their positions"""
        agents = {}

        try:
            if hasattr(self.server, "world") and hasattr(
                self.server.world, "get_all_agents"
            ):
                for agent in self.server.world.get_all_agents():
                    agents[agent.id] = (agent.x, agent.y)
            elif hasattr(self.server, "agent_registry"):
                for agent_id in self.server.agent_registry.get_all_agent_ids():
                    agent = self.server.agent_registry.get_agent(agent_id)
                    if agent:
                        agents[agent_id] = (agent.x, agent.y)
        except Exception as e:
            logger.error(f"Error getting agents for signal broadcast: {e}")

        return agents

    def _get_agent(self, agent_id: str):
        """Get a specific agent instance"""
        try:
            if hasattr(self.server, "world") and hasattr(
                self.server.world, "get_agent"
            ):
                return self.server.world.get_agent(agent_id)
            elif hasattr(self.server, "agent_registry"):
                return self.server.agent_registry.get_agent(agent_id)
        except Exception as e:
            logger.error(f"Error getting agent {agent_id}: {e}")

        return None

    def _get_signal_type_counts(self) -> Dict[str, int]:
        """Get counts of each signal type"""
        counts = defaultdict(int)
        for signal in self.active_signals.values():
            counts[signal.signal_type.value] += 1
        return dict(counts)

    def _get_top_senders(self, limit: int = 5) -> List[tuple]:
        """Get top signal senders"""
        sender_counts = defaultdict(int)
        for signal in self.active_signals.values():
            sender_counts[signal.sender_id] += 1

        # Sort by count and return top senders
        top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)
        return top_senders[:limit]


class SignalQueue:
    """Signal queue for agents to manage received signals"""

    def __init__(self, agent_id: str, max_size: int = 50):
        self.agent_id = agent_id
        self.max_size = max_size
        self.signals: List[Signal] = []
        self.processed_signals: Set[str] = set()

    def add_signal(self, signal: Signal):
        """Add a signal to the queue"""
        # Check if already processed
        if signal.signal_id in self.processed_signals:
            return

        # Add to queue
        self.signals.append(signal)

        # Sort by priority and recency
        self.signals.sort(key=lambda s: (s.priority.value, -s.timestamp), reverse=True)

        # Trim if too large
        if len(self.signals) > self.max_size:
            removed = self.signals[self.max_size :]
            self.signals = self.signals[: self.max_size]

            # Mark removed signals as processed to avoid re-adding
            for removed_signal in removed:
                self.processed_signals.add(removed_signal.signal_id)

    def get_next_signal(self) -> Optional[Signal]:
        """Get the next highest priority signal"""
        # Remove expired signals first
        self.signals = [s for s in self.signals if not s.is_expired()]

        if self.signals:
            signal = self.signals.pop(0)
            self.processed_signals.add(signal.signal_id)
            return signal

        return None

    def get_signals_by_type(self, signal_type: SignalType) -> List[Signal]:
        """Get all signals of a specific type"""
        return [
            s
            for s in self.signals
            if s.signal_type == signal_type and not s.is_expired()
        ]

    def clear_expired(self):
        """Remove expired signals from queue"""
        original_count = len(self.signals)
        self.signals = [s for s in self.signals if not s.is_expired()]

        if len(self.signals) < original_count:
            logger.debug(
                f"Agent {self.agent_id} cleared {original_count - len(self.signals)} expired signals"
            )

    def clear_all(self):
        """Clear all signals from queue"""
        self.signals.clear()

    def get_queue_info(self) -> Dict[str, Any]:
        """Get information about the signal queue"""
        return {
            "total_signals": len(self.signals),
            "by_priority": {
                priority.name: len([s for s in self.signals if s.priority == priority])
                for priority in SignalPriority
            },
            "by_type": {
                signal_type.name: len(
                    [s for s in self.signals if s.signal_type == signal_type]
                )
                for signal_type in SignalType
            },
        }
