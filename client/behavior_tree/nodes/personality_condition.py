"""
Personality-aware condition nodes for behavior trees.

These nodes allow behavior trees to make decisions based on agent personality.
"""

import logging
from typing import Callable, List

from .base import ConditionNode

logger = logging.getLogger(__name__)


class PersonalityCondition(ConditionNode):
    """
    Condition node that checks personality desires against thresholds.
    """

    def __init__(self, desire: str, threshold: float, comparison: str = ">="):
        """
        Initialize personality condition.

        Args:
            desire: Name of the desire to check (e.g., "combat", "exploration")
            threshold: Value to compare against (0-10)
            comparison: Comparison operator (">=", "<=", ">", "<", "==")
        """
        super().__init__(f"PersonalityCondition_{desire}_{comparison}_{threshold}")
        self.desire = desire
        self.threshold = threshold
        self.comparison = comparison

    def check_condition(self, agent) -> bool:
        """Check if agent's personality desire meets the threshold"""
        if not hasattr(agent, "personality") or not agent.personality:
            return False

        desire_value = agent.personality.get_desire_priority(self.desire)

        if self.comparison == ">=":
            return desire_value >= self.threshold
        elif self.comparison == "<=":
            return desire_value <= self.threshold
        elif self.comparison == ">":
            return desire_value > self.threshold
        elif self.comparison == "<":
            return desire_value < self.threshold
        elif self.comparison == "==":
            return (
                abs(desire_value - self.threshold) < 0.1
            )  # Allow for floating point comparison
        else:
            logger.warning(f"Unknown comparison operator: {self.comparison}")
            return False


class PersonalityPriorityCondition(ConditionNode):
    """
    Check if one desire is higher priority than another for this agent.
    """

    def __init__(self, primary_desire: str, secondary_desire: str):
        """
        Initialize priority condition.

        Args:
            primary_desire: Desire that should be higher
            secondary_desire: Desire that should be lower
        """
        super().__init__(
            f"PersonalityPriority_{primary_desire}_over_{secondary_desire}"
        )
        self.primary_desire = primary_desire
        self.secondary_desire = secondary_desire

    def check_condition(self, agent) -> bool:
        """Check if primary desire has higher priority than secondary"""
        if not hasattr(agent, "personality") or not agent.personality:
            return False

        return agent.personality.should_prioritize(
            self.primary_desire, self.secondary_desire
        )


class PersonalityActivityMotivation(ConditionNode):
    """
    Check if agent is motivated enough to engage in a specific activity.
    """

    def __init__(self, activity: str, minimum_motivation: float = 5.0):
        """
        Initialize activity motivation condition.

        Args:
            activity: Name of the activity
            minimum_motivation: Minimum motivation score (0-10)
        """
        super().__init__(f"ActivityMotivation_{activity}_{minimum_motivation}")
        self.activity = activity
        self.minimum_motivation = minimum_motivation

    def check_condition(self, agent) -> bool:
        """Check if agent is motivated enough for the activity"""
        if not hasattr(agent, "personality") or not agent.personality:
            return False

        if hasattr(agent, "should_engage_in_activity"):
            motivation = agent.should_engage_in_activity(self.activity)
            return motivation >= self.minimum_motivation
        else:
            # Fallback to basic personality check
            desire_value = agent.personality.get_desire_priority(self.activity)
            return desire_value >= self.minimum_motivation


class PersonalityCompatibility(ConditionNode):
    """
    Check if agent's personality is compatible with nearby agents for cooperation.
    """

    def __init__(self, range_check: float = 10.0, compatibility_threshold: float = 5.0):
        """
        Initialize compatibility condition.

        Args:
            range_check: How far to look for other agents
            compatibility_threshold: Minimum compatibility score
        """
        super().__init__(
            f"PersonalityCompatibility_{range_check}_{compatibility_threshold}"
        )
        self.range_check = range_check
        self.compatibility_threshold = compatibility_threshold

    def check_condition(self, agent) -> bool:
        """Check if any nearby agents are compatible"""
        if not hasattr(agent, "personality") or not agent.personality:
            return False

        if not hasattr(agent, "visible_entities"):
            return False

        for entity in agent.visible_entities:
            # Skip non-agents or self
            if not entity.get("agent_type") or entity.get("id") == agent.id:
                continue

            # Check distance
            dx = entity.get("x", 0) - agent.x
            dy = entity.get("y", 0) - agent.y
            distance = (dx * dx + dy * dy) ** 0.5

            if distance <= self.range_check:
                # For now, assume compatibility (would need other agent's personality)
                # This is a placeholder for future expansion
                return True

        return False


class PersonalityArchetypeMatch(ConditionNode):
    """
    Check if agent matches a specific personality archetype.
    """

    def __init__(self, archetype_name: str):
        """
        Initialize archetype match condition.

        Args:
            archetype_name: Name of archetype to match against
        """
        super().__init__(f"ArchetypeMatch_{archetype_name}")
        self.archetype_name = archetype_name.lower()

    def check_condition(self, agent) -> bool:
        """Check if agent matches the archetype"""
        if hasattr(agent, "archetype_name"):
            return agent.archetype_name.lower() == self.archetype_name

        if hasattr(agent, "get_personality_type"):
            return agent.get_personality_type().lower() == self.archetype_name

        return False


# Convenience factory functions for common personality conditions


def high_combat_drive(threshold: float = 7.0) -> PersonalityCondition:
    """Condition for agents with high combat drive"""
    return PersonalityCondition("combat", threshold, ">=")


def high_exploration_drive(threshold: float = 7.0) -> PersonalityCondition:
    """Condition for agents with high exploration drive"""
    return PersonalityCondition("exploration", threshold, ">=")


def low_risk_tolerance(threshold: float = 4.0) -> PersonalityCondition:
    """Condition for cautious agents"""
    return PersonalityCondition("risk_tolerance", threshold, "<=")


def high_social_desire(threshold: float = 6.0) -> PersonalityCondition:
    """Condition for socially motivated agents"""
    return PersonalityCondition("social", threshold, ">=")


def prefers_combat_over_exploration() -> PersonalityPriorityCondition:
    """Condition for agents who prefer combat to exploration"""
    return PersonalityPriorityCondition("combat", "exploration")


def motivated_to_fish(threshold: float = 6.0) -> PersonalityActivityMotivation:
    """Condition for agents motivated to fish"""
    return PersonalityActivityMotivation("fishing", threshold)


def motivated_to_explore(threshold: float = 5.0) -> PersonalityActivityMotivation:
    """Condition for agents motivated to explore"""
    return PersonalityActivityMotivation("exploration", threshold)
