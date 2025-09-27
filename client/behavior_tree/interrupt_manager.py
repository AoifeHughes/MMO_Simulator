"""
Interrupt & Resume System for Behavior Trees

This module enables agents to:
- Handle interruptions gracefully by preserving behavior state
- Make intelligent decisions about when to interrupt current behaviors
- Resume interrupted behaviors when appropriate
- Track interrupt history to learn from patterns
- Balance multiple competing priorities dynamically
"""

import logging
import time
import pickle
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .nodes.base import BehaviorNode, NodeStatus

logger = logging.getLogger(__name__)


class InterruptPriority(Enum):
    """Priority levels for interrupts"""
    EMERGENCY = 100     # Life-threatening situations (health < 10%)
    CRITICAL = 80       # Immediate threats (under attack)
    URGENT = 60         # Important opportunities (rare resources)
    HIGH = 40           # Significant events (trade opportunities)
    NORMAL = 20         # Regular interrupts (social interactions)
    LOW = 10           # Minor distractions (exploration opportunities)


class InterruptReason(Enum):
    """Reasons for behavior interruption"""
    HEALTH_CRITICAL = "health_critical"
    UNDER_ATTACK = "under_attack"
    BETTER_OPPORTUNITY = "better_opportunity"
    RESOURCE_DEPLETED = "resource_depleted"
    TIME_LIMIT_EXCEEDED = "time_limit_exceeded"
    EXTERNAL_REQUEST = "external_request"
    ENVIRONMENT_CHANGED = "environment_changed"
    GOAL_COMPLETED = "goal_completed"
    GOAL_IMPOSSIBLE = "goal_impossible"


class ResumptionStrategy(Enum):
    """Strategies for resuming interrupted behaviors"""
    RESUME_IMMEDIATELY = "resume_immediately"     # Resume as soon as interrupt clears
    RESUME_WITH_DELAY = "resume_with_delay"       # Wait a bit before resuming
    RESUME_WHEN_OPTIMAL = "resume_when_optimal"   # Wait for good conditions
    REEVALUATE_NECESSITY = "reevaluate_necessity" # Check if still needed
    ABANDON_GRACEFULLY = "abandon_gracefully"     # Don't resume, clean up
    RESTART_FROM_BEGINNING = "restart_from_beginning" # Start over completely


@dataclass
class BehaviorState:
    """Represents the state of a behavior that can be preserved during interruption"""
    behavior_id: str
    behavior_type: str
    state_data: Dict[str, Any]
    progress: float  # 0.0 to 1.0
    context: Dict[str, Any]
    start_time: float
    last_update_time: float
    execution_count: int = 0
    success_probability: float = 1.0  # Estimated chance of success if resumed

    def get_age(self, current_time: Optional[float] = None) -> float:
        """Get how long this behavior has been running"""
        if current_time is None:
            current_time = time.time()
        return current_time - self.start_time

    def get_time_since_update(self, current_time: Optional[float] = None) -> float:
        """Get time since last update"""
        if current_time is None:
            current_time = time.time()
        return current_time - self.last_update_time

    def update_progress(self, new_progress: float):
        """Update behavior progress"""
        self.progress = max(0.0, min(1.0, new_progress))
        self.last_update_time = time.time()
        self.execution_count += 1

    def serialize_state(self) -> str:
        """Serialize state for storage"""
        try:
            return pickle.dumps(self.state_data).hex()
        except:
            logger.warning(f"Failed to serialize state for behavior {self.behavior_id}")
            return ""

    def deserialize_state(self, serialized_data: str) -> bool:
        """Deserialize state from storage"""
        try:
            self.state_data = pickle.loads(bytes.fromhex(serialized_data))
            return True
        except:
            logger.warning(f"Failed to deserialize state for behavior {self.behavior_id}")
            return False


@dataclass
class InterruptEvent:
    """Represents an interruption event"""
    interrupt_id: str
    priority: InterruptPriority
    reason: InterruptReason
    interrupted_behavior_id: str  # Behavior that was interrupted
    interrupt_time: float
    source_behavior_id: Optional[str] = None  # Behavior that caused the interrupt
    context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_time: Optional[float] = None
    resumption_strategy: ResumptionStrategy = ResumptionStrategy.RESUME_IMMEDIATELY

    def get_duration(self, current_time: Optional[float] = None) -> float:
        """Get how long this interrupt has been active"""
        if current_time is None:
            current_time = time.time()
        end_time = self.resolution_time if self.resolved else current_time
        return end_time - self.interrupt_time

    def resolve(self, strategy: ResumptionStrategy = ResumptionStrategy.RESUME_IMMEDIATELY):
        """Mark interrupt as resolved"""
        self.resolved = True
        self.resolution_time = time.time()
        self.resumption_strategy = strategy


