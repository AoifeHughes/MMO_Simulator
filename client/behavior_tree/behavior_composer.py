"""
Behavior Composer System

This module enables dynamic behavior composition for agents, allowing them to:
- Combine behavior fragments based on context and personality
- Transition smoothly between different behavior patterns
- Resolve conflicts when multiple behaviors compete
- Adapt behavior trees at runtime based on changing conditions
"""

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .interrupt_manager import (
    InterruptManager,
    InterruptPriority,
    InterruptReason,
    ResumptionStrategy,
)
from .nodes.action import ActionNode
from .nodes.base import BehaviorNode, NodeStatus
from .utility_selector import UtilityFunction, UtilitySelector

logger = logging.getLogger(__name__)


class _SimpleActionNode(ActionNode):
    """Simple concrete ActionNode implementation for behavior composition testing"""

    def __init__(self, name: str):
        super().__init__(name)

    def start_action(self, agent):
        """Simple start action implementation"""
        return True

    def stop_action(self, agent):
        """Simple stop action implementation"""
        pass

    def update_action(self, agent, delta_time: float = 0.0):
        """Simple update action implementation"""
        return NodeStatus.SUCCESS


class BehaviorFragmentType(Enum):
    """Types of behavior fragments"""

    MOVEMENT = "movement"
    COMBAT = "combat"
    RESOURCE_GATHERING = "resource_gathering"
    SOCIAL = "social"
    TRADING = "trading"
    EXPLORATION = "exploration"
    SURVIVAL = "survival"
    CRAFTING = "crafting"


class BehaviorPriority(Enum):
    """Priority levels for behavior fragments"""

    EMERGENCY = 5  # Life-threatening situations
    URGENT = 4  # Important immediate needs
    HIGH = 3  # High priority tasks
    NORMAL = 2  # Standard activities
    LOW = 1  # Optional activities
    BACKGROUND = 0  # Passive behaviors


