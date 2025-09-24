"""
Personality-driven agent that replaces all specific agent types.

This unified agent class uses personality desires to drive behavior
instead of hardcoded agent type logic.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from client.agent import BaseAgent
from shared.personality import Personality, PersonalityArchetype

logger = logging.getLogger(__name__)


class PersonalityAgent(BaseAgent):
    """
    Unified agent class that uses personality to drive behavior.

    Replaces ExplorerAgent, EnemyAgent, FishingExplorerAgent, etc.
    with a single flexible class that adapts based on personality desires.
    """

    def __init__(self, agent_id: str, x: float, y: float, personality: Personality):
        # We still need a basic agent_type for server compatibility during transition
        # This will be derived from the personality's primary desire
        primary_desires = personality.get_primary_desires(1)
        legacy_type = self._personality_to_legacy_type(personality, primary_desires)

        super().__init__(agent_id, x, y, legacy_type, personality)

        # Core personality system
        self.personality = personality
        self.archetype_name = self._determine_archetype_name(personality)

        # Dynamic behavior state based on personality
        self.exploration_history: List[Tuple[float, float]] = []
        self.social_interactions: Dict[str, float] = {}  # agent_id -> last_interaction_time
        self.resource_goals: Dict[str, int] = {}  # resource_type -> target_amount
        self.activity_satisfaction: Dict[str, float] = {}  # activity -> satisfaction_level

        # Personality-driven configuration
        self._configure_from_personality()

        # Don't initialize behavior tree yet - wait for provider injection
        self.behavior_tree_initialized = False

        logger.info(f"PersonalityAgent {agent_id[:8]} created with {self.archetype_name} personality: {personality}")

    def _personality_to_legacy_type(self, personality: Personality, primary_desires: List[Tuple[str, float]]) -> str:
        """Convert personality to legacy agent type for server compatibility"""
        if not primary_desires:
            return "player"

        primary_desire = primary_desires[0][0]

        # Map primary desires to legacy types
        desire_to_type = {
            'exploration': 'explorer',
            'combat': 'enemy' if personality.cooperativeness < 5.0 else 'player',
            'fishing': 'explorer',  # Fishing explorers were explorers
            'social': 'npc',
            'farming': 'npc',
            'money': 'npc',
            'building': 'npc',
            'cooking': 'npc',
            'foraging': 'explorer'
        }

        return desire_to_type.get(primary_desire, 'player')

    def _determine_archetype_name(self, personality: Personality) -> str:
        """Determine the closest archetype name for this personality"""
        archetypes = PersonalityArchetype.get_all_archetypes()

        best_match = None
        best_score = float('inf')

        for name, archetype in archetypes.items():
            # Calculate difference score
            score = 0.0
            for field_name in personality.__dataclass_fields__:
                if field_name.startswith('_'):  # Skip private fields
                    continue

                personality_value = getattr(personality, field_name)
                archetype_value = getattr(archetype, field_name)
                score += abs(personality_value - archetype_value)

            if score < best_score:
                best_score = score
                best_match = name

        return best_match or "custom"

    def _configure_from_personality(self):
        """Configure agent properties based on personality"""
        # Adjust speed based on exploration and combat desires
        base_speed = 5.0
        speed_modifier = (self.personality.exploration + self.personality.combat) / 20.0
        self.speed = base_speed * (0.8 + speed_modifier * 0.4)

        # Adjust vision based on exploration and risk tolerance
        base_vision = 15.0
        vision_modifier = (self.personality.exploration + self.personality.risk_tolerance) / 20.0
        self.vision_range = base_vision * (0.8 + vision_modifier * 0.4)

        # Set intention cooldown based on patience
        patience_factor = self.personality.patience / 10.0
        self.base_intention_cooldown = 1.0 + patience_factor * 2.0  # 1-3 seconds
        self.intention_cooldown = self.base_intention_cooldown

    def get_personality_type(self) -> str:
        """Get the personality archetype name"""
        return self.archetype_name

    def get_primary_motivations(self, count: int = 3) -> List[str]:
        """Get the agent's primary motivational desires"""
        desires = self.personality.get_primary_desires(count)
        return [desire[0] for desire in desires]

    def should_engage_in_activity(self, activity: str, context: Dict[str, Any] = None) -> float:
        """
        Calculate how motivated the agent is to engage in a specific activity.

        Args:
            activity: The activity type (combat, exploration, fishing, etc.)
            context: Additional context about the activity

        Returns:
            Motivation score (0.0 = not interested, 10.0 = extremely interested)
        """
        context = context or {}

        # Base motivation from personality
        base_motivation = self.personality.get_desire_priority(activity)

        # Apply context modifiers
        motivation = base_motivation

        if activity == "combat":
            # Reduce combat motivation if health is low (unless very aggressive)
            if self.health < self.max_health * 0.3:
                health_penalty = (1.0 - self.personality.risk_tolerance / 10.0) * 3.0
                motivation = max(0, motivation - health_penalty)

        elif activity == "exploration":
            # Increase exploration if we haven't moved much lately
            if hasattr(self, 'last_position') and len(self.exploration_history) > 5:
                recent_movement = sum(
                    abs(pos[0] - self.x) + abs(pos[1] - self.y)
                    for pos in self.exploration_history[-5:]
                ) / 5.0

                if recent_movement < 2.0:  # Been stationary
                    motivation += 2.0

        elif activity == "social":
            # Increase social desire if haven't interacted recently
            current_time = getattr(context, 'time', 0)
            if self.social_interactions:
                last_interaction = max(self.social_interactions.values())
                time_since_social = current_time - last_interaction
                if time_since_social > 30.0:  # 30 seconds since last interaction
                    motivation += 1.0

        # Apply satisfaction decay - if we've been doing something a lot, motivation decreases
        activity_satisfaction = self.activity_satisfaction.get(activity, 5.0)
        satisfaction_modifier = (5.0 - activity_satisfaction) / 5.0  # -1.0 to 1.0
        motivation += satisfaction_modifier

        return max(0.0, min(10.0, motivation))

    def update_activity_satisfaction(self, activity: str, success: bool, duration: float):
        """Update satisfaction levels for activities"""
        if activity not in self.activity_satisfaction:
            self.activity_satisfaction[activity] = 5.0

        # Successful activities increase satisfaction up to a point
        if success:
            # Diminishing returns - the more satisfied, the smaller the gain
            current = self.activity_satisfaction[activity]
            gain = (10.0 - current) / 10.0 * duration * 0.1
            self.activity_satisfaction[activity] = min(10.0, current + gain)
        else:
            # Failures decrease satisfaction
            self.activity_satisfaction[activity] = max(0.0, self.activity_satisfaction[activity] - duration * 0.2)

        # All other activities slowly decay toward neutral (5.0)
        for other_activity in self.activity_satisfaction:
            if other_activity != activity:
                current = self.activity_satisfaction[other_activity]
                if current > 5.0:
                    self.activity_satisfaction[other_activity] = max(5.0, current - 0.05)
                elif current < 5.0:
                    self.activity_satisfaction[other_activity] = min(5.0, current + 0.05)

    def record_exploration(self, x: float, y: float):
        """Record exploration progress"""
        self.exploration_history.append((x, y))
        # Keep only recent history
        if len(self.exploration_history) > 50:
            self.exploration_history = self.exploration_history[-50:]

    def record_social_interaction(self, other_agent_id: str, interaction_time: float):
        """Record social interaction"""
        self.social_interactions[other_agent_id] = interaction_time

    def _initialize_behavior_tree(self):
        """Initialize the behavior tree for this personality agent"""
        # PersonalityAgent ALWAYS uses the personality tree builder (not provider system)
        try:
            from client.behavior_tree.personality_tree_builder import personality_tree_builder

            logger.info(f"PersonalityAgent {self.id[:8]} building personality-driven behavior tree")
            tree = personality_tree_builder.build_tree(
                self.personality,
                self.x,
                self.y,
                home_base=(self.x, self.y),
                patrol_radius=8.0
            )

            if tree:
                self.set_behavior_tree(tree)
                logger.info(f"PersonalityAgent {self.id[:8]} initialized with personality tree builder")
                self.behavior_tree_initialized = True
            else:
                logger.error(f"PersonalityAgent {self.id[:8]} personality tree builder returned None")
                self._create_fallback_tree()

        except Exception as e:
            logger.error(f"PersonalityAgent {self.id[:8]} failed to initialize behavior tree: {e}")
            self._create_fallback_tree()

    def _create_fallback_tree(self):
        """Create a basic fallback behavior tree"""
        try:
            from client.behavior_tree.nodes import Idle
            from client.behavior_tree.tree import BehaviorTree
            fallback_tree = BehaviorTree(Idle(5.0), "FallbackTree")
            self.set_behavior_tree(fallback_tree)
            self.behavior_tree_initialized = True
            logger.warning(f"PersonalityAgent {self.id[:8]} using fallback idle tree")
        except Exception as e:
            logger.error(f"PersonalityAgent {self.id[:8]} failed to create fallback tree: {e}")

    def update(self, delta_time: float):
        """Update agent using personality-driven behavior tree"""
        # Initialize behavior tree if not already done
        if not self.behavior_tree_initialized:
            self._initialize_behavior_tree()

        # Record current position for exploration tracking
        import time
        current_time = time.time()
        if not hasattr(self, '_last_position_record') or current_time - self._last_position_record > 1.0:
            self.record_exploration(self.x, self.y)
            self._last_position_record = current_time

        # Use behavior tree system
        if self.behavior_tree:
            self.update_behavior_tree(delta_time)
        else:
            logger.warning(f"PersonalityAgent {self.id[:8]} has no behavior tree!")

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        """Update visible entities with personality-aware perception"""
        self.visible_entities = visible_entities

        # Record social opportunities
        import time
        current_time = time.time()
        for entity in visible_entities:
            if entity.get("id") != self.id and entity.get("agent_type") in ["player", "npc"]:
                # This is a potential social interaction
                if self.personality.social > 6.0:  # Only record if socially inclined
                    entity_id = entity.get("id")
                    if entity_id not in self.social_interactions:
                        # New social opportunity
                        self.record_social_interaction(entity_id, current_time)

    def decide(self) -> Optional[Dict[str, Any]]:
        """Personality-driven decision making (mostly handled by behavior tree now)"""
        # The behavior tree now handles most decisions
        # This method mainly serves for reporting and debugging

        if hasattr(self, 'personality') and self.personality:
            primary_motivations = self.get_primary_motivations(2)

            # Report personality-driven status occasionally
            import time
            if not hasattr(self, '_last_personality_report') or \
               time.time() - self._last_personality_report > 10.0:
                self._last_personality_report = time.time()

                return {
                    "type": "personality_status",
                    "agent_id": self.id,
                    "archetype": self.archetype_name,
                    "primary_motivations": primary_motivations,
                    "current_activity": getattr(self, 'current_intention', None),
                    "position": (self.x, self.y)
                }

        return None

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debugging information about this personality agent"""
        base_debug = super().get_state()

        personality_debug = {
            "archetype": self.archetype_name,
            "personality": self.personality.to_dict(),
            "primary_motivations": self.get_primary_motivations(3),
            "activity_satisfaction": dict(self.activity_satisfaction),
            "social_interactions_count": len(self.social_interactions),
            "exploration_history_length": len(self.exploration_history)
        }

        base_debug.update(personality_debug)
        return base_debug

    @classmethod
    def create_from_archetype(cls, agent_id: str, x: float, y: float, archetype_name: str) -> 'PersonalityAgent':
        """Create a personality agent from a named archetype"""
        archetype = PersonalityArchetype.get_archetype(archetype_name)
        if archetype is None:
            logger.warning(f"Unknown archetype '{archetype_name}', using explorer default")
            archetype = PersonalityArchetype.explorer()

        return cls(agent_id, x, y, archetype)

    @classmethod
    def create_random(cls, agent_id: str, x: float, y: float, seed: Optional[int] = None) -> 'PersonalityAgent':
        """Create a personality agent with random personality"""
        random_personality = PersonalityArchetype.random_personality(seed)
        return cls(agent_id, x, y, random_personality)