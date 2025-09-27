"""
Personality system for agents in the MMO Simulator.

This module defines the core personality framework that replaces the rigid
agent type system with flexible desire-driven behavior.
"""

import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Personality:
    """
    Represents an agent's personality through various desire attributes.

    Each desire is rated 0-10 where:
    - 0 = No interest/drive
    - 5 = Moderate interest
    - 10 = Maximum drive/obsession

    These desires determine behavior tree priorities and decision making.
    """

    # Core desires that drive agent behavior
    exploration: float = 5.0  # Drive to explore unknown areas
    combat: float = 5.0  # Inclination towards fighting/aggression
    money: float = 5.0  # Desire to accumulate wealth/resources
    social: float = 5.0  # Interest in interacting with others
    fishing: float = 5.0  # Preference for fishing activities
    farming: float = 5.0  # Interest in growing crops
    foraging: float = 5.0  # Drive to gather natural resources
    cooking: float = 5.0  # Interest in food preparation
    building: float = 5.0  # Desire to construct/craft

    # Personality traits that modify behavior
    risk_tolerance: float = 5.0  # Willingness to take risks (0=cautious, 10=reckless)
    patience: float = 5.0  # How long they stick with activities
    cooperativeness: float = 5.0  # Tendency to work with others

    def __post_init__(self):
        """Validate and clamp desire values to 0-10 range"""
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)):
                raise ValueError(f"{field_name} must be a number, got {type(value)}")

            # Clamp to valid range
            clamped_value = max(0.0, min(10.0, float(value)))
            setattr(self, field_name, clamped_value)

    def get_primary_desires(self, count: int = 3) -> List[Tuple[str, float]]:
        """
        Get the top N desires for this personality.

        Returns:
            List of (desire_name, value) tuples sorted by value (highest first)
        """
        desire_fields = [
            "exploration",
            "combat",
            "money",
            "social",
            "fishing",
            "farming",
            "foraging",
            "cooking",
            "building",
        ]

        desires = [(name, getattr(self, name)) for name in desire_fields]
        desires.sort(key=lambda x: x[1], reverse=True)
        return desires[:count]

    def get_desire_priority(self, desire: str) -> float:
        """Get the priority value for a specific desire (0-10)"""
        if hasattr(self, desire):
            return getattr(self, desire)
        return 0.0

    def should_prioritize(self, desire_a: str, desire_b: str) -> bool:
        """Check if desire_a should be prioritized over desire_b"""
        return self.get_desire_priority(desire_a) > self.get_desire_priority(desire_b)

    def calculate_activity_score(self, activity_desires: Dict[str, float]) -> float:
        """
        Calculate how much this personality would enjoy an activity.

        Args:
            activity_desires: Dict mapping desires to their importance for the activity
                             e.g., {"combat": 0.8, "exploration": 0.3}

        Returns:
            Weighted score based on personality desires
        """
        total_score = 0.0
        total_weight = 0.0

        for desire, weight in activity_desires.items():
            if hasattr(self, desire):
                personality_value = getattr(self, desire)
                total_score += personality_value * weight
                total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.0

    def is_compatible_with(self, other: "Personality", threshold: float = 5.0) -> bool:
        """Check if this personality is compatible with another for cooperation"""
        # High cooperativeness makes compatibility easier
        cooperation_bonus = (self.cooperativeness + other.cooperativeness) / 20.0

        # Calculate difference in core desires
        desire_fields = ["exploration", "combat", "money", "social"]
        total_difference = 0.0

        for field in desire_fields:
            diff = abs(getattr(self, field) - getattr(other, field))
            total_difference += diff

        avg_difference = total_difference / len(desire_fields)
        compatibility_score = 10.0 - avg_difference + cooperation_bonus * 2.0

        return compatibility_score >= threshold

    def to_dict(self) -> Dict[str, Any]:
        """Convert personality to dictionary for serialization"""
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Personality":
        """Create personality from dictionary"""
        # Filter to only include valid fields
        valid_fields = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)

    def to_json(self) -> str:
        """Convert personality to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Personality":
        """Create personality from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __str__(self) -> str:
        """Human-readable personality description"""
        primary = self.get_primary_desires(3)
        primary_str = ", ".join(f"{name}:{value:.1f}" for name, value in primary)
        return f"Personality({primary_str})"


