from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid
import random
import logging

from src.world.world import Vector2

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    COMBAT = "combat"
    INTERACTING = "interacting"
    LEARNING = "learning"
    TEACHING = "teaching"
    TRADING = "trading"
    RESTING = "resting"


@dataclass
class Personality:
    """Agent personality traits that influence behavior"""
    risk_taking: float = 0.5  # 0 = cautious, 1 = reckless
    social: float = 0.5  # 0 = loner, 1 = very social
    exploration: float = 0.5  # 0 = stays in comfort zone, 1 = explores everywhere
    experimentation: float = 0.5  # 0 = follows known patterns, 1 = tries new things
    teaching: float = 0.5  # 0 = keeps knowledge, 1 = shares freely
    trust: float = 0.5  # 0 = skeptical, 1 = trusting

    def randomize(self):
        """Randomize personality traits"""
        self.risk_taking = random.random()
        self.social = random.random()
        self.exploration = random.random()
        self.experimentation = random.random()
        self.teaching = random.random()
        self.trust = random.random()

    def get_trait_influence(self, trait_name: str) -> float:
        """Get the influence value of a specific trait"""
        return getattr(self, trait_name, 0.5)


@dataclass
class CharacterStats:
    """Basic RPG character statistics"""
    health: int = 100
    max_health: int = 100
    mana: int = 50
    max_mana: int = 50
    stamina: int = 100
    max_stamina: int = 100
    strength: int = 10
    intelligence: int = 10
    dexterity: int = 10
    constitution: int = 10
    wisdom: int = 10
    charisma: int = 10


@dataclass
class AgentMemory:
    """Agent's memory system for tracking experiences"""
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    learned_patterns: Dict[str, Any] = field(default_factory=dict)
    relationships: Dict[str, float] = field(default_factory=dict)  # agent_id -> trust level
    knowledge_base: List[Dict[str, Any]] = field(default_factory=list)
    max_recent_actions: int = 100

    def add_action(self, action: Dict[str, Any]):
        """Record an action in memory"""
        self.recent_actions.append(action)
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions.pop(0)

    def get_relationship(self, agent_id: str) -> float:
        """Get trust level with another agent"""
        return self.relationships.get(agent_id, 0.0)

    def update_relationship(self, agent_id: str, delta: float):
        """Update relationship with another agent"""
        current = self.relationships.get(agent_id, 0.0)
        self.relationships[agent_id] = max(-1.0, min(1.0, current + delta))


