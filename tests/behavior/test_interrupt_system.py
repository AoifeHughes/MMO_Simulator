"""
Tests for Interrupt & Resume System

Tests behavior state preservation, interruption logic, smart resumption decisions,
interrupt history tracking, and integration with the behavior tree system.
"""

import time
from unittest.mock import Mock, patch

import pytest

from client.behavior_tree.interrupt_manager import (
    BehaviorState,
    InterruptEvent,
    InterruptManager,
    InterruptPriority,
    InterruptReason,
    ResumptionStrategy,
)


class TestBehaviorState:
    """Test behavior state functionality"""

    def test_behavior_state_creation(self):
        """Test behavior state creation with all parameters"""
        current_time = time.time()
        state = BehaviorState(
            behavior_id="test_behavior",
            behavior_type="resource_gathering",
            state_data={"target": "wood", "amount": 5},
            progress=0.6,
            context={"location": (10, 20)},
            start_time=current_time,
            last_update_time=current_time,
            success_probability=0.8,
        )

        assert state.behavior_id == "test_behavior"
        assert state.behavior_type == "resource_gathering"
        assert state.state_data["target"] == "wood"
        assert state.progress == 0.6
        assert state.success_probability == 0.8

    def test_behavior_state_age_calculation(self):
        """Test behavior state age calculation"""
        start_time = time.time() - 100  # 100 seconds ago
        state = BehaviorState(
            behavior_id="test",
            behavior_type="test",
            state_data={},
            progress=0.0,
            context={},
            start_time=start_time,
            last_update_time=start_time,
        )

        age = state.get_age()
        assert 99 <= age <= 101  # Allow for small timing differences

    def test_behavior_state_progress_update(self):
        """Test behavior state progress updates"""
        state = BehaviorState(
            behavior_id="test",
            behavior_type="test",
            state_data={},
            progress=0.3,
            context={},
            start_time=time.time(),
            last_update_time=time.time(),
        )

        initial_count = state.execution_count
        initial_update_time = state.last_update_time

        time.sleep(0.01)  # Small delay
        state.update_progress(0.7)

        assert state.progress == 0.7
        assert state.execution_count == initial_count + 1
        assert state.last_update_time > initial_update_time

    def test_behavior_state_serialization(self):
        """Test behavior state serialization"""
        state_data = {"complex_data": [1, 2, {"nested": True}]}
        state = BehaviorState(
            behavior_id="test",
            behavior_type="test",
            state_data=state_data,
            progress=0.0,
            context={},
            start_time=time.time(),
            last_update_time=time.time(),
        )

        # Test serialization
        serialized = state.serialize_state()
        assert isinstance(serialized, str)
        assert len(serialized) > 0

        # Test deserialization
        new_state = BehaviorState(
            "test2", "test", {}, 0.0, {}, time.time(), time.time()
        )
        success = new_state.deserialize_state(serialized)
        assert success
        assert new_state.state_data == state_data


class TestInterruptEvent:
    """Test interrupt event functionality"""

    def test_interrupt_event_creation(self):
        """Test interrupt event creation"""
        current_time = time.time()
        event = InterruptEvent(
            interrupt_id="test_interrupt",
            priority=InterruptPriority.URGENT,
            reason=InterruptReason.UNDER_ATTACK,
            source_behavior_id="combat_behavior",
            interrupted_behavior_id="gathering_behavior",
            interrupt_time=current_time,
            context={"attacker": "bandit"},
        )

        assert event.interrupt_id == "test_interrupt"
        assert event.priority == InterruptPriority.URGENT
        assert event.reason == InterruptReason.UNDER_ATTACK
        assert event.context["attacker"] == "bandit"
        assert not event.resolved

    def test_interrupt_event_duration(self):
        """Test interrupt event duration calculation"""
        start_time = time.time() - 50
        event = InterruptEvent(
            interrupt_id="test",
            priority=InterruptPriority.NORMAL,
            reason=InterruptReason.EXTERNAL_REQUEST,
            interrupted_behavior_id="test_behavior",
            interrupt_time=start_time,
        )

        duration = event.get_duration()
        assert 49 <= duration <= 51  # Allow for timing variance

    def test_interrupt_event_resolution(self):
        """Test interrupt event resolution"""
        event = InterruptEvent(
            interrupt_id="test",
            priority=InterruptPriority.NORMAL,
            reason=InterruptReason.EXTERNAL_REQUEST,
            interrupted_behavior_id="test_behavior",
            interrupt_time=time.time(),
        )

        assert not event.resolved
        assert event.resolution_time is None

        event.resolve(ResumptionStrategy.RESUME_WITH_DELAY)

        assert event.resolved
        assert event.resolution_time is not None
        assert event.resumption_strategy == ResumptionStrategy.RESUME_WITH_DELAY