class InterruptManager:
    """Manages behavior interruptions and resumptions"""

    def __init__(self, max_preserved_behaviors: int = 10, cleanup_interval: float = 300.0):
        self.max_preserved_behaviors = max_preserved_behaviors
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()

        # State management
        self.preserved_behaviors: Dict[str, BehaviorState] = {}
        self.interrupt_stack: List[InterruptEvent] = []  # Most recent interrupts first
        self.active_interrupts: Dict[str, InterruptEvent] = {}

        # History and analytics
        self.interrupt_history: deque = deque(maxlen=100)
        self.behavior_resumption_success: Dict[str, List[bool]] = defaultdict(list)

        # Configuration
        self.interrupt_thresholds = {
            InterruptPriority.EMERGENCY: 0.95,   # Almost always interrupt
            InterruptPriority.CRITICAL: 0.85,
            InterruptPriority.URGENT: 0.70,
            InterruptPriority.HIGH: 0.55,
            InterruptPriority.NORMAL: 0.40,
            InterruptPriority.LOW: 0.25          # Rarely interrupt
        }

        # Statistics
        self.stats = {
            "total_interrupts": 0,
            "successful_resumptions": 0,
            "abandoned_behaviors": 0,
            "interrupt_reasons": defaultdict(int),
            "average_interrupt_duration": 0.0
        }

    def should_interrupt(self, current_behavior_id: str, interrupt_priority: InterruptPriority,
                        reason: InterruptReason, context: Dict[str, Any]) -> bool:
        """Determine if current behavior should be interrupted"""

        # Always allow emergency interrupts
        if interrupt_priority == InterruptPriority.EMERGENCY:
            return True

        # Get current behavior state
        current_behavior = self.preserved_behaviors.get(current_behavior_id)
        if not current_behavior:
            return True  # No current behavior to protect

        # Calculate interrupt probability based on multiple factors
        base_probability = self.interrupt_thresholds[interrupt_priority]

        # Factor 1: Current behavior progress (more progress = harder to interrupt)
        progress_factor = 1.0 - (current_behavior.progress * 0.4)

        # Factor 2: Current behavior age (longer running = more invested)
        age_factor = max(0.6, 1.0 - (current_behavior.get_age() / 3600.0))  # Reduce over 1 hour

        # Factor 3: Success probability of current behavior
        success_factor = 2.0 - current_behavior.success_probability

        # Factor 4: Recent interrupt frequency (avoid thrashing)
        recent_interrupts = len([i for i in self.interrupt_history
                               if time.time() - i.interrupt_time < 60.0])
        frequency_factor = max(0.5, 1.0 - (recent_interrupts * 0.1))

        # Factor 5: Context-specific factors
        context_factor = self._calculate_context_factor(reason, context, current_behavior)

        # Combine all factors
        final_probability = (base_probability * progress_factor * age_factor *
                           success_factor * frequency_factor * context_factor)

        # Add some randomness to avoid predictable behavior
        import random
        random_factor = random.uniform(0.8, 1.2)
        final_probability *= random_factor

        decision = random.random() < final_probability

        logger.debug(f"Interrupt decision for {current_behavior_id}: {decision} "
                    f"(prob={final_probability:.3f}, priority={interrupt_priority.name})")

        return decision

    def _calculate_context_factor(self, reason: InterruptReason, context: Dict[str, Any],
                                current_behavior: BehaviorState) -> float:
        """Calculate context-specific interrupt factor"""
        factor = 1.0

        if reason == InterruptReason.UNDER_ATTACK:
            # More likely to interrupt if low health or multiple attackers
            health_pct = context.get("health_percentage", 100.0)
            attacker_count = context.get("attacker_count", 1)
            factor *= (2.0 - health_pct / 100.0) * min(2.0, 1.0 + attacker_count * 0.3)

        elif reason == InterruptReason.BETTER_OPPORTUNITY:
            # Compare opportunity value with current behavior
            opportunity_value = context.get("opportunity_value", 1.0)
            current_value = current_behavior.context.get("expected_value", 1.0)
            factor *= min(3.0, opportunity_value / max(0.1, current_value))

        elif reason == InterruptReason.RESOURCE_DEPLETED:
            # High factor if current behavior depends on the depleted resource
            depleted_resource = context.get("resource_type", "")
            current_target = current_behavior.context.get("target_resource", "")
            if depleted_resource == current_target:
                factor *= 2.5

        elif reason == InterruptReason.TIME_LIMIT_EXCEEDED:
            # Factor based on how much time has exceeded
            exceeded_by = context.get("time_exceeded_seconds", 0)
            factor *= min(2.0, 1.0 + exceeded_by / 300.0)  # Scale over 5 minutes

        return max(0.1, min(3.0, factor))

    def interrupt_behavior(self, behavior_id: str, priority: InterruptPriority,
                          reason: InterruptReason, interrupting_behavior_id: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None) -> InterruptEvent:
        """Interrupt a behavior and preserve its state"""

        context = context or {}
        interrupt_id = f"interrupt_{int(time.time() * 1000000)}"

        # Create interrupt event
        interrupt_event = InterruptEvent(
            interrupt_id=interrupt_id,
            priority=priority,
            reason=reason,
            source_behavior_id=interrupting_behavior_id,
            interrupted_behavior_id=behavior_id,
            interrupt_time=time.time(),
            context=context
        )

        # Preserve current behavior state if it exists
        if behavior_id in self.preserved_behaviors:
            behavior_state = self.preserved_behaviors[behavior_id]
            logger.info(f"Interrupting behavior {behavior_id} (progress: {behavior_state.progress:.2f}) "
                       f"due to {reason.value} with priority {priority.name}")
        else:
            logger.info(f"Interrupting behavior {behavior_id} due to {reason.value}")

        # Add to interrupt tracking
        self.interrupt_stack.insert(0, interrupt_event)
        self.active_interrupts[interrupt_id] = interrupt_event
        self.interrupt_history.append(interrupt_event)

        # Update statistics
        self.stats["total_interrupts"] += 1
        self.stats["interrupt_reasons"][reason.value] += 1

        return interrupt_event

    def preserve_behavior_state(self, behavior_id: str, behavior_type: str,
                               state_data: Dict[str, Any], progress: float = 0.0,
                               context: Optional[Dict[str, Any]] = None,
                               success_probability: float = 1.0) -> BehaviorState:
        """Preserve the state of a behavior for later resumption"""

        context = context or {}
        current_time = time.time()

        # Check if we already have this behavior preserved
        if behavior_id in self.preserved_behaviors:
            existing_state = self.preserved_behaviors[behavior_id]
            existing_state.state_data.update(state_data)
            existing_state.update_progress(progress)
            existing_state.success_probability = success_probability
            return existing_state

        # Create new behavior state
        behavior_state = BehaviorState(
            behavior_id=behavior_id,
            behavior_type=behavior_type,
            state_data=state_data,
            progress=progress,
            context=context,
            start_time=current_time,
            last_update_time=current_time,
            success_probability=success_probability
        )

        # Store the preserved state
        self.preserved_behaviors[behavior_id] = behavior_state

        # Cleanup if too many preserved behaviors
        if len(self.preserved_behaviors) > self.max_preserved_behaviors:
            self._cleanup_old_behaviors()

        logger.debug(f"Preserved behavior state for {behavior_id} with progress {progress:.2f}")
        return behavior_state

    def can_resume_behavior(self, behavior_id: str, current_context: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if a behavior can be resumed given current context"""

        if behavior_id not in self.preserved_behaviors:
            return False, "Behavior state not preserved"

        behavior_state = self.preserved_behaviors[behavior_id]
        current_time = time.time()

        # Check if behavior is too old
        age = behavior_state.get_age(current_time)
        if age > 3600.0:  # 1 hour
            return False, "Behavior too old to resume"

        # Check if success probability is still reasonable
        if behavior_state.success_probability < 0.3:
            return False, "Low success probability"

        # Check context compatibility
        required_resources = behavior_state.context.get("required_resources", [])
        for resource in required_resources:
            # Check both "has_resource" and direct resource name
            has_resource = (current_context.get(f"has_{resource}", False) or
                          current_context.get(resource, False))
            if not has_resource:
                return False, f"Required resource {resource} no longer available"

        # Check if there are blocking interrupts
        blocking_interrupts = [i for i in self.active_interrupts.values()
                             if i.priority.value >= InterruptPriority.CRITICAL.value and not i.resolved]
        if blocking_interrupts:
            return False, "Critical interrupts still active"

        return True, "Can resume"

    def get_resumption_strategy(self, behavior_id: str, interrupt_event: InterruptEvent) -> ResumptionStrategy:
        """Determine the best strategy for resuming a behavior"""

        if behavior_id not in self.preserved_behaviors:
            return ResumptionStrategy.ABANDON_GRACEFULLY

        behavior_state = self.preserved_behaviors[behavior_id]
        interrupt_duration = interrupt_event.get_duration()

        # Emergency interrupts: usually resume immediately
        if interrupt_event.priority == InterruptPriority.EMERGENCY:
            if interrupt_event.reason == InterruptReason.HEALTH_CRITICAL:
                return ResumptionStrategy.RESUME_WITH_DELAY  # Wait for health to stabilize
            return ResumptionStrategy.RESUME_IMMEDIATELY

        # Critical interrupts: depend on reason
        if interrupt_event.priority == InterruptPriority.CRITICAL:
            if interrupt_event.reason == InterruptReason.UNDER_ATTACK:
                return ResumptionStrategy.RESUME_WHEN_OPTIMAL  # Wait for safety
            elif interrupt_event.reason == InterruptReason.BETTER_OPPORTUNITY:
                return ResumptionStrategy.REEVALUATE_NECESSITY  # Check if still worthwhile

        # Resource-based interrupts: usually abandon or reevaluate
        if interrupt_event.reason == InterruptReason.RESOURCE_DEPLETED:
            return ResumptionStrategy.ABANDON_GRACEFULLY

        # Consider behavior progress
        if behavior_state.progress > 0.8:
            return ResumptionStrategy.RESUME_IMMEDIATELY  # Close to completion
        elif behavior_state.progress < 0.2:
            return ResumptionStrategy.RESTART_FROM_BEGINNING  # Minimal progress lost

        # Consider interrupt duration
        if interrupt_duration > 300.0:  # 5 minutes
            if behavior_state.behavior_type in ["exploration", "casual_gathering"]:
                return ResumptionStrategy.ABANDON_GRACEFULLY  # Low priority behaviors
            else:
                return ResumptionStrategy.REEVALUATE_NECESSITY  # Check if still needed

        # Consider historical success rate
        behavior_type = behavior_state.behavior_type
        if behavior_type in self.behavior_resumption_success:
            success_rate = sum(self.behavior_resumption_success[behavior_type]) / len(self.behavior_resumption_success[behavior_type])
            if success_rate < 0.5:
                return ResumptionStrategy.REEVALUATE_NECESSITY

        # Default strategy
        return ResumptionStrategy.RESUME_WHEN_OPTIMAL

    def resume_behavior(self, behavior_id: str, force_strategy: Optional[ResumptionStrategy] = None) -> Tuple[bool, Optional[BehaviorState], str]:
        """Attempt to resume a preserved behavior"""

        if behavior_id not in self.preserved_behaviors:
            return False, None, "Behavior state not found"

        behavior_state = self.preserved_behaviors[behavior_id]

        # Find the most recent interrupt for this behavior
        interrupt_event = None
        for interrupt in self.interrupt_stack:
            if interrupt.interrupted_behavior_id == behavior_id:
                interrupt_event = interrupt
                break

        if not interrupt_event:
            logger.warning(f"No interrupt event found for behavior {behavior_id}")
            # Create a synthetic interrupt event
            interrupt_event = InterruptEvent(
                interrupt_id="synthetic",
                priority=InterruptPriority.NORMAL,
                reason=InterruptReason.EXTERNAL_REQUEST,
                interrupted_behavior_id=behavior_id,
                interrupt_time=time.time() - 1.0
            )

        # Determine resumption strategy
        strategy = force_strategy or self.get_resumption_strategy(behavior_id, interrupt_event)

        # Execute strategy
        if strategy == ResumptionStrategy.ABANDON_GRACEFULLY:
            self._abandon_behavior(behavior_id, "Strategy: abandon gracefully")
            return False, None, "Behavior abandoned"

        elif strategy == ResumptionStrategy.RESTART_FROM_BEGINNING:
            behavior_state.progress = 0.0
            behavior_state.execution_count = 0
            behavior_state.state_data.clear()
            behavior_state.last_update_time = time.time()
            logger.info(f"Restarting behavior {behavior_id} from beginning")

        elif strategy == ResumptionStrategy.REEVALUATE_NECESSITY:
            # This requires external evaluation - return state for caller to decide
            logger.info(f"Behavior {behavior_id} requires reevaluation before resumption")
            return True, behavior_state, "Requires reevaluation"

        elif strategy == ResumptionStrategy.RESUME_WITH_DELAY:
            # Check if enough time has passed
            time_since_interrupt = time.time() - interrupt_event.interrupt_time
            if time_since_interrupt < 30.0:  # 30 second delay
                return False, behavior_state, f"Delaying resumption ({30 - time_since_interrupt:.1f}s remaining)"

        # Mark interrupt as resolved
        if interrupt_event and not interrupt_event.resolved:
            interrupt_event.resolve(strategy)
            if interrupt_event.interrupt_id in self.active_interrupts:
                del self.active_interrupts[interrupt_event.interrupt_id]

        # Update statistics
        self.stats["successful_resumptions"] += 1

        logger.info(f"Resuming behavior {behavior_id} with strategy {strategy.value} "
                   f"(progress: {behavior_state.progress:.2f})")

        return True, behavior_state, "Resumed successfully"

    def _abandon_behavior(self, behavior_id: str, reason: str):
        """Abandon a preserved behavior"""
        if behavior_id in self.preserved_behaviors:
            behavior_state = self.preserved_behaviors[behavior_id]
            logger.info(f"Abandoning behavior {behavior_id} - {reason}")

            # Track abandonment in resumption history
            behavior_type = behavior_state.behavior_type
            self.behavior_resumption_success[behavior_type].append(False)

            # Update statistics
            self.stats["abandoned_behaviors"] += 1

            # Remove from preserved behaviors
            del self.preserved_behaviors[behavior_id]

    def get_next_behavior_to_resume(self, current_context: Dict[str, Any]) -> Optional[Tuple[str, BehaviorState]]:
        """Get the next behavior that should be resumed based on priority and context"""

        candidates = []

        for behavior_id, behavior_state in self.preserved_behaviors.items():
            can_resume, reason = self.can_resume_behavior(behavior_id, current_context)
            if can_resume:
                # Calculate resumption priority
                priority_score = self._calculate_resumption_priority(behavior_state, current_context)
                candidates.append((behavior_id, behavior_state, priority_score))

        if not candidates:
            return None

        # Sort by priority (highest first)
        candidates.sort(key=lambda x: x[2], reverse=True)

        return candidates[0][0], candidates[0][1]

    def _calculate_resumption_priority(self, behavior_state: BehaviorState, context: Dict[str, Any]) -> float:
        """Calculate priority score for resuming a behavior"""

        score = 0.0

        # Progress bonus (more progress = higher priority)
        score += behavior_state.progress * 50.0

        # Success probability bonus
        score += behavior_state.success_probability * 30.0

        # Recency bonus (more recent = higher priority)
        age = behavior_state.get_age()
        recency_score = max(0.0, 20.0 - (age / 60.0))  # Decreases over 20 minutes
        score += recency_score

        # Behavior type importance
        type_importance = {
            "combat": 40.0,
            "resource_gathering": 25.0,
            "trading": 20.0,
            "exploration": 15.0,
            "social": 10.0,
            "crafting": 30.0
        }
        score += type_importance.get(behavior_state.behavior_type, 10.0)

        # Context matching bonus
        behavior_context = behavior_state.context
        for key, value in behavior_context.items():
            if key in context and context[key] == value:
                score += 5.0

        return score

    def resolve_interrupt(self, interrupt_id: str, strategy: ResumptionStrategy = ResumptionStrategy.RESUME_IMMEDIATELY) -> bool:
        """Manually resolve an interrupt"""

        if interrupt_id not in self.active_interrupts:
            return False

        interrupt_event = self.active_interrupts[interrupt_id]
        interrupt_event.resolve(strategy)

        # Update average interrupt duration
        duration = interrupt_event.get_duration()
        current_avg = self.stats["average_interrupt_duration"]
        total_interrupts = self.stats["total_interrupts"]
        self.stats["average_interrupt_duration"] = ((current_avg * (total_interrupts - 1)) + duration) / total_interrupts

        del self.active_interrupts[interrupt_id]

        logger.debug(f"Resolved interrupt {interrupt_id} with strategy {strategy.value}")
        return True

    def get_active_interrupts(self) -> List[InterruptEvent]:
        """Get list of currently active interrupts"""
        return list(self.active_interrupts.values())

    def get_preserved_behaviors(self) -> List[BehaviorState]:
        """Get list of currently preserved behaviors"""
        return list(self.preserved_behaviors.values())

    def periodic_cleanup(self):
        """Perform periodic cleanup of old interrupts and behaviors"""
        current_time = time.time()

        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        # Clean up old preserved behaviors
        self._cleanup_old_behaviors()

        # Clean up resolved interrupts from active list
        resolved_interrupts = [iid for iid, interrupt in self.active_interrupts.items() if interrupt.resolved]
        for interrupt_id in resolved_interrupts:
            del self.active_interrupts[interrupt_id]

        # Limit interrupt stack size
        self.interrupt_stack = self.interrupt_stack[:50]

        self.last_cleanup = current_time
        logger.debug(f"Interrupt manager cleanup: {len(self.preserved_behaviors)} behaviors, "
                    f"{len(self.active_interrupts)} active interrupts")

    def _cleanup_old_behaviors(self):
        """Clean up old or low-priority preserved behaviors"""
        current_time = time.time()

        # Sort behaviors by priority (age, progress, success probability)
        behavior_priorities = []
        for behavior_id, behavior_state in self.preserved_behaviors.items():
            age = behavior_state.get_age(current_time)
            priority_score = (
                behavior_state.progress * 50.0 +
                behavior_state.success_probability * 30.0 +
                max(0.0, 20.0 - age / 60.0)  # Recency bonus
            )
            behavior_priorities.append((behavior_id, priority_score))

        # Sort by priority (lowest first for removal)
        behavior_priorities.sort(key=lambda x: x[1])

        # Remove excess behaviors
        while len(self.preserved_behaviors) > self.max_preserved_behaviors:
            behavior_id_to_remove = behavior_priorities.pop(0)[0]
            self._abandon_behavior(behavior_id_to_remove, "Cleanup: capacity exceeded")

    def get_interrupt_statistics(self) -> Dict[str, Any]:
        """Get comprehensive interrupt statistics"""
        current_time = time.time()

        # Calculate additional statistics
        active_interrupt_count = len(self.active_interrupts)
        preserved_behavior_count = len(self.preserved_behaviors)

        # Recent interrupt frequency (last hour)
        recent_interrupts = [i for i in self.interrupt_history
                           if current_time - i.interrupt_time < 3600.0]

        # Success rates by behavior type
        success_rates = {}
        for behavior_type, results in self.behavior_resumption_success.items():
            if results:
                success_rates[behavior_type] = sum(results) / len(results)

        return {
            **self.stats,
            "active_interrupts": active_interrupt_count,
            "preserved_behaviors": preserved_behavior_count,
            "recent_interrupts_per_hour": len(recent_interrupts),
            "resumption_success_rates": success_rates,
            "interrupt_stack_size": len(self.interrupt_stack)
        }

    def get_behavior_state_summary(self, behavior_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of a specific behavior's state"""
        if behavior_id not in self.preserved_behaviors:
            return None

        behavior_state = self.preserved_behaviors[behavior_id]
        current_time = time.time()

        # Find related interrupts
        related_interrupts = [i for i in self.interrupt_history
                            if i.interrupted_behavior_id == behavior_id]

        return {
            "behavior_id": behavior_id,
            "behavior_type": behavior_state.behavior_type,
            "progress": behavior_state.progress,
            "age_seconds": behavior_state.get_age(current_time),
            "execution_count": behavior_state.execution_count,
            "success_probability": behavior_state.success_probability,
            "interrupt_count": len(related_interrupts),
            "last_interrupt_reason": related_interrupts[0].reason.value if related_interrupts else None,
            "can_resume": self.can_resume_behavior(behavior_id, {})[0]
        }