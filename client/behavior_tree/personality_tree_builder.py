"""
Personality-driven behavior tree builder.

This module replaces the static TreeFactory with a dynamic system that
builds behavior trees based on agent personality desires and priorities.
"""

import logging
import math
from typing import Dict, List, Optional, Any, Tuple

from shared.personality import Personality
from .tree import BehaviorTree
from .nodes import *

logger = logging.getLogger(__name__)


class PersonalityTreeBuilder:
    """
    Builds behavior trees dynamically based on agent personality.

    Instead of hardcoded tree structures, this system composes trees
    from modular behavior components weighted by personality desires.
    """

    def __init__(self):
        self.behavior_components = self._initialize_behavior_components()

    def build_tree(self, personality: Personality, agent_x: float, agent_y: float, **context) -> BehaviorTree:
        """
        Build a behavior tree tailored to the agent's personality.

        Args:
            personality: The agent's personality profile
            agent_x: Agent's spawn X position
            agent_y: Agent's spawn Y position
            **context: Additional context (home_base, patrol_radius, etc.)

        Returns:
            Dynamically composed behavior tree
        """
        # Get behavior priorities based on personality
        priorities = self._calculate_behavior_priorities(personality)

        # Build tree structure based on priorities
        root = self._build_priority_selector(
            "PersonalityDrivenRoot",
            personality,
            priorities,
            agent_x,
            agent_y,
            **context
        )

        tree_name = f"PersonalityTree_{personality.get_primary_desires(1)[0][0]}"
        logger.info(f"Built personality tree: {tree_name} with priorities: {priorities[:3]}")

        return BehaviorTree(root, tree_name)

    def _calculate_behavior_priorities(self, personality: Personality) -> List[Tuple[str, float]]:
        """Calculate behavior priorities based on personality desires"""
        # Map desires to behavior categories
        behavior_weights = {
            'emergency': 10.0,  # Always highest priority regardless of personality
            'combat': personality.combat,
            'exploration': personality.exploration,
            'fishing': personality.fishing,
            'social': personality.social,
            'foraging': personality.foraging,
            'building': personality.building,
            'patrol': (personality.exploration + personality.social) / 2.0,  # Combination behavior
            'idle': personality.patience / 2.0,  # Low-patience agents idle less
        }

        # Sort by priority (highest first)
        priorities = [(behavior, weight) for behavior, weight in behavior_weights.items()]
        priorities.sort(key=lambda x: x[1], reverse=True)

        return priorities

    def _build_priority_selector(self, name: str, personality: Personality,
                                priorities: List[Tuple[str, float]],
                                agent_x: float, agent_y: float, **context) -> PrioritySelector:
        """Build the main priority selector with personality-weighted behaviors"""

        children = []

        for behavior, priority in priorities:
            if priority < 1.0:  # Skip very low priority behaviors
                continue

            behavior_node = self._create_behavior_node(
                behavior, personality, priority, agent_x, agent_y, **context
            )

            if behavior_node:
                children.append(behavior_node)

        if not children:
            # Fallback to basic idle behavior
            children = [Idle(3.0)]

        return PrioritySelector(name, children)

    def _create_behavior_node(self, behavior: str, personality: Personality,
                             priority: float, agent_x: float, agent_y: float,
                             **context) -> Optional[Any]:
        """Create a specific behavior node based on type and personality"""

        if behavior == 'emergency':
            return self._create_emergency_behavior(personality)

        elif behavior == 'combat':
            return self._create_combat_behavior(personality, **context)

        elif behavior == 'exploration':
            return self._create_exploration_behavior(personality, agent_x, agent_y, **context)

        elif behavior == 'fishing':
            return self._create_fishing_behavior(personality, **context)

        elif behavior == 'social':
            return self._create_social_behavior(personality, agent_x, agent_y, **context)

        elif behavior == 'foraging':
            return self._create_foraging_behavior(personality, agent_x, agent_y, **context)

        elif behavior == 'building':
            return self._create_building_behavior(personality, **context)

        elif behavior == 'patrol':
            return self._create_patrol_behavior(personality, agent_x, agent_y, **context)

        elif behavior == 'idle':
            return self._create_idle_behavior(personality)

        return None

    def _create_emergency_behavior(self, personality: Personality) -> Sequence:
        """Create emergency behavior (low health response)"""
        # Health threshold varies by risk tolerance
        health_threshold = 15.0 + (personality.risk_tolerance * 2.0)  # 15-35 health

        # Flight duration varies by patience
        flee_duration = max(3.0, 8.0 - personality.patience)  # 3-8 seconds

        return Sequence(
            "EmergencyResponse",
            [
                HealthBelowThreshold(health_threshold),
                TimerDecorator(
                    "EmergencyFlee",
                    CooldownDecorator(
                        "FleeExecution",
                        Wander(0, 0, 20.0),  # Flee in any direction
                        cooldown_duration=1.0
                    ),
                    minimum_duration=flee_duration
                )
            ]
        )

    def _create_combat_behavior(self, personality: Personality, **context) -> Optional[Sequence]:
        """Create combat behavior based on personality"""
        if personality.combat < 2.0:
            return None  # Peaceful personalities skip combat

        # Determine enemy types based on cooperativeness
        if personality.cooperativeness < 5.0:
            enemy_types = ["player", "npc"]  # Hostile to everyone
        else:
            enemy_types = ["enemy"]  # Only hostile to designated enemies

        # Combat range varies by risk tolerance
        chase_range = 12.0 + (personality.risk_tolerance * 1.5)  # 12-27 units

        # Commitment duration varies by patience and combat desire
        commitment_duration = max(2.0, (personality.patience + personality.combat) / 5.0)  # 2-4 seconds

        return Sequence(
            "CombatEngagement",
            [
                # Health check - more cautious personalities need more health
                HealthAboveThreshold(20.0 + (10.0 - personality.risk_tolerance) * 2.0),
                DynamicEnemyInChaseRange(chase_range, enemy_types),
                TimerDecorator(
                    "CombatCommitment",
                    self._create_combat_state_machine(personality, enemy_types),
                    minimum_duration=commitment_duration
                )
            ]
        )

    def _create_combat_state_machine(self, personality: Personality, enemy_types: List[str]) -> PrioritySelector:
        """Create the internal combat state machine"""
        children = []

        # High-combat personalities try weapon selection if available
        if personality.combat > 7.0:
            children.append(
                Sequence(
                    "WeaponBasedCombat",
                    [
                        IsInWeaponRange(enemy_types),
                        AttackWithBestWeapon(enemy_types=enemy_types)
                    ]
                )
            )

        # Standard attack sequence
        children.extend([
            Sequence(
                "StandardAttack",
                [
                    DynamicEnemyInRange("sword_slash", enemy_types),
                    CooldownDecorator(
                        "AttackExecution",
                        AttackNearestEnemy(
                            attack_name="sword_slash",
                            damage=15.0,
                            attack_range=2.5,
                            enemy_types=enemy_types
                        ),
                        cooldown_duration=1.5
                    )
                ]
            ),
            # Chase behavior
            CooldownDecorator(
                "ChaseEnemy",
                ChaseNearestEnemy(enemy_types=enemy_types, chase_range=15.0),
                cooldown_duration=0.3
            )
        ])

        return PrioritySelector("CombatStateMachine", children)

    def _create_exploration_behavior(self, personality: Personality,
                                   agent_x: float, agent_y: float, **context) -> Optional[Sequence]:
        """Create exploration behavior"""
        if personality.exploration < 2.0:
            return None

        # Exploration radius based on exploration desire and risk tolerance
        base_radius = 20.0
        exploration_radius = base_radius + (personality.exploration * 3.0) + (personality.risk_tolerance * 2.0)

        # Exploration mode based on other desires
        if personality.fishing > 6.0:
            mode = "water_seeking"
        elif personality.foraging > 6.0:
            mode = "resource_seeking"
        else:
            mode = "frontier"

        # Commitment duration based on patience
        commitment_duration = max(2.0, personality.patience / 2.0)

        return CooldownDecorator(
            "ExplorationCooldown",
            TimerDecorator(
                "ExplorationCommitment",
                Explore(exploration_radius, mode),
                minimum_duration=commitment_duration
            ),
            cooldown_duration=max(0.5, 2.0 - personality.exploration / 5.0)
        )

    def _create_fishing_behavior(self, personality: Personality, **context) -> Optional[Sequence]:
        """Create fishing behavior"""
        if personality.fishing < 3.0:
            return None

        # Fishing commitment varies by patience and fishing desire
        fishing_duration = max(3.0, (personality.patience + personality.fishing) / 2.0)

        return Sequence(
            "FishingBehavior",
            [
                HasFishingRod(),
                PrioritySelector(
                    "FishingSelector",
                    [
                        # Fish if at water
                        Sequence(
                            "FishAtLocation",
                            [
                                WaterNearby(1.5),
                                TimerDecorator(
                                    "FishingCommitment",
                                    CooldownDecorator(
                                        "FishingAction",
                                        FishAtWater(1.5),
                                        cooldown_duration=2.0
                                    ),
                                    minimum_duration=fishing_duration
                                )
                            ]
                        ),
                        # Move to water if known
                        Sequence(
                            "MoveToWater",
                            [
                                WaterDiscoveredButNotNearby(1.5),
                                TimerDecorator(
                                    "MoveToWaterTimer",
                                    MoveToFishingSpot(1.5),
                                    minimum_duration=2.0
                                )
                            ]
                        )
                    ]
                )
            ]
        )

    def _create_social_behavior(self, personality: Personality,
                               agent_x: float, agent_y: float, **context) -> Optional[Sequence]:
        """Create social interaction behavior"""
        if personality.social < 3.0:
            return None

        # Social range based on social desire
        social_range = 8.0 + personality.social

        return Sequence(
            "SocialBehavior",
            [
                NearOtherAgent(["player", "npc"], social_range),
                CooldownDecorator(
                    "SocialInteraction",
                    Idle(2.0),  # Simple interaction - could be expanded
                    cooldown_duration=5.0 - personality.social / 2.0  # More social = shorter cooldown
                )
            ]
        )

    def _create_foraging_behavior(self, personality: Personality,
                                 agent_x: float, agent_y: float, **context) -> Optional[CooldownDecorator]:
        """Create resource foraging behavior"""
        if personality.foraging < 3.0:
            return None

        # Foraging is a type of exploration focused on resources
        forage_radius = 15.0 + personality.foraging * 2.0

        return CooldownDecorator(
            "ForagingBehavior",
            TimerDecorator(
                "ForagingTimer",
                Explore(forage_radius, "resource_seeking"),
                minimum_duration=max(2.0, personality.patience / 2.0)
            ),
            cooldown_duration=max(1.0, 3.0 - personality.foraging / 3.0)
        )

    def _create_building_behavior(self, personality: Personality, **context) -> Optional[Sequence]:
        """Create building/crafting behavior (placeholder for future expansion)"""
        if personality.building < 4.0:
            return None

        # For now, building translates to staying in one area
        return Sequence(
            "BuildingBehavior",
            [
                CustomCondition(
                    lambda agent: True,  # Always try to build if personality supports it
                    "BuildingOpportunity"
                ),
                TimerDecorator(
                    "BuildingActivity",
                    Idle(personality.building),  # Duration based on building desire
                    minimum_duration=personality.building
                )
            ]
        )

    def _create_patrol_behavior(self, personality: Personality,
                               agent_x: float, agent_y: float, **context) -> Optional[CooldownDecorator]:
        """Create patrol behavior"""
        patrol_radius = context.get('patrol_radius', 8.0)

        # Adjust patrol radius based on exploration and social desires
        adjusted_radius = patrol_radius + (personality.exploration + personality.social) / 5.0

        # Create patrol points
        patrol_points = []
        num_points = max(3, int(personality.patience / 2.0))  # 3-5 points
        for i in range(num_points):
            angle = (2 * math.pi / num_points) * i
            px = agent_x + math.cos(angle) * adjusted_radius
            py = agent_y + math.sin(angle) * adjusted_radius
            patrol_points.append((px, py))

        commitment_duration = max(2.0, personality.patience / 2.0)

        return CooldownDecorator(
            "PatrolBehavior",
            TimerDecorator(
                "PatrolCommitment",
                Patrol(patrol_points),
                minimum_duration=commitment_duration
            ),
            cooldown_duration=max(1.0, 3.0 - personality.social / 3.0)
        )

    def _create_idle_behavior(self, personality: Personality) -> TimerDecorator:
        """Create idle behavior based on personality"""
        # Idle duration varies by patience - impatient agents idle briefly
        idle_duration = max(1.0, personality.patience / 2.0)
        minimum_duration = max(0.5, personality.patience / 4.0)

        return TimerDecorator(
            "IdleCommitment",
            Idle(idle_duration),
            minimum_duration=minimum_duration
        )

    def _initialize_behavior_components(self) -> Dict[str, Any]:
        """Initialize available behavior components"""
        # Future expansion: modular behavior components that can be mixed and matched
        return {
            'emergency_behaviors': ['flee', 'hide', 'call_for_help'],
            'combat_behaviors': ['attack', 'defend', 'tactical_retreat'],
            'exploration_behaviors': ['frontier', 'spiral', 'random'],
            'social_behaviors': ['greet', 'trade', 'follow', 'guard'],
            'economic_behaviors': ['gather', 'craft', 'trade', 'hoard']
        }

    def get_tree_debug_info(self, tree: BehaviorTree, personality: Personality) -> Dict[str, Any]:
        """Get debug information about a generated tree"""
        priorities = self._calculate_behavior_priorities(personality)

        return {
            'tree_name': tree.name,
            'personality_archetype': personality.get_primary_desires(1)[0][0],
            'behavior_priorities': priorities[:5],
            'tree_depth': self._calculate_tree_depth(tree.root),
            'node_count': self._count_nodes(tree.root)
        }

    def _calculate_tree_depth(self, node) -> int:
        """Calculate the maximum depth of the behavior tree"""
        if not hasattr(node, 'children') or not node.children:
            return 1

        return 1 + max(self._calculate_tree_depth(child) for child in node.children)

    def _count_nodes(self, node) -> int:
        """Count the total number of nodes in the tree"""
        count = 1
        if hasattr(node, 'children') and node.children:
            count += sum(self._count_nodes(child) for child in node.children)
        elif hasattr(node, 'child') and node.child:
            count += self._count_nodes(node.child)

        return count


# Global instance for easy access
personality_tree_builder = PersonalityTreeBuilder()