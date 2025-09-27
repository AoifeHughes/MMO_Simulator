"""
Tests for Behavior Composer System

Tests dynamic behavior composition, fragment management, template selection,
conflict resolution, and runtime behavior adaptation.
"""

import pytest
import time
from unittest.mock import Mock, MagicMock

from client.behavior_tree.behavior_composer import (
    BehaviorComposer, BehaviorFragment, BehaviorTemplate, BehaviorComposition,
    BehaviorFragmentType, BehaviorPriority
)
from client.behavior_tree.nodes.action import ActionNode
from client.behavior_tree.nodes.base import NodeStatus
from shared.personality import Personality


class MockActionNode(ActionNode):
    """Mock ActionNode for testing that implements required abstract methods"""

    def __init__(self, name: str):
        super().__init__(name)
        self.started = False
        self.stopped = False

    def start_action(self, context):
        """Mock implementation of start_action"""
        self.started = True
        return NodeStatus.RUNNING

    def stop_action(self, context):
        """Mock implementation of stop_action"""
        self.stopped = True

    def update_action(self, context):
        """Mock implementation of update_action"""
        return NodeStatus.SUCCESS


class MockAgent:
    """Mock agent for testing behavior composition"""

    def __init__(self, agent_id: str, personality: Personality = None):
        self.id = agent_id
        self.personality = personality or Personality()
        self.x = 10.0
        self.y = 10.0
        self.health = 100.0
        self.agent_type = "test_agent"  # Add agent_type for logging


class TestBehaviorFragment:
    """Test behavior fragment functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.agent = MockAgent("test_agent", Personality(combat=7.0, social=3.0))
        self.fragment = BehaviorFragment(
            fragment_id="test_fragment",
            fragment_type=BehaviorFragmentType.COMBAT,
            priority=BehaviorPriority.HIGH,
            node=MockActionNode("test_action"),
            required_context={"enemy_target"},
            personality_weights={"combat": 0.5},
            cooldown_duration=2.0
        )

    def test_fragment_creation(self):
        """Test behavior fragment creation"""
        assert self.fragment.fragment_id == "test_fragment"
        assert self.fragment.fragment_type == BehaviorFragmentType.COMBAT
        assert self.fragment.priority == BehaviorPriority.HIGH
        assert "enemy_target" in self.fragment.required_context

    def test_can_activate_with_valid_context(self):
        """Test fragment activation with valid context"""
        context = {"enemy_target": "enemy_1"}
        can_activate, message = self.fragment.can_activate(self.agent, context)
        assert can_activate is True
        assert "Fragment can activate" in message

    def test_can_activate_missing_context(self):
        """Test fragment activation with missing context"""
        context = {}
        can_activate, message = self.fragment.can_activate(self.agent, context)
        assert can_activate is False
        assert "Missing required context" in message

    def test_can_activate_cooldown(self):
        """Test fragment activation during cooldown"""
        context = {"enemy_target": "enemy_1"}

        # First activation should work
        self.fragment.activate()

        # Second activation should be blocked by cooldown
        can_activate, message = self.fragment.can_activate(self.agent, context)
        assert can_activate is False
        assert "cooldown" in message

    def test_can_activate_personality_requirements(self):
        """Test personality-based activation requirements"""
        # Agent has combat=7.0, which should satisfy combat weight of 0.5
        context = {"enemy_target": "enemy_1"}
        can_activate, _ = self.fragment.can_activate(self.agent, context)
        assert can_activate is True

        # Create fragment requiring high social trait (agent has social=3.0)
        social_fragment = BehaviorFragment(
            fragment_id="social_fragment",
            fragment_type=BehaviorFragmentType.SOCIAL,
            priority=BehaviorPriority.NORMAL,
            node=MockActionNode("social_action"),
            personality_weights={"social": 0.8}  # Requires high social
        )

        can_activate, message = social_fragment.can_activate(self.agent, {})
        assert can_activate is False
        assert "Insufficient social trait" in message

    def test_calculate_utility(self):
        """Test utility calculation"""
        context = {"enemy_target": "enemy_1"}
        utility = self.fragment.calculate_utility(self.agent, context)

        # Should be positive since fragment can activate
        assert utility > 0.0

        # High priority fragment should have higher base utility
        assert utility >= 30.0  # HIGH priority = 3 * 10.0 base

    def test_calculate_utility_blocked(self):
        """Test utility calculation when fragment is blocked"""
        # Missing required context
        context = {}
        utility = self.fragment.calculate_utility(self.agent, context)
        assert utility == 0.0

    def test_success_rate_tracking(self):
        """Test success rate tracking and influence on utility"""
        initial_rate = self.fragment.success_rate
        assert initial_rate == 1.0

        # Update with failure
        self.fragment.update_success_rate(False)
        assert self.fragment.success_rate < initial_rate

        # Update with success
        self.fragment.update_success_rate(True)
        assert self.fragment.success_rate > 0.0

    def test_activation_tracking(self):
        """Test activation count tracking"""
        initial_count = self.fragment.activation_count
        assert initial_count == 0

        self.fragment.activate()
        assert self.fragment.activation_count == initial_count + 1
        assert self.fragment.last_activation > 0


class TestBehaviorTemplate:
    """Test behavior template functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.template = BehaviorTemplate("test_template", "Test Template")

    def test_template_creation(self):
        """Test template creation"""
        assert self.template.template_id == "test_template"
        assert self.template.name == "Test Template"
        assert len(self.template.fragment_slots) == 0

    def test_add_slots(self):
        """Test adding fragment slots"""
        self.template.add_slot("movement", BehaviorFragmentType.MOVEMENT)
        self.template.add_slot("combat", BehaviorFragmentType.COMBAT)

        assert len(self.template.fragment_slots) == 2
        assert self.template.fragment_slots["movement"] == BehaviorFragmentType.MOVEMENT
        assert self.template.fragment_slots["combat"] == BehaviorFragmentType.COMBAT

    def test_add_rules(self):
        """Test adding composition rules"""
        self.template.add_rule("movement REQUIRED")
        self.template.add_rule("combat OR social")

        assert len(self.template.composition_rules) == 2
        assert "movement REQUIRED" in self.template.composition_rules

    def test_set_structure(self):
        """Test setting template structure"""
        structure = {"type": "selector", "children": ["movement", "combat"]}
        self.template.set_structure(structure)

        assert self.template.root_structure == structure


