from __future__ import annotations
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING
import random
from queue import PriorityQueue

from .base import Entity
from .stats import Stats
from ..ai.personality import Personality
from ..ai.character_class import CharacterClass, get_random_character_class
from ..ai.goal import Goal
from ..ai.decision_maker import DecisionMaker

if TYPE_CHECKING:
    from ..core.world import World
    from ..actions.base import Action


class Agent(Entity):
    def __init__(
        self,
        position: Tuple[int, int],
        name: str = "Agent",
        personality: Optional[Personality] = None,
        character_class: Optional[CharacterClass] = None,
        stats: Optional[Stats] = None
    ):
        super().__init__(position, name, stats or Stats())

        self.personality = personality or Personality.randomize()
        self.character_class = character_class or get_random_character_class()

        # Apply class bonuses to stats
        self._apply_class_bonuses()

        # AI state
        self.skills: Dict[str, int] = {}
        self.decision_maker = DecisionMaker()
        self.current_goals: List[Goal] = []
        self.current_action: Optional[Action] = None
        self.action_queue: List[Action] = []

        # Experience and relationships
        self.total_experience = 0
        self.relationships: Dict[int, float] = {}  # entity_id -> relationship (-1 to 1)

        # Memory and awareness
        self.known_entities: Dict[int, Dict] = {}  # Recent entity sightings
        self.memory_duration = 50  # How long to remember entity positions

        # Behavioral state
        self.last_action_tick = 0
        self.idle_ticks = 0
        self.max_idle_ticks = 10

    def _apply_class_bonuses(self) -> None:
        """Apply character class stat bonuses"""
        for stat_name, bonus in self.character_class.starting_stats_bonus.items():
            if hasattr(self.stats, stat_name):
                current_value = getattr(self.stats, stat_name)
                setattr(self.stats, stat_name, current_value + bonus)

        # Give starting equipment
        for item in self.character_class.get_starting_equipment():
            self.inventory.add_item(item, 1)

            # Equip weapons and tools automatically
            if item.item_type == "weapon":
                self.inventory.equip_weapon(item)
            elif item.item_type == "tool":
                tool_type = item.get_property("tool_type")
                if tool_type:
                    self.inventory.equip_tool(item, tool_type)

    def update(self, world: World) -> None:
        """Main update loop for agent AI"""
        self.update_status_effects()
        self._update_memory(world)

        if not self.stats.is_alive():
            return

        # Three-phase AI update
        self.perceive(world)
        self.decide(world)
        self.act(world)

    def perceive(self, world: World) -> None:
        """Update agent's knowledge of the world"""
        self._scan_for_entities(world)
        self._update_relationships(world)

    def decide(self, world: World) -> None:
        """Make decisions about what to do next"""
        # Clean up completed/invalid goals
        self.current_goals = [
            goal for goal in self.current_goals
            if not goal.is_complete(self, world) and not goal.should_abandon(self, world)
        ]

        # Select new goal if needed
        if not self.current_goals or random.random() < 0.1:  # 10% chance to reconsider
            new_goal = self.decision_maker.select_goal(self, world, self.current_goals)
            if new_goal and new_goal not in self.current_goals:
                self.current_goals.append(new_goal)

        # Sort goals by priority
        self.current_goals.sort(key=lambda g: g.priority, reverse=True)

    def act(self, world: World) -> None:
        """Execute actions based on current goals"""
        # Check if current action is still running
        if (self.current_action and
            hasattr(self.current_action, 'is_active') and
            self.current_action.is_active and
            not self.current_action.is_complete(world.current_tick)):
            return  # Still executing current action

        # Get next action from highest priority goal
        new_action = None

        if self.action_queue:
            # Execute queued actions first
            new_action = self.action_queue.pop(0)
        elif self.current_goals:
            # Get action from current goal
            active_goal = self.current_goals[0]
            new_action = active_goal.get_next_action(self, world)

            if new_action:
                # Start the action
                if hasattr(new_action, 'start'):
                    new_action.start(world.current_tick)

                # Execute immediately for single-tick actions
                if new_action.get_duration() <= 1:
                    result = new_action.execute(self, world)
                    active_goal.on_action_completed(new_action, result.success, self, world)

                    # Gain experience for successful actions
                    if result.success:
                        self._gain_experience(new_action, 1)
                else:
                    # Multi-tick action - store for later completion
                    self.current_action = new_action

        if new_action:
            self.last_action_tick = world.current_tick
            self.idle_ticks = 0
        else:
            self.idle_ticks += 1

            # If idle too long, add a wander goal
            if self.idle_ticks > self.max_idle_ticks:
                from ..ai.goal import ExploreGoal
                self.current_goals.append(ExploreGoal(priority=2))
                self.idle_ticks = 0

    def _scan_for_entities(self, world: World) -> None:
        """Scan for nearby entities and update knowledge"""
        agent_x, agent_y = self.position

        for entity in world.entities.values():
            if entity.id == self.id:
                continue

            if not entity.stats.is_alive():
                continue

            distance = self.distance_to(entity)

            if distance <= self.vision_range:
                # Update knowledge of this entity
                self.known_entities[entity.id] = {
                    "position": entity.position,
                    "last_seen_tick": world.current_tick,
                    "type": type(entity).__name__,
                    "hostile": getattr(entity, "npc_type", "neutral") == "aggressive",
                    "health_percentage": entity.stats.get_health_percentage()
                }

    def _update_memory(self, world: World) -> None:
        """Clean up old memory entries"""
        current_tick = world.current_tick
        entities_to_remove = []

        for entity_id, info in self.known_entities.items():
            if current_tick - info["last_seen_tick"] > self.memory_duration:
                entities_to_remove.append(entity_id)

        for entity_id in entities_to_remove:
            del self.known_entities[entity_id]

    def _update_relationships(self, world: World) -> None:
        """Update relationships with other agents"""
        # Simplified relationship system - could be expanded
        for entity_id, info in self.known_entities.items():
            if info["type"] == "Agent":
                # Neutral decay towards 0
                if entity_id in self.relationships:
                    current_rel = self.relationships[entity_id]
                    self.relationships[entity_id] = current_rel * 0.99

    def _gain_experience(self, action: Action, amount: int) -> None:
        """Gain experience for performing actions"""
        self.total_experience += amount

        # Gain skill experience based on action type
        skill_name = self._get_skill_for_action(action)
        if skill_name:
            multiplier = self.character_class.get_skill_modifier(skill_name)
            skill_gain = int(amount * multiplier)

            current_skill = self.skills.get(skill_name, 0)
            self.skills[skill_name] = current_skill + skill_gain

    def _get_skill_for_action(self, action: Action) -> Optional[str]:
        """Map action types to skill names"""
        action_type = type(action).__name__

        skill_mapping = {
            "MeleeAttack": "combat",
            "RangedAttack": "archery",
            "MagicAttack": "magic",
            "GatherAction": "gathering",
            "FishAction": "fishing",
            "MineAction": "mining",
            "WoodcutAction": "woodcutting",
            "ForageAction": "foraging",
            "CraftAction": "crafting",
            "PathfindAction": "exploration"
        }

        return skill_mapping.get(action_type)

    def add_relationship(self, entity_id: int, relationship_change: float) -> None:
        """Modify relationship with another entity"""
        current = self.relationships.get(entity_id, 0.0)
        new_relationship = max(-1.0, min(1.0, current + relationship_change))
        self.relationships[entity_id] = new_relationship

    def get_relationship(self, entity_id: int) -> float:
        """Get relationship level with another entity (-1 to 1)"""
        return self.relationships.get(entity_id, 0.0)

    def is_hostile_to(self, entity: Entity) -> bool:
        """Check if this agent is hostile to another entity"""
        if hasattr(entity, 'npc_type') and entity.npc_type == "aggressive":
            return True  # Always hostile to aggressive NPCs

        if entity.id in self.relationships:
            return self.relationships[entity.id] < -0.3

        return False

    def get_skill_level(self, skill_name: str) -> int:
        """Get current level in a skill"""
        return self.skills.get(skill_name, 0)

    def get_dominant_skills(self, threshold: int = 5) -> List[Tuple[str, int]]:
        """Get skills above the threshold"""
        return [(skill, level) for skill, level in self.skills.items() if level >= threshold]

    def get_agent_summary(self) -> Dict:
        """Get a summary of the agent's state for debugging/analysis"""
        return {
            "id": self.id,
            "name": self.name,
            "position": self.position,
            "personality": self.personality.to_dict(),
            "character_class": self.character_class.name,
            "skills": self.skills.copy(),
            "current_goals": [str(goal) for goal in self.current_goals],
            "current_action": str(self.current_action) if self.current_action else None,
            "total_experience": self.total_experience,
            "relationships": len(self.relationships),
            "known_entities": len(self.known_entities),
            "health": f"{self.stats.health}/{self.stats.max_health}",
            "stamina": f"{self.stats.stamina}/{self.stats.max_stamina}",
            "inventory_items": len(self.inventory.get_all_items())
        }

    def on_death(self, killer: Optional[Entity] = None) -> None:
        """Handle agent death"""
        if killer and killer.id != self.id:
            # Negative relationship with killer
            if hasattr(killer, 'add_relationship'):
                killer.add_relationship(self.id, -0.5)

        # Clear current state
        self.current_goals.clear()
        self.current_action = None
        self.action_queue.clear()

    def __repr__(self) -> str:
        status = "alive" if self.stats.is_alive() else "dead"
        goals = len(self.current_goals)
        action = "acting" if self.current_action else "idle"
        return (f"Agent(id={self.id}, name='{self.name}', class={self.character_class.name}, "
                f"{status}, {action}, {goals} goals)")