@dataclass
class BehaviorFragment:
    """A reusable behavior fragment that can be composed into larger behaviors"""

    fragment_id: str
    fragment_type: BehaviorFragmentType
    priority: BehaviorPriority
    node: BehaviorNode

    # Composition metadata
    required_context: Set[str] = field(default_factory=set)
    conflicting_fragments: Set[str] = field(default_factory=set)
    prerequisites: Set[str] = field(default_factory=set)

    # Activation conditions
    personality_weights: Dict[str, float] = field(default_factory=dict)
    context_requirements: Dict[str, Any] = field(default_factory=dict)
    cooldown_duration: float = 0.0

    # Runtime state
    last_activation: float = 0.0
    activation_count: int = 0
    success_rate: float = 1.0

    def can_activate(self, agent, context_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if this fragment can be activated given current conditions"""
        current_time = time.time()

        # Check cooldown
        if current_time - self.last_activation < self.cooldown_duration:
            remaining = self.cooldown_duration - (current_time - self.last_activation)
            return False, f"Fragment on cooldown for {remaining:.1f}s"

        # Check required context
        for req in self.required_context:
            if req not in context_data:
                return False, f"Missing required context: {req}"

        # Check context requirements
        for key, required_value in self.context_requirements.items():
            actual_value = context_data.get(key)
            if actual_value != required_value:
                return (
                    False,
                    f"Context requirement not met: {key} = {actual_value}, required = {required_value}",
                )

        # Check personality compatibility
        if hasattr(agent, "personality") and self.personality_weights:
            for trait, weight in self.personality_weights.items():
                if hasattr(agent.personality, trait):
                    trait_value = getattr(agent.personality, trait)
                    if weight > 0:
                        # Higher weights require higher trait values
                        # weight 0.1-0.3: requires >= 2.0
                        # weight 0.4-0.6: requires >= 5.0
                        # weight 0.7-1.0: requires >= 8.0
                        required_value = (
                            2.0 if weight < 0.4 else (5.0 if weight < 0.7 else 8.0)
                        )
                        if trait_value < required_value:
                            return (
                                False,
                                f"Insufficient {trait} trait: {trait_value} < {required_value}",
                            )
                    elif (
                        weight < 0 and trait_value > 7.0
                    ):  # Negative weight requires low trait value
                        return False, f"Excessive {trait} trait: {trait_value} > 7.0"

        return True, "Fragment can activate"

    def calculate_utility(self, agent, context_data: Dict[str, Any]) -> float:
        """Calculate utility score for activating this fragment"""
        can_activate, _ = self.can_activate(agent, context_data)
        if not can_activate:
            return 0.0

        base_utility = float(self.priority.value) * 10.0

        # Personality influence
        personality_modifier = 1.0
        if hasattr(agent, "personality") and self.personality_weights:
            for trait, weight in self.personality_weights.items():
                if hasattr(agent.personality, trait):
                    trait_value = getattr(agent.personality, trait)
                    # Normalize trait value (0-10) to modifier (0.5-1.5)
                    normalized = trait_value / 10.0
                    personality_modifier *= 1.0 + weight * normalized

        # Success rate influence
        success_modifier = 0.5 + (self.success_rate * 0.5)  # 0.5 to 1.0

        # Recency bonus (prefer fragments not used recently)
        current_time = time.time()
        time_since_use = current_time - self.last_activation
        recency_bonus = min(1.0, time_since_use / 60.0)  # Full bonus after 1 minute

        # Memory-based modifiers
        memory_modifier = 1.0
        if hasattr(agent, "memory") and agent.memory:
            # Location-based memory modifier
            if hasattr(agent, "x") and hasattr(agent, "y"):
                memory_modifier *= agent.memory.calculate_location_utility_modifier(
                    agent.x, agent.y, self._get_action_type()
                )

            # Social memory modifier for social fragments
            if self.fragment_type.value in ["social", "trading"] and context_data.get(
                "target_agent_id"
            ):
                target_id = context_data["target_agent_id"]
                memory_modifier *= agent.memory.calculate_social_utility_modifier(
                    target_id, self._get_action_type()
                )

        final_utility = (
            base_utility
            * personality_modifier
            * success_modifier
            * (1.0 + recency_bonus)
            * memory_modifier
        )
        return max(0.0, final_utility)

    def _get_action_type(self) -> str:
        """Get action type string for memory system integration"""
        fragment_to_action = {
            BehaviorFragmentType.MOVEMENT: "movement",
            BehaviorFragmentType.COMBAT: "attack",
            BehaviorFragmentType.RESOURCE_GATHERING: "gather_resources",
            BehaviorFragmentType.SOCIAL: "cooperate",
            BehaviorFragmentType.TRADING: "trade",
            BehaviorFragmentType.EXPLORATION: "explore",
            BehaviorFragmentType.SURVIVAL: "survival",
            BehaviorFragmentType.CRAFTING: "crafting",
        }
        return fragment_to_action.get(self.fragment_type, "unknown")

    def activate(self):
        """Mark fragment as activated"""
        self.last_activation = time.time()
        self.activation_count += 1

    def update_success_rate(self, success: bool):
        """Update success rate based on execution result"""
        # Exponential moving average
        alpha = 0.1
        new_rate = 1.0 if success else 0.0
        self.success_rate = (1 - alpha) * self.success_rate + alpha * new_rate


class BehaviorTemplate:
    """Template for creating behavior compositions"""

    def __init__(self, template_id: str, name: str):
        self.template_id = template_id
        self.name = name
        self.fragment_slots: Dict[str, BehaviorFragmentType] = {}
        self.composition_rules: List[str] = []
        self.root_structure: Optional[Dict[str, Any]] = None

    def add_slot(self, slot_name: str, fragment_type: BehaviorFragmentType):
        """Add a slot for a specific type of behavior fragment"""
        self.fragment_slots[slot_name] = fragment_type

    def add_rule(self, rule: str):
        """Add a composition rule (e.g., 'movement OR combat', 'resource_gathering AND NOT social')"""
        self.composition_rules.append(rule)

    def set_structure(self, structure: Dict[str, Any]):
        """Set the root structure for composing fragments"""
        self.root_structure = structure


class BehaviorComposer:
    """Main behavior composition system"""

    def __init__(self):
        self.fragment_library: Dict[str, BehaviorFragment] = {}
        self.templates: Dict[str, BehaviorTemplate] = {}
        self.active_compositions: Dict[
            str, "BehaviorComposition"
        ] = {}  # agent_id -> composition

        # Interrupt management
        self.interrupt_manager = InterruptManager()

        # Conflict resolution settings
        self.max_concurrent_fragments = 3
        self.conflict_resolution_strategy = (
            "priority"  # "priority", "utility", "personality"
        )

        # Performance tracking
        self.composition_stats = {
            "total_compositions": 0,
            "successful_transitions": 0,
            "conflict_resolutions": 0,
            "fragment_activations": defaultdict(int),
        }

        self._initialize_default_fragments()
        self._initialize_default_templates()

    def _initialize_default_fragments(self):
        """Initialize default behavior fragments"""
        # Movement fragments
        self.register_fragment(
            BehaviorFragment(
                fragment_id="basic_movement",
                fragment_type=BehaviorFragmentType.MOVEMENT,
                priority=BehaviorPriority.NORMAL,
                node=self._create_movement_node(),
                required_context={"target_position"},
                personality_weights={"exploration": 0.2},
            )
        )

        self.register_fragment(
            BehaviorFragment(
                fragment_id="evasive_movement",
                fragment_type=BehaviorFragmentType.MOVEMENT,
                priority=BehaviorPriority.HIGH,
                node=self._create_evasive_movement_node(),
                required_context={"danger_source", "target_position"},
                conflicting_fragments={"basic_movement"},
                personality_weights={"combat": -0.3, "exploration": 0.1},
            )
        )

        # Combat fragments
        self.register_fragment(
            BehaviorFragment(
                fragment_id="aggressive_combat",
                fragment_type=BehaviorFragmentType.COMBAT,
                priority=BehaviorPriority.HIGH,
                node=self._create_aggressive_combat_node(),
                required_context={"enemy_target"},
                personality_weights={"combat": 0.5},
                cooldown_duration=2.0,
            )
        )

        self.register_fragment(
            BehaviorFragment(
                fragment_id="defensive_combat",
                fragment_type=BehaviorFragmentType.COMBAT,
                priority=BehaviorPriority.NORMAL,
                node=self._create_defensive_combat_node(),
                required_context={"enemy_target"},
                conflicting_fragments={"aggressive_combat"},
                personality_weights={"combat": -0.2},
            )
        )

        # Resource gathering fragments
        self.register_fragment(
            BehaviorFragment(
                fragment_id="efficient_gathering",
                fragment_type=BehaviorFragmentType.RESOURCE_GATHERING,
                priority=BehaviorPriority.NORMAL,
                node=self._create_efficient_gathering_node(),
                required_context={"resource_target"},
                personality_weights={"foraging": 0.3, "fishing": 0.3},
            )
        )

        # Social fragments
        self.register_fragment(
            BehaviorFragment(
                fragment_id="cooperative_behavior",
                fragment_type=BehaviorFragmentType.SOCIAL,
                priority=BehaviorPriority.NORMAL,
                node=self._create_cooperative_node(),
                required_context={"nearby_allies"},
                personality_weights={"social": 0.4, "cooperativeness": 0.3},
            )
        )

        # Trading fragments
        self.register_fragment(
            BehaviorFragment(
                fragment_id="active_trading",
                fragment_type=BehaviorFragmentType.TRADING,
                priority=BehaviorPriority.NORMAL,
                node=self._create_active_trading_node(),
                required_context={"trade_opportunities"},
                personality_weights={"money": 0.4, "social": 0.2},
            )
        )

    def _initialize_default_templates(self):
        """Initialize default behavior templates"""
        # Balanced explorer template
        explorer_template = BehaviorTemplate("balanced_explorer", "Balanced Explorer")
        explorer_template.add_slot("movement", BehaviorFragmentType.MOVEMENT)
        explorer_template.add_slot("resource", BehaviorFragmentType.RESOURCE_GATHERING)
        explorer_template.add_slot("social", BehaviorFragmentType.SOCIAL)
        explorer_template.add_rule("movement REQUIRED")
        explorer_template.add_rule("resource OR social")
        self.register_template(explorer_template)

        # Combat specialist template
        combat_template = BehaviorTemplate("combat_specialist", "Combat Specialist")
        combat_template.add_slot("movement", BehaviorFragmentType.MOVEMENT)
        combat_template.add_slot("combat", BehaviorFragmentType.COMBAT)
        combat_template.add_rule("combat REQUIRED")
        combat_template.add_rule("movement AND combat")
        self.register_template(combat_template)

        # Trader template
        trader_template = BehaviorTemplate("trader", "Trading Specialist")
        trader_template.add_slot("movement", BehaviorFragmentType.MOVEMENT)
        trader_template.add_slot("trading", BehaviorFragmentType.TRADING)
        trader_template.add_slot("social", BehaviorFragmentType.SOCIAL)
        trader_template.add_rule("trading REQUIRED")
        trader_template.add_rule("social PREFERRED")
        self.register_template(trader_template)

    def register_fragment(self, fragment: BehaviorFragment):
        """Register a behavior fragment in the library"""
        self.fragment_library[fragment.fragment_id] = fragment
        logger.debug(f"Registered behavior fragment: {fragment.fragment_id}")

    def register_template(self, template: BehaviorTemplate):
        """Register a behavior template"""
        self.templates[template.template_id] = template
        logger.debug(f"Registered behavior template: {template.template_id}")

    def compose_behavior(
        self, agent, context_data: Dict[str, Any], template_id: Optional[str] = None
    ) -> "BehaviorComposition":
        """Compose a behavior for an agent based on context and personality"""
        # Select template
        if template_id:
            template = self.templates.get(template_id)
        else:
            template = self._select_best_template(agent, context_data)

        if not template:
            template = self.templates.get("balanced_explorer")  # Fallback

        # Select fragments for each slot
        selected_fragments = {}
        for slot_name, fragment_type in template.fragment_slots.items():
            fragment = self._select_best_fragment(agent, context_data, fragment_type)
            if fragment:
                selected_fragments[slot_name] = fragment

        # Resolve conflicts
        resolved_fragments = self._resolve_conflicts(
            selected_fragments, agent, context_data
        )

        # Create composition
        composition = BehaviorComposition(
            composition_id=f"{agent.id}_{int(time.time())}",
            agent_id=agent.id,
            template=template,
            fragments=resolved_fragments,
            creation_time=time.time(),
        )

        # Build behavior tree
        root_node = self._build_behavior_tree(composition, context_data)
        composition.root_node = root_node

        # Track composition
        self.active_compositions[agent.id] = composition
        self.composition_stats["total_compositions"] += 1

        logger.info(
            f"Composed behavior for {agent.id} using template {template.template_id} with {len(resolved_fragments)} fragments"
        )
        return composition

    def update_composition(self, agent, context_data: Dict[str, Any]) -> bool:
        """Update existing composition or create new one if needed"""
        current_composition = self.active_compositions.get(agent.id)

        if not current_composition:
            self.compose_behavior(agent, context_data)
            return True

        # Check if current composition is still valid
        if self._should_recompose(current_composition, agent, context_data):
            new_composition = self.compose_behavior(agent, context_data)
            self._transition_behavior(current_composition, new_composition, agent)
            self.composition_stats["successful_transitions"] += 1
            return True

        return False

    def _select_best_template(
        self, agent, context_data: Dict[str, Any]
    ) -> Optional[BehaviorTemplate]:
        """Select the best template based on agent personality and context"""
        if not hasattr(agent, "personality"):
            return self.templates.get("balanced_explorer")

        personality = agent.personality

        # Simple template selection based on dominant personality traits
        if personality.combat > 7.0:
            return self.templates.get("combat_specialist")
        elif personality.money > 7.0 or personality.social > 7.0:
            return self.templates.get("trader")
        else:
            return self.templates.get("balanced_explorer")

    def _select_best_fragment(
        self, agent, context_data: Dict[str, Any], fragment_type: BehaviorFragmentType
    ) -> Optional[BehaviorFragment]:
        """Select the best fragment of a given type"""
        candidates = [
            fragment
            for fragment in self.fragment_library.values()
            if fragment.fragment_type == fragment_type
        ]

        if not candidates:
            return None

        # Calculate utilities for all candidates
        fragment_utilities = []
        for fragment in candidates:
            can_activate, _ = fragment.can_activate(agent, context_data)
            if can_activate:
                utility = fragment.calculate_utility(agent, context_data)
                fragment_utilities.append((fragment, utility))

        if not fragment_utilities:
            return None

        # Select fragment with highest utility
        fragment_utilities.sort(key=lambda x: x[1], reverse=True)
        return fragment_utilities[0][0]

    def _resolve_conflicts(
        self,
        selected_fragments: Dict[str, BehaviorFragment],
        agent,
        context_data: Dict[str, Any],
    ) -> Dict[str, BehaviorFragment]:
        """Resolve conflicts between selected fragments"""
        resolved = {}
        conflicting_pairs = []

        # Identify conflicts
        for slot1, fragment1 in selected_fragments.items():
            for slot2, fragment2 in selected_fragments.items():
                if (
                    slot1 != slot2
                    and fragment1.fragment_id in fragment2.conflicting_fragments
                ):
                    conflicting_pairs.append((slot1, fragment1, slot2, fragment2))

        if not conflicting_pairs:
            return selected_fragments

        # Resolve based on strategy
        self.composition_stats["conflict_resolutions"] += 1

        if self.conflict_resolution_strategy == "priority":
            return self._resolve_by_priority(selected_fragments, conflicting_pairs)
        elif self.conflict_resolution_strategy == "utility":
            return self._resolve_by_utility(
                selected_fragments, conflicting_pairs, agent, context_data
            )
        else:
            return self._resolve_by_personality(
                selected_fragments, conflicting_pairs, agent
            )

    def _resolve_by_priority(
        self, fragments: Dict[str, BehaviorFragment], conflicts: List[Tuple]
    ) -> Dict[str, BehaviorFragment]:
        """Resolve conflicts by priority level"""
        resolved = fragments.copy()

        for slot1, fragment1, slot2, fragment2 in conflicts:
            if fragment1.priority.value > fragment2.priority.value:
                if slot2 in resolved:
                    del resolved[slot2]
            else:
                if slot1 in resolved:
                    del resolved[slot1]

        return resolved

    def _resolve_by_utility(
        self,
        fragments: Dict[str, BehaviorFragment],
        conflicts: List[Tuple],
        agent,
        context_data: Dict[str, Any],
    ) -> Dict[str, BehaviorFragment]:
        """Resolve conflicts by utility score"""
        resolved = fragments.copy()

        for slot1, fragment1, slot2, fragment2 in conflicts:
            utility1 = fragment1.calculate_utility(agent, context_data)
            utility2 = fragment2.calculate_utility(agent, context_data)

            if utility1 > utility2:
                if slot2 in resolved:
                    del resolved[slot2]
            else:
                if slot1 in resolved:
                    del resolved[slot1]

        return resolved

    def _resolve_by_personality(
        self, fragments: Dict[str, BehaviorFragment], conflicts: List[Tuple], agent
    ) -> Dict[str, BehaviorFragment]:
        """Resolve conflicts based on agent personality preferences"""
        # Implementation would analyze personality weights and preferences
        # For now, fall back to priority-based resolution
        return self._resolve_by_priority(fragments, conflicts)

    def _build_behavior_tree(
        self, composition: "BehaviorComposition", context_data: Dict[str, Any]
    ) -> BehaviorNode:
        """Build the actual behavior tree from selected fragments"""
        if not composition.fragments:
            return self._create_fallback_node()

        # Collect all fragment nodes
        fragment_nodes = []
        for slot_name, fragment in composition.fragments.items():
            # Create utility function for this fragment
            utility_func = UtilityFunction(
                name=f"{fragment.fragment_id}_utility",
                base_utility=float(fragment.priority.value) * 10.0,
            )

            # Wrap fragment node with utility
            fragment.node.utility_function = utility_func
            fragment_nodes.append(fragment.node)

            # Mark fragment as activated
            fragment.activate()
            self.composition_stats["fragment_activations"][fragment.fragment_id] += 1

        # Create utility selector as root with all fragment nodes as children
        root = UtilitySelector("composed_behavior", fragment_nodes)

        return root

    def _should_recompose(
        self, composition: "BehaviorComposition", agent, context_data: Dict[str, Any]
    ) -> bool:
        """Check if behavior should be recomposed"""
        current_time = time.time()

        # Time-based recomposition (every 30 seconds)
        if current_time - composition.creation_time > 30.0:
            return True

        # Context-based recomposition
        # Check if new high-priority opportunities have appeared
        if "emergency" in context_data and context_data["emergency"]:
            return True

        # Check if current fragments are no longer valid
        for fragment in composition.fragments.values():
            can_activate, _ = fragment.can_activate(agent, context_data)
            if not can_activate:
                return True

        return False

    def _transition_behavior(
        self,
        old_composition: "BehaviorComposition",
        new_composition: "BehaviorComposition",
        agent,
    ):
        """Handle smooth transition between behavior compositions"""
        logger.info(
            f"Transitioning behavior for {agent.id} from {old_composition.template.name} to {new_composition.template.name}"
        )

        # Could implement smooth transition logic here
        # For now, just replace immediately
        pass

    def _create_movement_node(self) -> BehaviorNode:
        """Create a basic movement behavior node"""
        return _SimpleActionNode("basic_move")

    def _create_evasive_movement_node(self) -> BehaviorNode:
        """Create an evasive movement behavior node"""
        return _SimpleActionNode("evasive_move")

    def _create_aggressive_combat_node(self) -> BehaviorNode:
        """Create an aggressive combat behavior node"""
        return _SimpleActionNode("aggressive_attack")

    def _create_defensive_combat_node(self) -> BehaviorNode:
        """Create a defensive combat behavior node"""
        return _SimpleActionNode("defensive_stance")

    def _create_efficient_gathering_node(self) -> BehaviorNode:
        """Create an efficient resource gathering behavior node"""
        return _SimpleActionNode("efficient_gather")

    def _create_cooperative_node(self) -> BehaviorNode:
        """Create a cooperative social behavior node"""
        return _SimpleActionNode("cooperate")

    def _create_active_trading_node(self) -> BehaviorNode:
        """Create an active trading behavior node"""
        return _SimpleActionNode("active_trade")

    def _create_fallback_node(self) -> BehaviorNode:
        """Create a fallback behavior node"""
        return _SimpleActionNode("idle")

    def get_composition_for_agent(
        self, agent_id: str
    ) -> Optional["BehaviorComposition"]:
        """Get current behavior composition for an agent"""
        return self.active_compositions.get(agent_id)

    def get_statistics(self) -> Dict[str, Any]:
        """Get composer statistics"""
        return {
            **self.composition_stats,
            "active_compositions": len(self.active_compositions),
            "available_fragments": len(self.fragment_library),
            "available_templates": len(self.templates),
            "interrupt_stats": self.interrupt_manager.get_interrupt_statistics(),
        }

    def check_for_interrupts(
        self, agent, context_data: Dict[str, Any]
    ) -> Optional[Tuple[InterruptPriority, InterruptReason, Dict[str, Any]]]:
        """Check if current behavior should be interrupted based on context"""

        # Check for emergency conditions
        if hasattr(agent, "health") and agent.health < 20:
            return (
                InterruptPriority.EMERGENCY,
                InterruptReason.HEALTH_CRITICAL,
                {
                    "health": agent.health,
                    "health_percentage": (agent.health / 100.0) * 100,
                },
            )

        # Check for combat threats
        if context_data.get("under_attack", False):
            attacker_count = len(context_data.get("attackers", []))
            return (
                InterruptPriority.CRITICAL,
                InterruptReason.UNDER_ATTACK,
                {
                    "attacker_count": attacker_count,
                    "attackers": context_data.get("attackers", []),
                },
            )

        # Check for better opportunities
        opportunity_value = context_data.get("opportunity_value", 0)
        current_composition = self.active_compositions.get(agent.id)
        if current_composition and opportunity_value > 0:
            current_value = self._estimate_composition_value(
                current_composition, context_data
            )
            if opportunity_value > current_value * 1.5:  # 50% better opportunity
                return (
                    InterruptPriority.URGENT,
                    InterruptReason.BETTER_OPPORTUNITY,
                    {
                        "opportunity_value": opportunity_value,
                        "current_value": current_value,
                    },
                )

        # Check for resource depletion
        if context_data.get("resource_depleted", False):
            resource_type = context_data.get("depleted_resource_type", "unknown")
            return (
                InterruptPriority.HIGH,
                InterruptReason.RESOURCE_DEPLETED,
                {"resource_type": resource_type},
            )

        # Check for time limits
        if current_composition:
            composition_age = time.time() - current_composition.creation_time
            max_duration = context_data.get(
                "max_behavior_duration", 600.0
            )  # 10 minutes default
            if composition_age > max_duration:
                return (
                    InterruptPriority.HIGH,
                    InterruptReason.TIME_LIMIT_EXCEEDED,
                    {"time_exceeded_seconds": composition_age - max_duration},
                )

        return None

    def _estimate_composition_value(
        self, composition: "BehaviorComposition", context_data: Dict[str, Any]
    ) -> float:
        """Estimate the value/utility of a current composition"""
        if not composition.fragments:
            return 1.0

        total_utility = 0.0
        for fragment in composition.fragments.values():
            # Use fragment priority as base value
            fragment_value = float(fragment.priority.value)
            # Adjust by progress if we can estimate it
            if hasattr(fragment, "progress_estimate"):
                fragment_value *= 1.0 + fragment.progress_estimate
            total_utility += fragment_value

        return total_utility / len(composition.fragments)

    def handle_interrupt(
        self,
        agent,
        interrupt_priority: InterruptPriority,
        interrupt_reason: InterruptReason,
        context: Dict[str, Any],
    ) -> bool:
        """Handle an interrupt by preserving current behavior and potentially starting new one"""

        current_composition = self.active_compositions.get(agent.id)
        if not current_composition:
            return False  # Nothing to interrupt

        composition_id = current_composition.composition_id

        # Check if we should actually interrupt
        should_interrupt = self.interrupt_manager.should_interrupt(
            composition_id, interrupt_priority, interrupt_reason, context
        )

        if not should_interrupt:
            return False

        # Preserve current behavior state
        progress = self._estimate_composition_progress(current_composition)
        state_data = self._extract_composition_state(current_composition)

        self.interrupt_manager.preserve_behavior_state(
            composition_id,
            current_composition.template.name,
            state_data,
            progress,
            context_data=context,
            success_probability=self._estimate_success_probability(current_composition),
        )

        # Interrupt the current behavior
        interrupt_event = self.interrupt_manager.interrupt_behavior(
            composition_id, interrupt_priority, interrupt_reason, context=context
        )

        # Remove from active compositions
        del self.active_compositions[agent.id]

        logger.info(
            f"Interrupted behavior composition {composition_id} for agent {agent.id} "
            f"due to {interrupt_reason.value} with priority {interrupt_priority.name}"
        )

        return True

    def try_resume_behavior(
        self, agent, context_data: Dict[str, Any]
    ) -> Optional["BehaviorComposition"]:
        """Try to resume a previously interrupted behavior"""

        # Check if there's a behavior that can be resumed
        next_behavior = self.interrupt_manager.get_next_behavior_to_resume(context_data)
        if not next_behavior:
            return None

        behavior_id, behavior_state = next_behavior

        # Try to resume the behavior
        success, resumed_state, message = self.interrupt_manager.resume_behavior(
            behavior_id
        )

        if not success:
            logger.debug(f"Could not resume behavior {behavior_id}: {message}")
            return None

        if message == "Requires reevaluation":
            # Let the caller decide whether to resume based on current utility
            current_utility = self._calculate_resumption_utility(
                resumed_state, context_data
            )
            if current_utility < 0.3:  # Not worth resuming
                self.interrupt_manager.resume_behavior(
                    behavior_id, ResumptionStrategy.ABANDON_GRACEFULLY
                )
                return None

        # Restore the behavior composition
        restored_composition = self._restore_composition_from_state(
            agent, resumed_state, context_data
        )

        if restored_composition:
            self.active_compositions[agent.id] = restored_composition
            logger.info(
                f"Resumed behavior composition {behavior_id} for agent {agent.id} "
                f"with progress {resumed_state.progress:.2f}"
            )

        return restored_composition

    def _estimate_composition_progress(
        self, composition: "BehaviorComposition"
    ) -> float:
        """Estimate how much progress has been made on a composition"""
        if not composition.fragments:
            return 0.0

        # Simple heuristic: age-based progress estimation
        age = time.time() - composition.creation_time
        estimated_duration = 300.0  # 5 minutes estimated duration
        return min(0.95, age / estimated_duration)

    def _extract_composition_state(
        self, composition: "BehaviorComposition"
    ) -> Dict[str, Any]:
        """Extract state data from a composition for preservation"""
        return {
            "template_name": composition.template.name,
            "fragment_ids": [f.fragment_id for f in composition.fragments.values()],
            "creation_time": composition.creation_time,
            "execution_history": getattr(composition, "execution_history", []),
        }

    def _estimate_success_probability(
        self, composition: "BehaviorComposition"
    ) -> float:
        """Estimate the probability of success for a composition"""
        if not composition.fragments:
            return 0.5

        # Average the success rates of all fragments
        total_success_rate = sum(f.success_rate for f in composition.fragments.values())
        return total_success_rate / len(composition.fragments)

    def _calculate_resumption_utility(
        self, behavior_state, context_data: Dict[str, Any]
    ) -> float:
        """Calculate utility of resuming a behavior"""
        base_utility = behavior_state.success_probability

        # Bonus for high progress
        progress_bonus = behavior_state.progress * 0.5

        # Penalty for age
        age_penalty = min(
            0.3, behavior_state.get_age() / 3600.0
        )  # Up to 30% penalty over 1 hour

        return max(0.0, base_utility + progress_bonus - age_penalty)

    def _restore_composition_from_state(
        self, agent, behavior_state, context_data: Dict[str, Any]
    ) -> Optional["BehaviorComposition"]:
        """Restore a behavior composition from preserved state"""
        try:
            template_name = behavior_state.state_data.get(
                "template_name", "balanced_explorer"
            )
            template = self.templates.get(template_name)

            if not template:
                logger.warning(f"Template {template_name} not found for restoration")
                return None

            # Create new composition with restored state
            composition = BehaviorComposition(
                composition_id=behavior_state.behavior_id,
                agent_id=agent.id,
                template=template,
                fragments={},
                creation_time=behavior_state.start_time,
            )

            # Try to restore fragments
            fragment_ids = behavior_state.state_data.get("fragment_ids", [])
            for fragment_id in fragment_ids:
                if fragment_id in self.fragment_library:
                    fragment = self.fragment_library[fragment_id]
                    # Check if fragment can still be activated
                    can_activate, _ = fragment.can_activate(agent, context_data)
                    if can_activate:
                        composition.fragments[fragment_id] = fragment

            # Rebuild behavior tree if we have fragments
            if composition.fragments:
                composition.root_node = self._build_behavior_tree(
                    composition, context_data
                )
                return composition

            return None

        except Exception as e:
            logger.error(f"Error restoring composition from state: {e}")
            return None

    def update_with_interrupts(
        self, agent, context_data: Dict[str, Any]
    ) -> Optional["BehaviorComposition"]:
        """Main update method that handles interrupts and resumptions"""

        # Periodic cleanup
        self.interrupt_manager.periodic_cleanup()

        # Check for interrupts on current behavior
        interrupt_info = self.check_for_interrupts(agent, context_data)
        if interrupt_info:
            priority, reason, interrupt_context = interrupt_info
            interrupted = self.handle_interrupt(
                agent, priority, reason, interrupt_context
            )

            if interrupted:
                # Try to compose a new behavior for the interrupt
                return self.compose_behavior(
                    agent, {**context_data, **interrupt_context}
                )

        # If no current behavior, try to resume an interrupted one
        if agent.id not in self.active_compositions:
            resumed_composition = self.try_resume_behavior(agent, context_data)
            if resumed_composition:
                return resumed_composition

        # Return current composition if no changes
        return self.active_compositions.get(agent.id)


@dataclass
class BehaviorComposition:
    """Represents a composed behavior for an agent"""

    composition_id: str
    agent_id: str
    template: BehaviorTemplate
    fragments: Dict[str, BehaviorFragment]
    creation_time: float
    root_node: Optional[BehaviorNode] = None

    def execute(self, agent, delta_time: float) -> NodeStatus:
        """Execute the composed behavior"""
        if not self.root_node:
            return NodeStatus.FAILURE

        # Execute the behavior tree
        status = self.root_node.execute(agent, delta_time)

        # Update memory based on execution results
        self._update_memory_from_execution(agent, status)

        return status

    def _update_memory_from_execution(self, agent, status: NodeStatus):
        """Update agent memory based on behavior execution results"""
        if not hasattr(agent, "memory") or not agent.memory:
            return

        current_time = time.time()

        # Update fragment success rates and potentially create memories
        for fragment in self.fragments.values():
            if status == NodeStatus.SUCCESS:
                fragment.update_success_rate(True)

                # Create positive memories for successful actions
                if fragment.fragment_type == BehaviorFragmentType.RESOURCE_GATHERING:
                    if hasattr(agent, "x") and hasattr(agent, "y"):
                        # Reinforce memory of resource locations
                        nearby_resources = agent.memory.get_known_resources(
                            agent.x, agent.y, radius=5.0
                        )
                        for resource_memory in nearby_resources:
                            resource_memory.reinforce(0.5)

                elif fragment.fragment_type == BehaviorFragmentType.EXPLORATION:
                    if hasattr(agent, "x") and hasattr(agent, "y"):
                        # Remember successful exploration results
                        agent.memory.remember_resource_location(
                            agent.x, agent.y, "exploration_success", 0.6, 1
                        )

            elif status == NodeStatus.FAILURE:
                fragment.update_success_rate(False)

                # Create negative memories for failed actions
                if fragment.fragment_type == BehaviorFragmentType.COMBAT:
                    if hasattr(agent, "x") and hasattr(agent, "y"):
                        # Remember dangerous locations
                        agent.memory.remember_danger_zone(
                            agent.x,
                            agent.y,
                            "combat_failure",
                            0.7,
                            {
                                "fragment_id": fragment.fragment_id,
                                "failure_time": current_time,
                            },
                        )

    def get_active_fragments(self) -> List[str]:
        """Get list of active fragment IDs"""
        return list(self.fragments.keys())

    def get_composition_info(self) -> Dict[str, Any]:
        """Get information about this composition"""
        return {
            "composition_id": self.composition_id,
            "agent_id": self.agent_id,
            "template": self.template.name,
            "fragments": [f.fragment_id for f in self.fragments.values()],
            "creation_time": self.creation_time,
            "age": time.time() - self.creation_time,
        }