class Agent:
    """Base Agent class with personality and behavior systems"""

    def __init__(self, name: str = None):
        self.id = str(uuid.uuid4())
        self.name = name or f"Agent_{self.id[:8]}"

        # Core attributes
        self.level = 1
        self.experience = 0
        self.character_class = "Adventurer"
        self.specialization = None

        # Position and movement
        self.position = Vector2(1000, 1000)  # Start in starting zone
        self.velocity = Vector2(0, 0)
        self.speed = 5.0

        # Systems
        self.personality = Personality()
        self.stats = CharacterStats()
        self.memory = AgentMemory()
        self.state = AgentState.IDLE

        # Inventory and equipment
        self.inventory: List[Any] = []
        self.equipment: Dict[str, Any] = {
            'weapon': None,
            'armor': None,
            'accessory': None
        }

        # Request queue for actions
        self.pending_requests: List[Dict[str, Any]] = []

        # Goals and current objective
        self.current_goal = None
        self.goal_queue: List[Any] = []

        logger.debug(f"Agent {self.name} created with ID {self.id}")

    def update(self, delta_time: float, world, request_manager):
        """Main update loop for the agent"""
        # Update state machine
        self._update_state(delta_time, world)

        # Make decisions based on personality and state
        self._make_decisions(world, request_manager)

        # Process movement
        if self.state == AgentState.MOVING:
            self._update_movement(delta_time, world)

        # Update stats (regeneration, etc.)
        self._update_stats(delta_time)

    def _update_state(self, delta_time: float, world):
        """Update agent's state based on current conditions"""
        # State transition logic
        if self.state == AgentState.IDLE:
            # Check if should start moving, interacting, etc.
            if self.current_goal and self._should_pursue_goal():
                self.state = AgentState.MOVING
        elif self.state == AgentState.COMBAT:
            # Check if combat is over
            if not self._in_combat_range(world):
                self.state = AgentState.IDLE

    def _make_decisions(self, world, request_manager):
        """Make decisions based on personality and current state"""
        # Personality-influenced decision making
        if self.state == AgentState.IDLE:
            # Exploration decision
            if random.random() < self.personality.exploration * 0.1:
                self._request_exploration(request_manager)

            # Social interaction decision
            if random.random() < self.personality.social * 0.05:
                self._request_social_interaction(world, request_manager)

            # Risk-taking decision for combat
            if random.random() < self.personality.risk_taking * 0.05:
                self._request_combat(world, request_manager)

    def _update_movement(self, delta_time: float, world):
        """Update agent position based on velocity"""
        if self.velocity.x != 0 or self.velocity.y != 0:
            new_x = self.position.x + self.velocity.x * self.speed * delta_time
            new_y = self.position.y + self.velocity.y * self.speed * delta_time

            # Boundary checking
            new_x = max(0, min(world.width, new_x))
            new_y = max(0, min(world.height, new_y))

            self.position = Vector2(new_x, new_y)
            world.update_entity_position(self.id, self.position)

    def _update_stats(self, delta_time: float):
        """Update character stats (regeneration, etc.)"""
        # Health regeneration when not in combat
        if self.state != AgentState.COMBAT:
            regen_rate = 1.0  # HP per second
            self.stats.health = min(
                self.stats.max_health,
                self.stats.health + regen_rate * delta_time
            )

        # Mana regeneration
        mana_regen = 0.5  # MP per second
        self.stats.mana = min(
            self.stats.max_mana,
            self.stats.mana + mana_regen * delta_time
        )

    def _should_pursue_goal(self) -> bool:
        """Determine if agent should pursue current goal"""
        if not self.current_goal:
            return False

        # Personality influences goal pursuit
        if self.current_goal.get('type') == 'exploration':
            return random.random() < self.personality.exploration
        elif self.current_goal.get('type') == 'social':
            return random.random() < self.personality.social

        return True

    def _in_combat_range(self, world) -> bool:
        """Check if enemies are in combat range"""
        enemies = world.get_nearby_enemies(self.position, 10.0)
        return len(enemies) > 0

    def _request_exploration(self, request_manager):
        """Create exploration request"""
        request = {
            'agent_id': self.id,
            'type': 'exploration',
            'priority': self.personality.exploration,
            'target_area': self._select_exploration_target()
        }
        request_manager.add_request(request)

    def _request_social_interaction(self, world, request_manager):
        """Create social interaction request"""
        nearby_agents = world.get_nearby_agents(self.position, 50.0)
        if nearby_agents:
            target = random.choice(nearby_agents)
            if target.id != self.id:
                request = {
                    'agent_id': self.id,
                    'type': 'social_interaction',
                    'priority': self.personality.social,
                    'target_agent': target.id,
                    'interaction_type': self._select_interaction_type()
                }
                request_manager.add_request(request)

    def _request_combat(self, world, request_manager):
        """Create combat request"""
        enemies = world.get_nearby_enemies(self.position, 100.0)
        if enemies:
            target = random.choice(enemies)
            request = {
                'agent_id': self.id,
                'type': 'combat',
                'priority': self.personality.risk_taking,
                'target_enemy': target.id
            }
            request_manager.add_request(request)

    def _select_exploration_target(self) -> str:
        """Select exploration target based on personality"""
        if self.personality.risk_taking > 0.7:
            return "dangerous_area"
        elif self.personality.exploration > 0.7:
            return "unknown_area"
        else:
            return "safe_area"

    def _select_interaction_type(self) -> str:
        """Select interaction type based on personality"""
        if self.personality.teaching > 0.7:
            return "teach"
        elif self.personality.social > 0.7:
            return "chat"
        elif self.personality.trust > 0.7:
            return "trade"
        else:
            return "greet"

    def share_knowledge(self, knowledge: Dict[str, Any], target_agent: 'Agent'):
        """Share knowledge with another agent"""
        if self.personality.teaching > random.random():
            # Willing to share based on teaching trait
            trust_level = self.memory.get_relationship(target_agent.id)
            if trust_level > -0.5:  # Don't share with distrusted agents
                logger.debug(f"{self.name} sharing knowledge with {target_agent.name}")
                target_agent.receive_knowledge(knowledge, self.id)

    def receive_knowledge(self, knowledge: Dict[str, Any], source_id: str):
        """Receive knowledge from another agent"""
        trust_level = self.memory.get_relationship(source_id)

        # Apply trust-based confidence adjustment
        adjusted_knowledge = knowledge.copy()
        adjusted_knowledge['confidence'] = knowledge.get('confidence', 1.0) * (0.5 + trust_level * 0.5)
        adjusted_knowledge['source'] = source_id

        self.memory.knowledge_base.append(adjusted_knowledge)
        logger.debug(f"{self.name} received knowledge from {source_id}")

    def get_info(self) -> Dict[str, Any]:
        """Get agent information for debugging/display"""
        return {
            'id': self.id,
            'name': self.name,
            'level': self.level,
            'class': self.character_class,
            'position': (self.position.x, self.position.y),
            'state': self.state.value,
            'health': f"{self.stats.health}/{self.stats.max_health}",
            'personality': {
                'risk_taking': self.personality.risk_taking,
                'social': self.personality.social,
                'exploration': self.personality.exploration
            }
        }