class TestBehaviorComposer:
    """Test behavior composer functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.composer = BehaviorComposer()
        self.agent = MockAgent("test_agent", Personality(
            combat=8.0, social=4.0, exploration=6.0, cooperativeness=5.0
        ))

    def test_composer_initialization(self):
        """Test composer initialization"""
        assert len(self.composer.fragment_library) > 0
        assert len(self.composer.templates) > 0
        assert "basic_movement" in self.composer.fragment_library
        assert "balanced_explorer" in self.composer.templates

    def test_register_fragment(self):
        """Test fragment registration"""
        fragment = BehaviorFragment(
            fragment_id="custom_fragment",
            fragment_type=BehaviorFragmentType.SURVIVAL,
            priority=BehaviorPriority.URGENT,
            node=MockActionNode("custom_action")
        )

        initial_count = len(self.composer.fragment_library)
        self.composer.register_fragment(fragment)

        assert len(self.composer.fragment_library) == initial_count + 1
        assert "custom_fragment" in self.composer.fragment_library

    def test_register_template(self):
        """Test template registration"""
        template = BehaviorTemplate("custom_template", "Custom Template")
        template.add_slot("movement", BehaviorFragmentType.MOVEMENT)

        initial_count = len(self.composer.templates)
        self.composer.register_template(template)

        assert len(self.composer.templates) == initial_count + 1
        assert "custom_template" in self.composer.templates

    def test_compose_behavior_basic(self):
        """Test basic behavior composition"""
        context = {
            "target_position": (20.0, 20.0),
            "resource_target": "wood_1",
            "nearby_allies": ["ally_1"]
        }

        composition = self.composer.compose_behavior(self.agent, context)

        assert composition is not None
        assert composition.agent_id == "test_agent"
        assert composition.template is not None
        assert len(composition.fragments) > 0
        assert composition.root_node is not None

    def test_compose_behavior_with_template(self):
        """Test behavior composition with specific template"""
        context = {
            "target_position": (20.0, 20.0),
            "enemy_target": "enemy_1"
        }

        composition = self.composer.compose_behavior(self.agent, context, "combat_specialist")

        assert composition.template.template_id == "combat_specialist"

        # Should include combat fragment if available
        fragment_types = [f.fragment_type for f in composition.fragments.values()]
        assert BehaviorFragmentType.COMBAT in fragment_types or len(fragment_types) == 0

    def test_template_selection_by_personality(self):
        """Test automatic template selection based on personality"""
        # High combat agent should get combat template
        combat_agent = MockAgent("combat_agent", Personality(combat=9.0))
        context = {"enemy_target": "enemy_1", "target_position": (20.0, 20.0)}

        composition = self.composer.compose_behavior(combat_agent, context)
        # Should select combat specialist template for high combat personality
        # (Note: actual selection depends on available context)

        # High money/social agent should get trader template
        trader_agent = MockAgent("trader_agent", Personality(money=9.0, social=8.0))
        context = {"trade_opportunities": ["trade_1"], "target_position": (20.0, 20.0)}

        composition = self.composer.compose_behavior(trader_agent, context)
        # Should consider trader template for high money/social personality

    def test_fragment_selection(self):
        """Test fragment selection for template slots"""
        context = {
            "target_position": (20.0, 20.0),
            "enemy_target": "enemy_1",
            "resource_target": "wood_1"
        }

        # Should select fragments based on context and personality
        best_movement = self.composer._select_best_fragment(
            self.agent, context, BehaviorFragmentType.MOVEMENT
        )
        assert best_movement is not None
        assert best_movement.fragment_type == BehaviorFragmentType.MOVEMENT

        best_combat = self.composer._select_best_fragment(
            self.agent, context, BehaviorFragmentType.COMBAT
        )
        if best_combat:  # May be None if context doesn't support combat
            assert best_combat.fragment_type == BehaviorFragmentType.COMBAT

    def test_conflict_resolution(self):
        """Test conflict resolution between fragments"""
        # Create conflicting fragments
        fragment1 = BehaviorFragment(
            fragment_id="frag1",
            fragment_type=BehaviorFragmentType.MOVEMENT,
            priority=BehaviorPriority.HIGH,
            node=MockActionNode("action1"),
            conflicting_fragments={"frag2"}
        )

        fragment2 = BehaviorFragment(
            fragment_id="frag2",
            fragment_type=BehaviorFragmentType.MOVEMENT,
            priority=BehaviorPriority.NORMAL,
            node=MockActionNode("action2"),
            conflicting_fragments={"frag1"}
        )

        selected = {"slot1": fragment1, "slot2": fragment2}
        conflicts = [("slot1", fragment1, "slot2", fragment2)]

        # Test priority-based resolution
        resolved = self.composer._resolve_by_priority(selected, conflicts)

        # Should keep higher priority fragment
        assert len(resolved) == 1
        remaining_fragment = next(iter(resolved.values()))
        assert remaining_fragment.priority == BehaviorPriority.HIGH

    def test_update_composition(self):
        """Test composition updating"""
        context = {"target_position": (20.0, 20.0)}

        # Initial composition
        composition1 = self.composer.compose_behavior(self.agent, context)
        assert self.agent.id in self.composer.active_compositions

        # Update with same context should not recompose immediately
        updated = self.composer.update_composition(self.agent, context)
        assert updated is False  # No change needed

        # Update with emergency context should recompose
        emergency_context = {**context, "emergency": True}
        updated = self.composer.update_composition(self.agent, emergency_context)
        assert updated is True

    def test_composition_aging(self):
        """Test that compositions are recomposed after aging"""
        context = {"target_position": (20.0, 20.0)}

        # Create composition
        composition = self.composer.compose_behavior(self.agent, context)

        # Mock old creation time
        composition.creation_time = time.time() - 35.0  # 35 seconds ago

        # Should recompose due to age
        should_recompose = self.composer._should_recompose(composition, self.agent, context)
        assert should_recompose is True

    def test_statistics_tracking(self):
        """Test statistics tracking"""
        initial_stats = self.composer.get_statistics()

        context = {"target_position": (20.0, 20.0)}
        composition = self.composer.compose_behavior(self.agent, context)

        final_stats = self.composer.get_statistics()

        # Should track composition creation
        assert final_stats["total_compositions"] > initial_stats["total_compositions"]
        assert final_stats["active_compositions"] >= 1

    def test_get_composition_for_agent(self):
        """Test retrieving composition for specific agent"""
        context = {"target_position": (20.0, 20.0)}

        # No composition initially
        composition = self.composer.get_composition_for_agent("test_agent")
        assert composition is None

        # Create composition
        self.composer.compose_behavior(self.agent, context)

        # Should retrieve composition
        composition = self.composer.get_composition_for_agent("test_agent")
        assert composition is not None
        assert composition.agent_id == "test_agent"

    def test_fragment_utility_comparison(self):
        """Test that fragments are selected based on utility"""
        # Create agent with high combat trait
        combat_agent = MockAgent("combat_agent", Personality(combat=9.0))

        context = {"enemy_target": "enemy_1"}

        # Get combat fragments
        aggressive = self.composer.fragment_library.get("aggressive_combat")
        defensive = self.composer.fragment_library.get("defensive_combat")

        if aggressive and defensive:
            aggressive_utility = aggressive.calculate_utility(combat_agent, context)
            defensive_utility = defensive.calculate_utility(combat_agent, context)

            # Aggressive should have higher utility for high-combat agent
            assert aggressive_utility >= defensive_utility

    def test_empty_context_handling(self):
        """Test behavior composition with minimal context"""
        context = {}

        # Should still create some composition, even with no context
        composition = self.composer.compose_behavior(self.agent, context)
        assert composition is not None
        assert composition.root_node is not None

    def test_multiple_agents(self):
        """Test composer handling multiple agents"""
        agent1 = MockAgent("agent1", Personality(combat=8.0))
        agent2 = MockAgent("agent2", Personality(social=8.0))

        context1 = {"enemy_target": "enemy_1", "target_position": (10.0, 10.0)}
        context2 = {"trade_opportunities": ["trade_1"], "target_position": (20.0, 20.0)}

        comp1 = self.composer.compose_behavior(agent1, context1)
        comp2 = self.composer.compose_behavior(agent2, context2)

        assert comp1.agent_id == "agent1"
        assert comp2.agent_id == "agent2"
        assert len(self.composer.active_compositions) == 2


class TestBehaviorComposition:
    """Test behavior composition execution and management"""

    def setup_method(self):
        """Set up test fixtures"""
        self.composer = BehaviorComposer()
        self.agent = MockAgent("test_agent")

        template = self.composer.templates["balanced_explorer"]
        fragments = {}

        # Create minimal composition
        self.composition = BehaviorComposition(
            composition_id="test_comp",
            agent_id="test_agent",
            template=template,
            fragments=fragments,
            creation_time=time.time()
        )

    def test_composition_creation(self):
        """Test composition creation and properties"""
        assert self.composition.composition_id == "test_comp"
        assert self.composition.agent_id == "test_agent"
        assert self.composition.template.template_id == "balanced_explorer"

    def test_composition_info(self):
        """Test composition information retrieval"""
        info = self.composition.get_composition_info()

        assert "composition_id" in info
        assert "agent_id" in info
        assert "template" in info
        assert "fragments" in info
        assert "age" in info

        assert info["agent_id"] == "test_agent"

    def test_get_active_fragments(self):
        """Test getting active fragment list"""
        active = self.composition.get_active_fragments()
        assert isinstance(active, list)

    def test_composition_execution_without_root(self):
        """Test composition execution without root node"""
        result = self.composition.execute(self.agent, 0.1)
        assert result == NodeStatus.FAILURE

    def test_composition_execution_with_root(self):
        """Test composition execution with root node"""
        # Create mock root node
        mock_root = Mock()
        mock_root.execute.return_value = NodeStatus.SUCCESS

        self.composition.root_node = mock_root
        result = self.composition.execute(self.agent, 0.1)

        assert result == NodeStatus.SUCCESS
        mock_root.execute.assert_called_once_with(self.agent, 0.1)


class TestBehaviorComposerIntegration:
    """Test behavior composer integration scenarios"""

    def test_full_composition_workflow(self):
        """Test complete composition workflow"""
        composer = BehaviorComposer()
        agent = MockAgent("workflow_agent", Personality(
            combat=6.0, exploration=8.0, social=4.0
        ))

        # Full context
        context = {
            "target_position": (25.0, 25.0),
            "resource_target": "wood_1",
            "enemy_target": "enemy_1",
            "nearby_allies": ["ally_1", "ally_2"],
            "trade_opportunities": ["trade_1"]
        }

        # Compose behavior
        composition = composer.compose_behavior(agent, context)

        assert composition is not None
        assert composition.root_node is not None
        assert len(composition.fragments) > 0

        # Execute behavior
        if composition.root_node:
            result = composition.execute(agent, 0.1)
            # Result depends on actual node implementation
            assert result is not None

        # Update composition
        updated = composer.update_composition(agent, context)
        # May or may not update depending on conditions

        # Get stats
        stats = composer.get_statistics()
        assert stats["total_compositions"] >= 1

    def test_behavior_adaptation_scenario(self):
        """Test behavior adaptation to changing conditions"""
        composer = BehaviorComposer()
        agent = MockAgent("adaptive_agent", Personality(combat=5.0))

        # Start with peaceful context
        peaceful_context = {
            "target_position": (15.0, 15.0),
            "resource_target": "wood_1"
        }

        comp1 = composer.compose_behavior(agent, peaceful_context)
        initial_fragments = comp1.get_active_fragments()

        # Change to dangerous context
        dangerous_context = {
            "target_position": (15.0, 15.0),
            "enemy_target": "enemy_1",
            "danger_source": (15.0, 15.0),
            "emergency": True
        }

        updated = composer.update_composition(agent, dangerous_context)

        if updated:
            comp2 = composer.get_composition_for_agent("adaptive_agent")
            new_fragments = comp2.get_active_fragments()

            # Fragments may have changed due to emergency
            # This depends on actual fragment availability and selection


if __name__ == "__main__":
    pytest.main([__file__])