class PersonalityArchetype:
    """
    Predefined personality archetypes that replace the old agent types.

    These provide convenient starting points but agents can have any
    custom personality configuration.
    """

    @staticmethod
    def explorer() -> Personality:
        """High exploration drive, low combat preference"""
        return Personality(
            exploration=9.0,
            combat=2.0,
            money=4.0,
            social=6.0,
            fishing=3.0,
            farming=2.0,
            foraging=7.0,
            cooking=3.0,
            building=4.0,
            risk_tolerance=7.0,
            patience=8.0,
            cooperativeness=7.0,
        )

    @staticmethod
    def warrior() -> Personality:
        """High combat drive, moderate exploration"""
        return Personality(
            exploration=3.0,
            combat=9.0,
            money=5.0,
            social=4.0,
            fishing=1.0,
            farming=1.0,
            foraging=2.0,
            cooking=2.0,
            building=4.0,
            risk_tolerance=8.0,
            patience=6.0,
            cooperativeness=5.0,
        )

    @staticmethod
    def fisher() -> Personality:
        """High fishing preference with moderate exploration"""
        return Personality(
            exploration=5.0,
            combat=2.0,
            money=6.0,
            social=7.0,
            fishing=9.0,
            farming=4.0,
            foraging=6.0,
            cooking=8.0,
            building=5.0,
            risk_tolerance=4.0,
            patience=9.0,
            cooperativeness=8.0,
        )

    @staticmethod
    def merchant() -> Personality:
        """Money-focused with high social interaction"""
        return Personality(
            exploration=4.0,
            combat=3.0,
            money=9.0,
            social=8.0,
            fishing=2.0,
            farming=5.0,
            foraging=4.0,
            cooking=3.0,
            building=6.0,
            risk_tolerance=6.0,
            patience=7.0,
            cooperativeness=9.0,
        )

    @staticmethod
    def farmer() -> Personality:
        """Agriculture-focused with building tendencies"""
        return Personality(
            exploration=2.0,
            combat=1.0,
            money=7.0,
            social=6.0,
            fishing=3.0,
            farming=9.0,
            foraging=5.0,
            cooking=7.0,
            building=8.0,
            risk_tolerance=3.0,
            patience=10.0,
            cooperativeness=8.0,
        )

    @staticmethod
    def guardian() -> Personality:
        """Balanced combat and social, protective nature"""
        return Personality(
            exploration=4.0,
            combat=7.0,
            money=3.0,
            social=8.0,
            fishing=2.0,
            farming=3.0,
            foraging=3.0,
            cooking=4.0,
            building=6.0,
            risk_tolerance=5.0,
            patience=8.0,
            cooperativeness=9.0,
        )

    @staticmethod
    def hunter() -> Personality:
        """Balanced combat and exploration with foraging"""
        return Personality(
            exploration=7.0,
            combat=6.0,
            money=4.0,
            social=3.0,
            fishing=4.0,
            farming=1.0,
            foraging=8.0,
            cooking=5.0,
            building=3.0,
            risk_tolerance=7.0,
            patience=6.0,
            cooperativeness=4.0,
        )

    @staticmethod
    def scholar() -> Personality:
        """Low physical activity, high exploration and cooking/building"""
        return Personality(
            exploration=8.0,
            combat=1.0,
            money=3.0,
            social=5.0,
            fishing=3.0,
            farming=4.0,
            foraging=6.0,
            cooking=7.0,
            building=8.0,
            risk_tolerance=3.0,
            patience=10.0,
            cooperativeness=6.0,
        )

    @staticmethod
    def random_personality(seed: Optional[int] = None) -> Personality:
        """Generate a random personality"""
        if seed is not None:
            random.seed(seed)

        return Personality(
            exploration=random.uniform(0, 10),
            combat=random.uniform(0, 10),
            money=random.uniform(0, 10),
            social=random.uniform(0, 10),
            fishing=random.uniform(0, 10),
            farming=random.uniform(0, 10),
            foraging=random.uniform(0, 10),
            cooking=random.uniform(0, 10),
            building=random.uniform(0, 10),
            risk_tolerance=random.uniform(0, 10),
            patience=random.uniform(0, 10),
            cooperativeness=random.uniform(0, 10),
        )

    @classmethod
    def get_all_archetypes(cls) -> Dict[str, Personality]:
        """Get all predefined archetypes as a dictionary"""
        return {
            "explorer": cls.explorer(),
            "warrior": cls.warrior(),
            "fisher": cls.fisher(),
            "merchant": cls.merchant(),
            "farmer": cls.farmer(),
            "guardian": cls.guardian(),
            "hunter": cls.hunter(),
            "scholar": cls.scholar(),
        }

    @classmethod
    def get_archetype(cls, name: str) -> Optional[Personality]:
        """Get a specific archetype by name"""
        archetypes = cls.get_all_archetypes()
        return archetypes.get(name.lower())


def create_personality_variant(
    base_personality: Personality, mutations: Dict[str, float]
) -> Personality:
    """
    Create a personality variant by modifying specific desires.

    Args:
        base_personality: The base personality to modify
        mutations: Dict of {desire_name: new_value} to apply

    Returns:
        New personality with modifications applied
    """
    # Convert to dict and apply mutations
    personality_dict = base_personality.to_dict()
    personality_dict.update(mutations)

    return Personality.from_dict(personality_dict)


def blend_personalities(
    personality_a: Personality, personality_b: Personality, weight_a: float = 0.5
) -> Personality:
    """
    Blend two personalities together.

    Args:
        personality_a: First personality
        personality_b: Second personality
        weight_a: Weight for personality_a (0.0 = all B, 1.0 = all A)

    Returns:
        New blended personality
    """
    weight_b = 1.0 - weight_a

    blended_dict = {}
    for field_name in personality_a.__dataclass_fields__:
        value_a = getattr(personality_a, field_name)
        value_b = getattr(personality_b, field_name)
        blended_dict[field_name] = value_a * weight_a + value_b * weight_b

    return Personality.from_dict(blended_dict)