class TestInterruptManager:
    """Test interrupt manager functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.manager = InterruptManager(max_preserved_behaviors=5)

    def test_interrupt_manager_initialization(self):
        """Test interrupt manager initialization"""
        assert self.manager.max_preserved_behaviors == 5
        assert len(self.manager.preserved_behaviors) == 0
        assert len(self.manager.interrupt_stack) == 0
        assert len(self.manager.active_interrupts) == 0

    def test_should_interrupt_emergency_priority(self):
        """Test that emergency priority always interrupts"""
        # Create a behavior in progress
        behavior_id = "important_behavior"
        self.manager.preserve_behavior_state(
            behavior_id, "trading", {"partner": "merchant"}, progress=0.9
        )

        # Emergency should always interrupt
        should_interrupt = self.manager.should_interrupt(
            behavior_id,
            InterruptPriority.EMERGENCY,
            InterruptReason.HEALTH_CRITICAL,
            {"health": 5},
        )

        assert should_interrupt

    def test_should_interrupt_progress_factor(self):
        """Test that progress affects interrupt decisions"""
        behavior_id = "progress_behavior"

        # High progress behavior should be harder to interrupt
        self.manager.preserve_behavior_state(
            behavior_id, "crafting", {"item": "sword"}, progress=0.95
        )

        # Test multiple times due to randomness
        interrupt_count = 0
        for _ in range(20):
            if self.manager.should_interrupt(
                behavior_id,
                InterruptPriority.NORMAL,
                InterruptReason.EXTERNAL_REQUEST,
                {},
            ):
                interrupt_count += 1

        # High progress should result in fewer interrupts
        assert interrupt_count < 15  # Should be less than 75% due to high progress

    def test_preserve_behavior_state(self):
        """Test behavior state preservation"""
        behavior_id = "test_behavior"
        state_data = {"target": "gold_ore", "tools": ["pickaxe"]}

        preserved_state = self.manager.preserve_behavior_state(
            behavior_id,
            "mining",
            state_data,
            progress=0.4,
            context={"location": (25, 30)},
            success_probability=0.85,
        )

        assert preserved_state.behavior_id == behavior_id
        assert preserved_state.behavior_type == "mining"
        assert preserved_state.state_data == state_data
        assert preserved_state.progress == 0.4
        assert preserved_state.success_probability == 0.85

        # Check it's stored in the manager
        assert behavior_id in self.manager.preserved_behaviors

    def test_preserve_behavior_state_update_existing(self):
        """Test updating existing preserved behavior state"""
        behavior_id = "update_test"

        # Initial preservation
        initial_state = self.manager.preserve_behavior_state(
            behavior_id, "exploration", {"explored_tiles": 5}, progress=0.3
        )

        # Update the same behavior
        updated_state = self.manager.preserve_behavior_state(
            behavior_id, "exploration", {"explored_tiles": 8}, progress=0.6
        )

        # Should be the same object, updated
        assert initial_state is updated_state
        assert updated_state.state_data["explored_tiles"] == 8
        assert updated_state.progress == 0.6

    def test_interrupt_behavior(self):
        """Test behavior interruption"""
        behavior_id = "interrupted_behavior"
        self.manager.preserve_behavior_state(
            behavior_id, "trading", {"partner": "merchant"}, progress=0.5
        )

        interrupt_event = self.manager.interrupt_behavior(
            behavior_id,
            InterruptPriority.CRITICAL,
            InterruptReason.UNDER_ATTACK,
            context={"attacker": "bandit"},
        )

        assert interrupt_event.interrupted_behavior_id == behavior_id
        assert interrupt_event.priority == InterruptPriority.CRITICAL
        assert interrupt_event.reason == InterruptReason.UNDER_ATTACK

        # Check tracking
        assert len(self.manager.interrupt_stack) == 1
        assert interrupt_event.interrupt_id in self.manager.active_interrupts
        assert len(self.manager.interrupt_history) == 1
        assert self.manager.stats["total_interrupts"] == 1

    def test_can_resume_behavior_valid(self):
        """Test can resume behavior with valid conditions"""
        behavior_id = "resumable_behavior"
        self.manager.preserve_behavior_state(
            behavior_id,
            "gathering",
            {"resource": "wood"},
            progress=0.6,
            context={"required_resources": ["axe"]},
            success_probability=0.8,
        )

        current_context = {"has_axe": True}
        can_resume, reason = self.manager.can_resume_behavior(
            behavior_id, current_context
        )

        assert can_resume
        assert reason == "Can resume"

    def test_can_resume_behavior_missing_resources(self):
        """Test can resume behavior with missing resources"""
        behavior_id = "resource_dependent"
        self.manager.preserve_behavior_state(
            behavior_id,
            "crafting",
            {"item": "bow"},
            progress=0.3,
            context={"required_resources": ["string", "wood"]},
            success_probability=0.9,
        )

        current_context = {"has_string": True, "has_wood": False}
        can_resume, reason = self.manager.can_resume_behavior(
            behavior_id, current_context
        )

        assert not can_resume
        assert "wood" in reason

    def test_can_resume_behavior_low_success_probability(self):
        """Test can resume behavior with low success probability"""
        behavior_id = "failing_behavior"
        self.manager.preserve_behavior_state(
            behavior_id,
            "combat",
            {"enemy": "dragon"},
            progress=0.1,
            success_probability=0.2,  # Very low
        )

        can_resume, reason = self.manager.can_resume_behavior(behavior_id, {})

        assert not can_resume
        assert "Low success probability" in reason

    def test_can_resume_behavior_too_old(self):
        """Test can resume behavior that's too old"""
        behavior_id = "old_behavior"
        old_time = time.time() - 4000  # More than 1 hour ago

        state = BehaviorState(
            behavior_id=behavior_id,
            behavior_type="exploration",
            state_data={},
            progress=0.5,
            context={},
            start_time=old_time,
            last_update_time=old_time,
        )

        self.manager.preserved_behaviors[behavior_id] = state

        can_resume, reason = self.manager.can_resume_behavior(behavior_id, {})

        assert not can_resume
        assert "too old" in reason

    def test_get_resumption_strategy_emergency(self):
        """Test resumption strategy for emergency interrupts"""
        behavior_id = "emergency_test"
        self.manager.preserve_behavior_state(behavior_id, "trading", {}, progress=0.5)

        interrupt_event = InterruptEvent(
            interrupt_id="emergency",
            priority=InterruptPriority.EMERGENCY,
            reason=InterruptReason.HEALTH_CRITICAL,
            interrupted_behavior_id=behavior_id,
            interrupt_time=time.time(),
        )

        strategy = self.manager.get_resumption_strategy(behavior_id, interrupt_event)
        assert strategy == ResumptionStrategy.RESUME_WITH_DELAY

    def test_get_resumption_strategy_high_progress(self):
        """Test resumption strategy for high progress behaviors"""
        behavior_id = "high_progress"
        self.manager.preserve_behavior_state(
            behavior_id, "crafting", {}, progress=0.9  # Very high progress
        )

        interrupt_event = InterruptEvent(
            interrupt_id="normal",
            priority=InterruptPriority.NORMAL,
            reason=InterruptReason.EXTERNAL_REQUEST,
            interrupted_behavior_id=behavior_id,
            interrupt_time=time.time(),
        )

        strategy = self.manager.get_resumption_strategy(behavior_id, interrupt_event)
        assert strategy == ResumptionStrategy.RESUME_IMMEDIATELY

    def test_get_resumption_strategy_low_progress(self):
        """Test resumption strategy for low progress behaviors"""
        behavior_id = "low_progress"
        self.manager.preserve_behavior_state(
            behavior_id, "exploration", {}, progress=0.1  # Very low progress
        )

        interrupt_event = InterruptEvent(
            interrupt_id="normal",
            priority=InterruptPriority.NORMAL,
            reason=InterruptReason.EXTERNAL_REQUEST,
            interrupted_behavior_id=behavior_id,
            interrupt_time=time.time(),
        )

        strategy = self.manager.get_resumption_strategy(behavior_id, interrupt_event)
        assert strategy == ResumptionStrategy.RESTART_FROM_BEGINNING

    def test_resume_behavior_success(self):
        """Test successful behavior resumption"""
        behavior_id = "resume_test"
        self.manager.preserve_behavior_state(
            behavior_id, "gathering", {"collected": 3}, progress=0.6
        )

        # Create and resolve an interrupt
        interrupt_event = self.manager.interrupt_behavior(
            behavior_id, InterruptPriority.NORMAL, InterruptReason.EXTERNAL_REQUEST
        )

        # Resume behavior
        success, state, message = self.manager.resume_behavior(behavior_id)

        assert success
        assert state is not None
        assert state.behavior_id == behavior_id
        assert "successfully" in message.lower()

        # Check statistics
        assert self.manager.stats["successful_resumptions"] == 1

    def test_resume_behavior_not_found(self):
        """Test resuming non-existent behavior"""
        success, state, message = self.manager.resume_behavior("nonexistent")

        assert not success
        assert state is None
        assert "not found" in message

    def test_resume_behavior_abandon_strategy(self):
        """Test resuming behavior with abandon strategy"""
        behavior_id = "abandon_test"
        self.manager.preserve_behavior_state(
            behavior_id, "exploration", {}, progress=0.2
        )

        # Force abandon strategy
        success, state, message = self.manager.resume_behavior(
            behavior_id, force_strategy=ResumptionStrategy.ABANDON_GRACEFULLY
        )

        assert not success
        assert state is None
        assert "abandoned" in message.lower()

        # Behavior should be removed
        assert behavior_id not in self.manager.preserved_behaviors
        assert self.manager.stats["abandoned_behaviors"] == 1

    def test_resume_behavior_restart_strategy(self):
        """Test resuming behavior with restart strategy"""
        behavior_id = "restart_test"
        original_state = self.manager.preserve_behavior_state(
            behavior_id, "crafting", {"materials": ["iron"]}, progress=0.4
        )
        original_state.execution_count = 5

        # Force restart strategy
        success, state, message = self.manager.resume_behavior(
            behavior_id, force_strategy=ResumptionStrategy.RESTART_FROM_BEGINNING
        )

        assert success
        assert state.progress == 0.0
        assert state.execution_count == 0
        assert len(state.state_data) == 0  # Should be cleared

    def test_get_next_behavior_to_resume(self):
        """Test getting next behavior to resume"""
        # Create multiple behaviors with different priorities
        self.manager.preserve_behavior_state(
            "low_priority", "exploration", {}, progress=0.2, success_probability=0.6
        )

        self.manager.preserve_behavior_state(
            "high_priority", "crafting", {}, progress=0.8, success_probability=0.9
        )

        self.manager.preserve_behavior_state(
            "medium_priority", "trading", {}, progress=0.5, success_probability=0.7
        )

        # Get next behavior to resume
        result = self.manager.get_next_behavior_to_resume({})

        assert result is not None
        behavior_id, behavior_state = result

        # Should prioritize high progress, high success probability behavior
        assert behavior_id == "high_priority"

    def test_get_next_behavior_to_resume_no_candidates(self):
        """Test getting next behavior when none can be resumed"""
        # Create behavior that can't be resumed (missing resources)
        self.manager.preserve_behavior_state(
            "blocked_behavior",
            "crafting",
            {},
            progress=0.5,
            context={"required_resources": ["rare_material"]},
        )

        # Context doesn't have required resource
        result = self.manager.get_next_behavior_to_resume({"has_common_material": True})

        assert result is None

    def test_resolve_interrupt(self):
        """Test manual interrupt resolution"""
        behavior_id = "resolve_test"
        interrupt_event = self.manager.interrupt_behavior(
            behavior_id, InterruptPriority.NORMAL, InterruptReason.EXTERNAL_REQUEST
        )

        interrupt_id = interrupt_event.interrupt_id
        assert interrupt_id in self.manager.active_interrupts

        # Resolve the interrupt
        success = self.manager.resolve_interrupt(
            interrupt_id, ResumptionStrategy.RESUME_WHEN_OPTIMAL
        )

        assert success
        assert interrupt_id not in self.manager.active_interrupts

        # Check that the event was marked as resolved
        assert interrupt_event.resolved
        assert (
            interrupt_event.resumption_strategy
            == ResumptionStrategy.RESUME_WHEN_OPTIMAL
        )

    def test_resolve_interrupt_not_found(self):
        """Test resolving non-existent interrupt"""
        success = self.manager.resolve_interrupt("nonexistent_interrupt")
        assert not success

    def test_periodic_cleanup(self):
        """Test periodic cleanup functionality"""
        # Temporarily increase max capacity to avoid immediate cleanup
        original_max = self.manager.max_preserved_behaviors
        self.manager.max_preserved_behaviors = 15

        # Add more behaviors than original max capacity
        for i in range(10):  # More than original max_preserved_behaviors (5)
            self.manager.preserve_behavior_state(
                f"behavior_{i}", "test", {}, progress=i * 0.1
            )

        assert len(self.manager.preserved_behaviors) == 10

        # Restore original max capacity
        self.manager.max_preserved_behaviors = original_max

        # Force cleanup
        self.manager.last_cleanup = time.time() - 400  # Force cleanup
        self.manager.periodic_cleanup()

        # Should be reduced to max capacity
        assert (
            len(self.manager.preserved_behaviors)
            <= self.manager.max_preserved_behaviors
        )

    def test_context_factor_calculation_under_attack(self):
        """Test context factor calculation for under attack scenario"""
        current_behavior = BehaviorState(
            "test", "gathering", {}, 0.5, {}, time.time(), time.time()
        )

        # High threat scenario
        high_threat_context = {"health_percentage": 20.0, "attacker_count": 3}

        factor = self.manager._calculate_context_factor(
            InterruptReason.UNDER_ATTACK, high_threat_context, current_behavior
        )

        assert factor > 1.0  # Should increase interrupt likelihood

        # Low threat scenario
        low_threat_context = {"health_percentage": 80.0, "attacker_count": 1}

        low_factor = self.manager._calculate_context_factor(
            InterruptReason.UNDER_ATTACK, low_threat_context, current_behavior
        )

        assert low_factor < factor  # Should be lower than high threat

    def test_context_factor_calculation_better_opportunity(self):
        """Test context factor calculation for better opportunity"""
        current_behavior = BehaviorState(
            "test",
            "gathering",
            {},
            0.5,
            {"expected_value": 10.0},
            time.time(),
            time.time(),
        )

        # Much better opportunity
        context = {"opportunity_value": 50.0}
        factor = self.manager._calculate_context_factor(
            InterruptReason.BETTER_OPPORTUNITY, context, current_behavior
        )

        assert factor > 2.0  # Should strongly favor interruption

        # Slightly better opportunity
        context = {"opportunity_value": 12.0}
        small_factor = self.manager._calculate_context_factor(
            InterruptReason.BETTER_OPPORTUNITY, context, current_behavior
        )

        assert small_factor < factor  # Should be less compelling

    def test_get_interrupt_statistics(self):
        """Test interrupt statistics generation"""
        # Create some test data
        self.manager.preserve_behavior_state("test1", "exploration", {}, 0.3)
        self.manager.preserve_behavior_state("test2", "trading", {}, 0.7)

        interrupt_event = self.manager.interrupt_behavior(
            "test1", InterruptPriority.NORMAL, InterruptReason.EXTERNAL_REQUEST
        )

        stats = self.manager.get_interrupt_statistics()

        assert stats["total_interrupts"] == 1
        assert stats["active_interrupts"] == 1
        assert stats["preserved_behaviors"] == 2
        assert "interrupt_reasons" in stats
        assert stats["interrupt_reasons"]["external_request"] == 1

    def test_get_behavior_state_summary(self):
        """Test behavior state summary generation"""
        behavior_id = "summary_test"
        self.manager.preserve_behavior_state(
            behavior_id,
            "crafting",
            {"item": "sword"},
            progress=0.6,
            success_probability=0.85,
        )

        # Add an interrupt
        self.manager.interrupt_behavior(
            behavior_id, InterruptPriority.NORMAL, InterruptReason.RESOURCE_DEPLETED
        )

        summary = self.manager.get_behavior_state_summary(behavior_id)

        assert summary is not None
        assert summary["behavior_id"] == behavior_id
        assert summary["behavior_type"] == "crafting"
        assert summary["progress"] == 0.6
        assert summary["success_probability"] == 0.85
        assert summary["interrupt_count"] == 1
        assert summary["last_interrupt_reason"] == "resource_depleted"

    def test_get_behavior_state_summary_not_found(self):
        """Test behavior state summary for non-existent behavior"""
        summary = self.manager.get_behavior_state_summary("nonexistent")
        assert summary is None

    def test_interrupt_priority_ordering(self):
        """Test that interrupt priorities are correctly ordered"""
        priorities = [
            InterruptPriority.EMERGENCY,
            InterruptPriority.CRITICAL,
            InterruptPriority.URGENT,
            InterruptPriority.HIGH,
            InterruptPriority.NORMAL,
            InterruptPriority.LOW,
        ]

        # Check that values are in descending order
        for i in range(len(priorities) - 1):
            assert priorities[i].value > priorities[i + 1].value

    def test_behavior_resumption_success_tracking(self):
        """Test that behavior resumption success is tracked"""
        behavior_type = "test_behavior"

        # Add some success/failure data
        self.manager.behavior_resumption_success[behavior_type] = [
            True,
            True,
            False,
            True,
        ]

        # Get statistics
        stats = self.manager.get_interrupt_statistics()
        success_rates = stats["resumption_success_rates"]

        assert behavior_type in success_rates
        assert success_rates[behavior_type] == 0.75  # 3 out of 4 successful

    def test_multiple_interrupts_same_behavior(self):
        """Test multiple interrupts on the same behavior"""
        behavior_id = "multi_interrupt"
        self.manager.preserve_behavior_state(behavior_id, "trading", {}, progress=0.4)

        # First interrupt
        interrupt1 = self.manager.interrupt_behavior(
            behavior_id, InterruptPriority.NORMAL, InterruptReason.EXTERNAL_REQUEST
        )

        # Second interrupt (higher priority)
        interrupt2 = self.manager.interrupt_behavior(
            behavior_id, InterruptPriority.CRITICAL, InterruptReason.UNDER_ATTACK
        )

        # Both should be tracked
        assert len(self.manager.interrupt_stack) == 2
        assert len(self.manager.active_interrupts) == 2

        # Most recent should be first in stack
        assert self.manager.interrupt_stack[0] == interrupt2
        assert self.manager.interrupt_stack[1] == interrupt1


