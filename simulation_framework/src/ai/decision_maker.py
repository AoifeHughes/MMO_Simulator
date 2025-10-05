from __future__ import annotations
from typing import List, Tuple, Dict, Optional, TYPE_CHECKING
import random
import math

from .goal import (
    Goal, ExploreGoal, GatherResourceGoal, CraftItemGoal,
    AttackEnemyGoal, FleeFromDangerGoal, RestGoal
)

if TYPE_CHECKING:
    from ..entities.base import Entity
    from ..core.world import World


class DecisionMaker:
    def __init__(self):
        self.goal_history: Dict[str, int] = {}  # Track how often goals are selected
        self.last_decision_tick = 0
        self.decision_cooldown = 3  # Ticks between decisions

    def evaluate_all_goals(
        self,
        agent: Entity,
        world: World,
        current_goals: List[Goal]
    ) -> List[Tuple[Goal, float]]:
        """Evaluate utility of all possible goals"""
        goal_utilities = []

        # Evaluate existing goals
        for goal in current_goals:
            if not goal.should_abandon(agent, world):
                utility = self._calculate_goal_utility(goal, agent, world)
                goal_utilities.append((goal, utility))

        # Generate new potential goals
        new_goals = self._generate_potential_goals(agent, world)
        for goal in new_goals:
            utility = self._calculate_goal_utility(goal, agent, world)
            goal_utilities.append((goal, utility))

        return goal_utilities

    def select_goal(
        self,
        agent: Entity,
        world: World,
        current_goals: List[Goal],
        selection_method: str = "utility_weighted"
    ) -> Optional[Goal]:
        """Select the best goal for the agent"""

        if world.current_tick < self.last_decision_tick + self.decision_cooldown:
            # Return current goal if still valid
            if current_goals:
                for goal in current_goals:
                    if not goal.should_abandon(agent, world):
                        return goal
            return None

        self.last_decision_tick = world.current_tick

        goal_utilities = self.evaluate_all_goals(agent, world, current_goals)

        if not goal_utilities:
            # Emergency goal - rest if nothing else
            return RestGoal(priority=1)

        # Sort by utility
        goal_utilities.sort(key=lambda x: x[1], reverse=True)

        if selection_method == "highest_utility":
            return goal_utilities[0][0]
        elif selection_method == "utility_weighted":
            return self._weighted_selection(goal_utilities)
        else:
            return goal_utilities[0][0]

    def _calculate_goal_utility(self, goal: Goal, agent: Entity, world: World) -> float:
        """Calculate the total utility of a goal"""
        base_utility = goal.get_utility(agent, world)

        # Personality modifiers
        personality_modifier = self._get_personality_modifier(goal, agent)

        # Class modifiers
        class_modifier = self._get_class_modifier(goal, agent)

        # Context modifiers
        context_modifier = self._get_context_modifier(goal, agent, world)

        # History modifier (avoid repeated goals)
        history_modifier = self._get_history_modifier(goal)

        total_utility = (
            base_utility *
            personality_modifier *
            class_modifier *
            context_modifier *
            history_modifier
        )

        return max(0.0, min(1.0, total_utility))

    def _get_personality_modifier(self, goal: Goal, agent: Entity) -> float:
        """Get personality-based utility modifier"""
        if not hasattr(agent, 'personality'):
            return 1.0

        personality = agent.personality
        modifier = 1.0

        if isinstance(goal, ExploreGoal):
            modifier = personality.curiosity * 1.5 + personality.bravery * 0.5
        elif isinstance(goal, GatherResourceGoal):
            modifier = personality.industriousness * 1.3 + personality.greed * 0.4
        elif isinstance(goal, CraftItemGoal):
            modifier = personality.industriousness * 1.2 + personality.patience * 0.8
        elif isinstance(goal, AttackEnemyGoal):
            modifier = personality.aggression * 1.5 + personality.bravery * 0.8
        elif isinstance(goal, FleeFromDangerGoal):
            modifier = personality.caution * 1.5 + (1.0 - personality.bravery) * 0.5
        elif isinstance(goal, RestGoal):
            modifier = personality.patience * 0.8 + personality.caution * 0.4

        return max(0.2, min(2.0, modifier))

    def _get_class_modifier(self, goal: Goal, agent: Entity) -> float:
        """Get character class-based utility modifier"""
        if not hasattr(agent, 'character_class'):
            return 1.0

        character_class = agent.character_class
        modifier = 1.0

        if isinstance(goal, ExploreGoal):
            if character_class.name in ["Explorer", "Hunter"]:
                modifier = 1.4
        elif isinstance(goal, GatherResourceGoal):
            if character_class.name in ["Hunter", "Alchemist", "Blacksmith", "Farmer"]:
                modifier = 1.3
        elif isinstance(goal, CraftItemGoal):
            if character_class.name in ["Blacksmith", "Alchemist", "Mage"]:
                modifier = 1.5
        elif isinstance(goal, AttackEnemyGoal):
            if character_class.name in ["Warrior", "Hunter"]:
                modifier = 1.4

        return modifier

    def _get_context_modifier(self, goal: Goal, agent: Entity, world: World) -> float:
        """Get context-based utility modifier"""
        modifier = 1.0

        # Health-based modifiers
        health_ratio = agent.stats.get_health_percentage()
        stamina_ratio = agent.stats.get_stamina_percentage()

        if health_ratio < 0.3 or stamina_ratio < 0.2:
            if isinstance(goal, RestGoal):
                modifier *= 2.0
            elif isinstance(goal, (AttackEnemyGoal, ExploreGoal)):
                modifier *= 0.3

        # Inventory space modifiers
        inventory_full = agent.inventory.get_total_items() >= agent.inventory.capacity * 0.9

        if inventory_full:
            if isinstance(goal, GatherResourceGoal):
                modifier *= 0.2
            elif isinstance(goal, CraftItemGoal):
                modifier *= 1.5  # Crafting uses materials

        # Time of day / environmental modifiers could be added here

        return modifier

    def _get_history_modifier(self, goal: Goal) -> float:
        """Get modifier based on goal selection history"""
        goal_type = type(goal).__name__

        recent_selections = self.goal_history.get(goal_type, 0)

        if recent_selections > 3:
            return 0.7  # Reduce likelihood of repeated goals
        elif recent_selections > 1:
            return 0.85
        else:
            return 1.0

    def _weighted_selection(self, goal_utilities: List[Tuple[Goal, float]]) -> Goal:
        """Select goal using weighted random selection"""
        if not goal_utilities:
            return RestGoal()

        # Normalize utilities
        total_utility = sum(utility for _, utility in goal_utilities)
        if total_utility <= 0:
            return goal_utilities[0][0]

        # Create weighted list
        weights = [utility / total_utility for _, utility in goal_utilities]

        # Random selection
        rand = random.random()
        cumulative = 0.0

        for i, weight in enumerate(weights):
            cumulative += weight
            if rand <= cumulative:
                selected_goal = goal_utilities[i][0]
                # Update history
                goal_type = type(selected_goal).__name__
                self.goal_history[goal_type] = self.goal_history.get(goal_type, 0) + 1
                return selected_goal

        # Fallback to highest utility
        return goal_utilities[0][0]

    def _generate_potential_goals(self, agent: Entity, world: World) -> List[Goal]:
        """Generate potential new goals based on agent state and world"""
        potential_goals = []

        # Always consider resting if tired
        if (agent.stats.get_stamina_percentage() < 0.5 or
            agent.stats.get_health_percentage() < 0.7):
            potential_goals.append(RestGoal())

        # Exploration goals
        if hasattr(agent, 'personality') and agent.personality.curiosity > 0.4:
            potential_goals.append(ExploreGoal())

        # Gathering goals based on needs and preferences
        needed_resources = self._identify_needed_resources(agent)
        for resource in needed_resources:
            potential_goals.append(GatherResourceGoal(resource, target_quantity=5))

        # Combat goals - look for nearby enemies
        enemies = self._find_nearby_enemies(agent, world, range_limit=10)
        for enemy in enemies:
            if self._should_consider_combat(agent, enemy):
                potential_goals.append(AttackEnemyGoal(enemy.id))

        # Flee goals - check for immediate threats
        threats = self._find_immediate_threats(agent, world)
        for threat in threats:
            potential_goals.append(FleeFromDangerGoal(threat.id))

        return potential_goals

    def _identify_needed_resources(self, agent: Entity) -> List[str]:
        """Identify what resources the agent currently needs"""
        needed = []

        # Basic needs
        if agent.inventory.get_item_count("Bread") < 3:
            needed.append("berries")  # For food

        if not agent.inventory.get_equipped_weapon():
            needed.append("wood")  # For crafting weapons

        # Class-specific needs
        if hasattr(agent, 'character_class'):
            if agent.character_class.name == "Blacksmith":
                if agent.inventory.get_item_count("Iron Ore") < 5:
                    needed.append("iron_ore")
            elif agent.character_class.name == "Alchemist":
                if agent.inventory.get_item_count("Herbs") < 3:
                    needed.append("herbs")

        return needed[:2]  # Limit to 2 most important needs

    def _find_nearby_enemies(self, agent: Entity, world: World, range_limit: int = 10) -> List:
        """Find potential enemies within range"""
        enemies = []
        agent_x, agent_y = agent.position

        for entity in world.entities.values():
            if entity.id == agent.id:
                continue

            if not entity.stats.is_alive():
                continue

            # Check if it's an NPC that could be hostile
            if hasattr(entity, 'npc_type') and entity.npc_type == "aggressive":
                distance = agent.distance_to(entity)
                if distance <= range_limit:
                    enemies.append(entity)

        return enemies

    def _should_consider_combat(self, agent: Entity, enemy: Entity) -> bool:
        """Determine if agent should consider fighting this enemy"""
        if not hasattr(agent, 'personality'):
            return False

        # Check relative strength
        agent_power = agent.stats.attack_power + agent.stats.defense
        enemy_power = enemy.stats.attack_power + enemy.stats.defense

        strength_ratio = agent_power / max(enemy_power, 1)

        # Factor in personality
        combat_willingness = (
            agent.personality.bravery * 0.4 +
            agent.personality.aggression * 0.4 +
            (1.0 - agent.personality.caution) * 0.2
        )

        # Adjust for strength
        if strength_ratio > 1.5:
            combat_willingness *= 1.3
        elif strength_ratio < 0.8:
            combat_willingness *= 0.5

        return random.random() < combat_willingness

    def _find_immediate_threats(self, agent: Entity, world: World, range_limit: int = 5) -> List:
        """Find immediate threats that agent should flee from"""
        threats = []

        for entity in world.entities.values():
            if entity.id == agent.id:
                continue

            if not entity.stats.is_alive():
                continue

            # Check if entity is hostile and nearby
            if (hasattr(entity, 'npc_type') and entity.npc_type == "aggressive" and
                hasattr(entity, 'target_id') and entity.target_id == agent.id):

                distance = agent.distance_to(entity)
                if distance <= range_limit:
                    # Check if we should flee
                    if self._should_flee_from(agent, entity):
                        threats.append(entity)

        return threats

    def _should_flee_from(self, agent: Entity, threat: Entity) -> bool:
        """Determine if agent should flee from this threat"""
        if not hasattr(agent, 'personality'):
            return True  # Default to caution

        # Check relative strength
        agent_power = agent.stats.attack_power + agent.stats.defense + agent.stats.health
        threat_power = threat.stats.attack_power + threat.stats.defense + threat.stats.health

        strength_ratio = agent_power / max(threat_power, 1)

        # Factor in personality and health
        flee_tendency = (
            agent.personality.caution * 0.5 +
            (1.0 - agent.personality.bravery) * 0.3 +
            (1.0 - agent.stats.get_health_percentage()) * 0.2
        )

        # Adjust for strength difference
        if strength_ratio < 0.7:  # Much weaker
            flee_tendency *= 1.5
        elif strength_ratio > 1.3:  # Much stronger
            flee_tendency *= 0.5

        # For very high flee tendency (>0.6), make it deterministic for testing
        if flee_tendency > 0.6:
            return True
        return random.random() < flee_tendency

    def reset_decision_cooldown(self) -> None:
        """Reset the decision cooldown (for testing or special cases)"""
        self.last_decision_tick = 0

    def get_decision_summary(self, agent: Entity) -> Dict[str, any]:
        """Get summary of decision-making state for debugging"""
        return {
            "last_decision_tick": self.last_decision_tick,
            "goal_history": self.goal_history.copy(),
            "decision_cooldown": self.decision_cooldown,
            "agent_personality": agent.personality.to_dict() if hasattr(agent, 'personality') else None,
            "agent_class": str(agent.character_class) if hasattr(agent, 'character_class') else None
        }