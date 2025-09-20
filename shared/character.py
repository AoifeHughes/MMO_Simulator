"""
Character class system for MMO agents
"""

from dataclasses import dataclass
from typing import Dict, Any
from enum import Enum


class CharacterClass(Enum):
    """Available character classes"""
    WARRIOR = "warrior"
    MAGE = "mage"


@dataclass
class BaseStats:
    """Base character statistics"""
    health: int
    max_health: int
    mana: int
    max_mana: int
    attack_power: int
    defense: int
    speed: float
    level: int = 1
    experience: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'health': self.health,
            'max_health': self.max_health,
            'mana': self.mana,
            'max_mana': self.max_mana,
            'attack_power': self.attack_power,
            'defense': self.defense,
            'speed': self.speed,
            'level': self.level,
            'experience': self.experience
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseStats':
        return cls(**data)


@dataclass
class BehaviorWeights:
    """Behavior tendency weights for decision making"""
    exploration: float = 0.5  # 0.0 = never explore, 1.0 = always explore
    combat: float = 0.5       # 0.0 = avoid combat, 1.0 = seek combat
    social: float = 0.3       # 0.0 = antisocial, 1.0 = very social
    caution: float = 0.5      # 0.0 = reckless, 1.0 = very cautious

    def to_dict(self) -> Dict[str, float]:
        return {
            'exploration': self.exploration,
            'combat': self.combat,
            'social': self.social,
            'caution': self.caution
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'BehaviorWeights':
        return cls(**data)

    def update_on_activity(self, activity_type: str, success: bool):
        """Update behavior weights based on activity outcomes"""
        adjustment = 0.05 if success else -0.03

        if activity_type == "exploration":
            self.exploration = max(0.1, min(0.9, self.exploration + adjustment))
        elif activity_type == "combat":
            self.combat = max(0.1, min(0.9, self.combat + adjustment))
        elif activity_type == "social":
            self.social = max(0.1, min(0.9, self.social + adjustment))


class Character:
    """Base character class for all agents"""

    def __init__(self, name: str, character_class: CharacterClass):
        self.name = name
        self.character_class = character_class
        self.stats = self._get_base_stats()
        self.behaviors = self._get_base_behaviors()
        self.current_focus = None  # Current behavioral focus
        self.focus_duration = 0    # How long to maintain current focus

    def _get_base_stats(self) -> BaseStats:
        """Override in subclasses to provide class-specific stats"""
        return BaseStats(
            health=100,
            max_health=100,
            mana=50,
            max_mana=50,
            attack_power=10,
            defense=5,
            speed=50.0
        )

    def _get_base_behaviors(self) -> BehaviorWeights:
        """Override in subclasses to provide class-specific behaviors"""
        return BehaviorWeights()

    def get_spawn_region(self) -> str:
        """Get preferred spawn region for this character class"""
        return "center"  # Override in subclasses

    def decide_focus(self) -> str:
        """Decide current behavioral focus based on weights and randomness"""
        import random

        # Weight the decision based on behavior preferences
        choices = [
            ("exploration", self.behaviors.exploration),
            ("combat", self.behaviors.combat),
        ]

        # Add some randomness but favor higher weights
        total_weight = sum(weight for _, weight in choices)
        rand_val = random.random() * total_weight

        current = 0
        for choice, weight in choices:
            current += weight
            if rand_val <= current:
                self.current_focus = choice
                self.focus_duration = random.randint(30, 120)  # 30-120 seconds
                return choice

        # Fallback
        self.current_focus = "exploration"
        self.focus_duration = 60
        return "exploration"

    def update_focus_progress(self, activity_type: str, success: bool):
        """Update behavior weights and focus duration"""
        self.behaviors.update_on_activity(activity_type, success)
        self.focus_duration -= 1

        # If focus duration expired, choose new focus
        if self.focus_duration <= 0:
            self.decide_focus()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize character data"""
        return {
            'name': self.name,
            'character_class': self.character_class.value,
            'stats': self.stats.to_dict(),
            'behaviors': self.behaviors.to_dict(),
            'current_focus': self.current_focus,
            'focus_duration': self.focus_duration
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Character':
        """Deserialize character data"""
        char_class = CharacterClass(data['character_class'])

        # Create appropriate subclass
        if char_class == CharacterClass.WARRIOR:
            from .warrior import Warrior
            char = Warrior(data['name'])
        elif char_class == CharacterClass.MAGE:
            from .mage import Mage
            char = Mage(data['name'])
        else:
            char = cls(data['name'], char_class)

        # Restore state
        char.stats = BaseStats.from_dict(data['stats'])
        char.behaviors = BehaviorWeights.from_dict(data['behaviors'])
        char.current_focus = data.get('current_focus')
        char.focus_duration = data.get('focus_duration', 0)

        return char


class Warrior(Character):
    """Warrior character class - high health, prefers combat"""

    def __init__(self, name: str):
        super().__init__(name, CharacterClass.WARRIOR)

    def _get_base_stats(self) -> BaseStats:
        return BaseStats(
            health=150,      # High health
            max_health=150,
            mana=30,         # Low mana
            max_mana=30,
            attack_power=15, # High attack
            defense=10,      # High defense
            speed=45.0       # Slightly slower
        )

    def _get_base_behaviors(self) -> BehaviorWeights:
        return BehaviorWeights(
            exploration=0.3,  # Less interested in exploration
            combat=0.8,       # Loves combat
            social=0.4,       # Moderately social
            caution=0.2       # Not very cautious
        )

    def get_spawn_region(self) -> str:
        return "southwest"  # Bottom-left corner


class Mage(Character):
    """Mage character class - high mana, balanced approach"""

    def __init__(self, name: str):
        super().__init__(name, CharacterClass.MAGE)

    def _get_base_stats(self) -> BaseStats:
        return BaseStats(
            health=80,       # Lower health
            max_health=80,
            mana=100,        # High mana
            max_mana=100,
            attack_power=12, # Moderate attack
            defense=6,       # Lower defense
            speed=55.0       # Faster movement
        )

    def _get_base_behaviors(self) -> BehaviorWeights:
        return BehaviorWeights(
            exploration=0.7,  # Loves exploration
            combat=0.4,       # Moderate combat interest
            social=0.6,       # More social
            caution=0.7       # Very cautious
        )

    def get_spawn_region(self) -> str:
        return "northeast"  # Top-right corner