class TestInterruptIntegration:
    """Test interrupt system integration scenarios"""

    def setup_method(self):
        """Set up test fixtures"""
        self.manager = InterruptManager()

    def test_combat_interrupt_scenario(self):
        """Test complete combat interrupt scenario"""
        # Agent is gathering resources
        gathering_id = "peaceful_gathering"
        self.manager.preserve_behavior_state(
            gathering_id,
            "resource_gathering",
            {"resource": "wood", "collected": 5, "target": 10},
            progress=0.5,
            success_probability=0.9,
        )

        # Suddenly under attack!
        attack_context = {
            "health_percentage": 60.0,
            "attacker_count": 2,
            "attacker_types": ["bandit", "wolf"],
        }

        # Should definitely interrupt
        should_interrupt = self.manager.should_interrupt(
            gathering_id,
            InterruptPriority.CRITICAL,
            InterruptReason.UNDER_ATTACK,
            attack_context,
        )

        assert should_interrupt

        # Interrupt the gathering
        interrupt_event = self.manager.interrupt_behavior(
            gathering_id,
            InterruptPriority.CRITICAL,
            InterruptReason.UNDER_ATTACK,
            context=attack_context,
        )

        # Combat ensues... eventually resolved
        interrupt_event.resolve(ResumptionStrategy.RESUME_WHEN_OPTIMAL)

        # Later, try to resume gathering
        safe_context = {"health_percentage": 90.0, "enemies_nearby": False}
        can_resume, reason = self.manager.can_resume_behavior(
            gathering_id, safe_context
        )

        assert can_resume

        # Resume the behavior
        success, state, message = self.manager.resume_behavior(gathering_id)
        assert success
        assert state.state_data["collected"] == 5  # Progress preserved
        assert state.progress == 0.5

    def test_resource_depletion_scenario(self):
        """Test resource depletion interrupt scenario"""
        # Agent is mining iron
        mining_id = "iron_mining"
        self.manager.preserve_behavior_state(
            mining_id,
            "mining",
            {"resource": "iron", "location": (30, 40), "ore_remaining": 0},
            progress=0.8,
            context={"target_resource": "iron"},
        )

        # Resource gets depleted
        depletion_context = {"resource_type": "iron", "location": (30, 40)}

        # Should interrupt because resource depleted
        should_interrupt = self.manager.should_interrupt(
            mining_id,
            InterruptPriority.HIGH,
            InterruptReason.RESOURCE_DEPLETED,
            depletion_context,
        )

        # Context factor should be high because target resource matches depleted resource
        assert should_interrupt

        # Interrupt the mining
        interrupt_event = self.manager.interrupt_behavior(
            mining_id,
            InterruptPriority.HIGH,
            InterruptReason.RESOURCE_DEPLETED,
            context=depletion_context,
        )

        # Strategy should be to abandon since resource is gone
        strategy = self.manager.get_resumption_strategy(mining_id, interrupt_event)
        assert strategy in [
            ResumptionStrategy.ABANDON_GRACEFULLY,
            ResumptionStrategy.REEVALUATE_NECESSITY,
        ]

    def test_opportunity_interrupt_scenario(self):
        """Test better opportunity interrupt scenario"""
        # Agent is doing routine exploration
        exploration_id = "routine_exploration"
        self.manager.preserve_behavior_state(
            exploration_id,
            "exploration",
            {"area": "forest", "tiles_explored": 20},
            progress=0.3,
            context={"expected_value": 5.0},
        )

        # Rare resource discovered nearby!
        opportunity_context = {
            "opportunity_value": 25.0,  # Much higher than current expected value
            "resource_type": "rare_gems",
            "distance": 50.0,
        }

        # Should likely interrupt for this great opportunity
        should_interrupt = self.manager.should_interrupt(
            exploration_id,
            InterruptPriority.URGENT,
            InterruptReason.BETTER_OPPORTUNITY,
            opportunity_context,
        )

        # May or may not interrupt due to randomness, but context factor should be high
        context_factor = self.manager._calculate_context_factor(
            InterruptReason.BETTER_OPPORTUNITY,
            opportunity_context,
            self.manager.preserved_behaviors[exploration_id],
        )

        assert context_factor > 2.0  # Much better opportunity

    def test_time_limit_exceeded_scenario(self):
        """Test time limit exceeded interrupt scenario"""
        # Agent is crafting something with a deadline
        crafting_id = "urgent_crafting"
        start_time = time.time() - 600  # Started 10 minutes ago

        crafting_state = BehaviorState(
            behavior_id=crafting_id,
            behavior_type="crafting",
            state_data={"item": "emergency_supplies", "completion_time": 300},
            progress=0.7,
            context={"deadline": start_time + 300},  # 5 minute deadline
            start_time=start_time,
            last_update_time=time.time() - 60,
        )

        self.manager.preserved_behaviors[crafting_id] = crafting_state

        # Time limit exceeded
        timeout_context = {
            "time_exceeded_seconds": 300,  # 5 minutes over deadline
            "original_deadline": start_time + 300,
        }

        # Should interrupt due to time limit
        should_interrupt = self.manager.should_interrupt(
            crafting_id,
            InterruptPriority.HIGH,
            InterruptReason.TIME_LIMIT_EXCEEDED,
            timeout_context,
        )

        # Context factor should increase with time exceeded
        context_factor = self.manager._calculate_context_factor(
            InterruptReason.TIME_LIMIT_EXCEEDED, timeout_context, crafting_state
        )

        assert context_factor > 1.0


if __name__ == "__main__":
    pytest.main([__file__])
