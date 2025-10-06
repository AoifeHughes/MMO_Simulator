from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict


@dataclass
class Personality:
    curiosity: float = 0.5  # Drives exploration behavior
    bravery: float = 0.5  # Willingness to engage in combat/take risks
    sociability: float = 0.5  # Preference for trading/cooperation
    greed: float = 0.5  # Focus on accumulating resources/wealth
    patience: float = 0.5  # Willingness to wait for better opportunities
    aggression: float = 0.3  # Tendency to initiate combat
    industriousness: float = 0.5  # Focus on gathering/crafting activities
    caution: float = 0.5  # Risk aversion in dangerous situations

    def __post_init__(self):
        # Ensure all traits are between 0 and 1
        self.curiosity = max(0.0, min(1.0, self.curiosity))
        self.bravery = max(0.0, min(1.0, self.bravery))
        self.sociability = max(0.0, min(1.0, self.sociability))
        self.greed = max(0.0, min(1.0, self.greed))
        self.patience = max(0.0, min(1.0, self.patience))
        self.aggression = max(0.0, min(1.0, self.aggression))
        self.industriousness = max(0.0, min(1.0, self.industriousness))
        self.caution = max(0.0, min(1.0, self.caution))

    @classmethod
    def randomize(cls, seed: int = None) -> Personality:
        if seed is not None:
            random.seed(seed)

        return cls(
            curiosity=random.uniform(0.1, 0.9),
            bravery=random.uniform(0.1, 0.9),
            sociability=random.uniform(0.1, 0.9),
            greed=random.uniform(0.1, 0.9),
            patience=random.uniform(0.1, 0.9),
            aggression=random.uniform(0.0, 0.7),
            industriousness=random.uniform(0.2, 0.9),
            caution=random.uniform(0.1, 0.8),
        )

    @classmethod
    def create_archetype(cls, archetype: str) -> Personality:
        """Create personality based on common archetypes"""
        archetypes = {
            "explorer": cls(
                curiosity=0.9,
                bravery=0.7,
                sociability=0.4,
                greed=0.3,
                patience=0.6,
                aggression=0.2,
                industriousness=0.5,
                caution=0.3,
            ),
            "warrior": cls(
                curiosity=0.4,
                bravery=0.9,
                sociability=0.3,
                greed=0.4,
                patience=0.3,
                aggression=0.8,
                industriousness=0.4,
                caution=0.2,
            ),
            "trader": cls(
                curiosity=0.5,
                bravery=0.4,
                sociability=0.9,
                greed=0.8,
                patience=0.7,
                aggression=0.1,
                industriousness=0.6,
                caution=0.6,
            ),
            "crafter": cls(
                curiosity=0.3,
                bravery=0.3,
                sociability=0.5,
                greed=0.5,
                patience=0.9,
                aggression=0.1,
                industriousness=0.9,
                caution=0.7,
            ),
            "hermit": cls(
                curiosity=0.6,
                bravery=0.3,
                sociability=0.1,
                greed=0.2,
                patience=0.8,
                aggression=0.1,
                industriousness=0.7,
                caution=0.9,
            ),
            "bandit": cls(
                curiosity=0.3,
                bravery=0.7,
                sociability=0.2,
                greed=0.9,
                patience=0.2,
                aggression=0.9,
                industriousness=0.2,
                caution=0.1,
            ),
        }

        if archetype in archetypes:
            return archetypes[archetype]
        else:
            return cls.randomize()

    def get_dominant_traits(self, threshold: float = 0.6) -> list[str]:
        """Return traits that are above the threshold"""
        traits = []
        if self.curiosity >= threshold:
            traits.append("curious")
        if self.bravery >= threshold:
            traits.append("brave")
        if self.sociability >= threshold:
            traits.append("sociable")
        if self.greed >= threshold:
            traits.append("greedy")
        if self.patience >= threshold:
            traits.append("patient")
        if self.aggression >= threshold:
            traits.append("aggressive")
        if self.industriousness >= threshold:
            traits.append("industrious")
        if self.caution >= threshold:
            traits.append("cautious")

        return traits

    def similarity_to(self, other: Personality) -> float:
        """Calculate similarity between two personalities (0-1, higher is more similar)"""
        differences = [
            abs(self.curiosity - other.curiosity),
            abs(self.bravery - other.bravery),
            abs(self.sociability - other.sociability),
            abs(self.greed - other.greed),
            abs(self.patience - other.patience),
            abs(self.aggression - other.aggression),
            abs(self.industriousness - other.industriousness),
            abs(self.caution - other.caution),
        ]

        avg_difference = sum(differences) / len(differences)
        return 1.0 - avg_difference

    def get_action_modifier(self, action_type: str) -> float:
        """Get personality modifier for different action types"""
        modifiers = {
            "explore": self.curiosity,
            "combat": self.bravery + self.aggression * 0.5,
            "trade": self.sociability,
            "gather": self.industriousness,
            "craft": self.industriousness + self.patience * 0.3,
            "flee": self.caution,
            "wait": self.patience,
            "hoard": self.greed,
            "help_others": self.sociability - self.greed * 0.3,
        }

        return modifiers.get(action_type, 0.5)

    def get_risk_tolerance(self) -> float:
        """Calculate overall risk tolerance (0-1)"""
        return (self.bravery + (1.0 - self.caution)) / 2.0

    def get_social_preference(self) -> float:
        """Calculate preference for social interactions"""
        return self.sociability

    def should_initiate_trade(
        self, potential_profit: float, relationship: float = 0.5
    ) -> bool:
        """Determine if agent should initiate a trade"""
        trade_desire = self.sociability * 0.4 + self.greed * 0.4 + self.patience * 0.2

        # Adjust for potential profit
        profit_factor = min(1.0, potential_profit / 10.0)  # Normalize profit
        trade_desire += profit_factor * 0.3

        # Adjust for relationship
        trade_desire += (relationship - 0.5) * 0.2

        return random.random() < trade_desire

    def should_engage_in_combat(
        self,
        enemy_strength: float,
        own_strength: float,
        potential_loot_value: float = 0.0,
    ) -> bool:
        """Determine if agent should engage in combat"""
        strength_ratio = own_strength / max(enemy_strength, 1)

        combat_desire = (
            self.bravery * 0.4 + self.aggression * 0.4 + (1.0 - self.caution) * 0.2
        )

        # Adjust for strength difference
        if strength_ratio > 1.5:  # Much stronger
            combat_desire += 0.3
        elif strength_ratio < 0.7:  # Much weaker
            combat_desire -= 0.4

        # Adjust for potential loot
        loot_factor = min(0.3, potential_loot_value * self.greed / 100.0)
        combat_desire += loot_factor

        return random.random() < combat_desire

    def get_exploration_desire(self, known_area_percentage: float) -> float:
        """Calculate desire to explore based on how much is known"""
        base_desire = self.curiosity

        # More desire to explore if less is known
        unknown_bonus = (1.0 - known_area_percentage) * 0.5

        # Brave agents explore more dangerous areas
        danger_tolerance = self.bravery * 0.3

        return min(1.0, base_desire + unknown_bonus + danger_tolerance)

    def to_dict(self) -> Dict[str, float]:
        return {
            "curiosity": self.curiosity,
            "bravery": self.bravery,
            "sociability": self.sociability,
            "greed": self.greed,
            "patience": self.patience,
            "aggression": self.aggression,
            "industriousness": self.industriousness,
            "caution": self.caution,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> Personality:
        return cls(**data)

    def __str__(self) -> str:
        dominant = self.get_dominant_traits()
        if dominant:
            return f"Personality({', '.join(dominant)})"
        else:
            return "Personality(balanced)"

    def __repr__(self) -> str:
        return (
            f"Personality(curiosity={self.curiosity:.2f}, bravery={self.bravery:.2f}, "
            f"sociability={self.sociability:.2f}, greed={self.greed:.2f}, "
            f"patience={self.patience:.2f}, aggression={self.aggression:.2f}, "
            f"industriousness={self.industriousness:.2f}, caution={self.caution:.2f})"
        )