def create_random_agent(position: Tuple[int, int], name: Optional[str] = None) -> Agent:
    """Create an agent with randomized personality and class"""
    if not name:
        # Generate a random name
        first_names = ["Alex", "Sam", "Jordan", "Casey", "Riley", "Avery", "Quinn", "Sage", "Blake", "Robin"]
        last_names = ["Smith", "Jones", "Brown", "Davis", "Wilson", "Clark", "Lewis", "Walker", "Hall", "Young"]
        name = f"{random.choice(first_names)} {random.choice(last_names)}"

    personality = Personality.randomize()
    character_class = get_random_character_class()

    # Adjust stats based on personality
    stats = Stats()

    # Brave agents get more health
    if personality.bravery > 0.7:
        stats.max_health += 10
        stats.health += 10

    # Industrious agents get more stamina
    if personality.industriousness > 0.7:
        stats.max_stamina += 15
        stats.stamina += 15

    return Agent(position, name, personality, character_class, stats)


def create_agent_with_archetype(
    position: Tuple[int, int],
    archetype: str,
    name: Optional[str] = None
) -> Agent:
    """Create an agent based on a personality archetype"""
    personality = Personality.create_archetype(archetype)

    # Choose appropriate class for archetype
    class_mapping = {
        "explorer": "explorer",
        "warrior": "warrior",
        "trader": "trader",
        "crafter": "blacksmith",
        "hermit": "alchemist",
        "bandit": "hunter"
    }

    from ..ai.character_class import get_character_class
    character_class = get_character_class(class_mapping.get(archetype, "warrior"))

    if not name:
        name = f"{archetype.title()} Agent"

    return Agent(position, name, personality, character_class)