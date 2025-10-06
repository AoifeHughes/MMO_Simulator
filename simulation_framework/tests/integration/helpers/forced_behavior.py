"""Deterministic agent and NPC classes for controlled testing"""

from typing import TYPE_CHECKING, List, Optional, Tuple

from src.ai.character_class import CharacterClass
from src.ai.goal import Goal
from src.ai.personality import Personality
from src.entities.agent import Agent
from src.entities.npc import NPC
from src.entities.stats import Stats
from src.items.loot_table import LootTable

if TYPE_CHECKING:
    from src.core.world import World


class ForcedBehaviorAgent(Agent):
    """
    Agent that executes only its assigned goals without decision-making.

    This agent bypasses the normal AI decision-making process and simply
    executes the goals it was given, making tests deterministic.
    """

    def __init__(
        self,
        position: Tuple[int, int],
        name: str = "TestAgent",
        personality: Optional[Personality] = None,
        character_class: Optional[CharacterClass] = None,
        stats: Optional[Stats] = None,
        goals: Optional[List[Goal]] = None,
    ):
        super().__init__(
            position=position,
            name=name,
            personality=personality
            or Personality(
                curiosity=0.5,
                bravery=0.5,
                sociability=0.5,
                greed=0.5,
                patience=0.5,
                aggression=0.5,
                industriousness=0.5,
                caution=0.5,
            ),
            character_class=character_class or CharacterClass.create_warrior(),
            stats=stats,
        )

        # Set initial goals if provided
        if goals:
            self.current_goals = goals

    def update(self, world: "World") -> None:
        """
        Update agent without decision-making - only execute assigned goals.

        This skips the DecisionMaker and only executes actions from current goals.
        """
        # Update status effects
        self.update_status_effects()

        # Don't make decisions if we have no goals
        if not self.current_goals:
            return

        # Remove completed or invalid goals
        self.current_goals = [
            goal
            for goal in self.current_goals
            if not goal.is_complete(self, world)
            and not goal.should_abandon(self, world)
        ]

        if not self.current_goals:
            return

        # Get the highest priority goal
        active_goal = self.current_goals[0]

        # If we don't have a current action, get one from the goal
        if not self.current_action or not self.current_action.is_active:
            action = active_goal.get_next_action(self, world)
            if action:
                self.current_action = action
                self.current_action.start(world.current_tick)


class ControlledNPC(NPC):
    """
    NPC with guaranteed aggro and simplified behavior for testing.

    This NPC will always aggro on specified targets and won't flee or
    exhibit complex behaviors that could make tests non-deterministic.
    """

    def __init__(
        self,
        position: Tuple[int, int],
        name: str = "TestNPC",
        npc_type: str = "aggressive",
        stats: Optional[Stats] = None,
        loot_table: Optional[LootTable] = None,
        aggro_range: int = 10,
        forced_target_id: Optional[int] = None,
    ):
        super().__init__(
            position=position,
            name=name,
            npc_type=npc_type,
            stats=stats
            or Stats(
                max_health=50,
                health=50,
                max_stamina=100,
                stamina=100,
                attack_power=10,
                defense=5,
            ),
            loot_table=loot_table or LootTable(),
            spawn_point=position,
            tether_radius=999,  # Effectively unlimited for testing
        )

        self.aggro_range = aggro_range
        self.forced_target_id = forced_target_id  # If set, always target this entity

    def update(self, world: "World") -> None:
        """
        Simplified update - just attack target or wander.

        No complex decision-making, no fleeing, no tether checks for tests.
        """
        self.update_status_effects()

        if not self.stats.is_alive():
            return

        # If we have a forced target, always use it
        if self.forced_target_id:
            self.target_id = self.forced_target_id

        # Combat behavior if we have a target
        if self.target_id and self._should_continue_combat(world):
            self._combat_behavior(world)
        elif self.npc_type == "aggressive":
            # Scan for targets
            self._scan_for_targets(world)

    def set_forced_target(self, target_id: int) -> None:
        """Force this NPC to always target a specific entity"""
        self.forced_target_id = target_id
        self.target_id = target_id


class StaticNPC(NPC):
    """
    NPC that doesn't move - stays in place for predictable testing.

    Useful for testing scenarios where you need an enemy that won't
    move around or chase the player.
    """

    def __init__(
        self,
        position: Tuple[int, int],
        name: str = "StaticNPC",
        stats: Optional[Stats] = None,
    ):
        super().__init__(
            position=position,
            name=name,
            npc_type="neutral",
            stats=stats
            or Stats(max_health=100, health=100, max_stamina=100, stamina=100),
            spawn_point=position,
            tether_radius=0,  # Won't move from spawn
        )

    def update(self, world: "World") -> None:
        """Do nothing - stay static"""
        self.update_status_effects()
        # Don't move, don't attack, don't do anything


def create_test_warrior(
    position: Tuple[int, int],
    name: str = "TestWarrior",
    goals: Optional[List[Goal]] = None,
) -> ForcedBehaviorAgent:
    """Create a warrior agent optimized for combat testing"""
    return ForcedBehaviorAgent(
        position=position,
        name=name,
        character_class=CharacterClass.create_warrior(),
        stats=Stats(
            max_health=100,
            health=100,
            max_stamina=100,
            stamina=100,
            attack_power=15,
            defense=10,
        ),
        goals=goals,
    )


def create_test_archer(
    position: Tuple[int, int],
    name: str = "TestArcher",
    goals: Optional[List[Goal]] = None,
) -> ForcedBehaviorAgent:
    """Create an archer agent optimized for ranged combat testing"""
    return ForcedBehaviorAgent(
        position=position,
        name=name,
        character_class=CharacterClass.create_hunter(),
        stats=Stats(
            max_health=80,
            health=80,
            max_stamina=100,
            stamina=100,
            attack_power=12,
            defense=5,
        ),
        goals=goals,
    )


def create_test_gatherer(
    position: Tuple[int, int],
    name: str = "TestGatherer",
    goals: Optional[List[Goal]] = None,
) -> ForcedBehaviorAgent:
    """Create a gatherer agent optimized for resource testing"""
    return ForcedBehaviorAgent(
        position=position,
        name=name,
        character_class=CharacterClass.create_explorer(),
        stats=Stats(
            max_health=70,
            health=70,
            max_stamina=120,
            stamina=120,
            attack_power=5,
            defense=3,
        ),
        goals=goals,
    )


def create_weak_goblin(
    position: Tuple[int, int], name: str = "WeakGoblin"
) -> ControlledNPC:
    """Create a weak goblin for guaranteed kill testing"""
    return ControlledNPC(
        position=position,
        name=name,
        npc_type="aggressive",
        stats=Stats(
            max_health=20,
            health=20,
            max_stamina=50,
            stamina=50,
            attack_power=3,
            defense=1,
        ),
        aggro_range=5,
    )


def create_strong_enemy(
    position: Tuple[int, int], name: str = "StrongEnemy"
) -> ControlledNPC:
    """Create a strong enemy for testing agent death scenarios"""
    return ControlledNPC(
        position=position,
        name=name,
        npc_type="aggressive",
        stats=Stats(
            max_health=200,
            health=200,
            max_stamina=150,
            stamina=150,
            attack_power=50,
            defense=20,
        ),
        aggro_range=10,
    )
