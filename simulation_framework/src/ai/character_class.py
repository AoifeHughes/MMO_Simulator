from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

from ..items.weapon import Weapon
from ..items.tool import Tool
from ..items.consumable import Consumable


class SkillType(Enum):
    COMBAT = "combat"
    ARCHERY = "archery"
    MAGIC = "magic"
    MINING = "mining"
    WOODCUTTING = "woodcutting"
    FISHING = "fishing"
    FORAGING = "foraging"
    CRAFTING = "crafting"
    TRADING = "trading"
    EXPLORATION = "exploration"


@dataclass
class CharacterClass:
    name: str
    description: str
    skill_affinities: Dict[str, float] = field(default_factory=dict)
    preferred_actions: List[str] = field(default_factory=list)
    starting_stats_bonus: Dict[str, int] = field(default_factory=dict)
    equipment_preferences: List[str] = field(default_factory=list)

    def get_skill_modifier(self, skill_name: str) -> float:
        """Get multiplier for skill experience gain"""
        return self.skill_affinities.get(skill_name, 1.0)

    def get_action_preference(self, action_type: str) -> float:
        """Get preference modifier for action types (0.5-1.5)"""
        if action_type in self.preferred_actions:
            return 1.3
        elif any(preferred in action_type.lower() for preferred in self.preferred_actions):
            return 1.1
        else:
            return 0.8

    def get_starting_equipment(self) -> List:
        """Get list of starting items for this class"""
        equipment = []

        if "sword" in self.equipment_preferences:
            equipment.append(Weapon.create_sword())
        elif "bow" in self.equipment_preferences:
            equipment.append(Weapon.create_bow())
        elif "staff" in self.equipment_preferences:
            equipment.append(Weapon.create_staff())

        if "pickaxe" in self.equipment_preferences:
            equipment.append(Tool.create_pickaxe())
        elif "axe" in self.equipment_preferences:
            equipment.append(Tool.create_axe())
        elif "fishing_rod" in self.equipment_preferences:
            equipment.append(Tool.create_fishing_rod())

        # Add some basic consumables
        equipment.append(Consumable.create_food("Bread"))
        equipment.append(Consumable.create_health_potion())

        return equipment

    @classmethod
    def create_warrior(cls) -> CharacterClass:
        return cls(
            name="Warrior",
            description="Masters of melee combat and physical prowess",
            skill_affinities={
                "combat": 1.5,
                "defense": 1.3,
                "athletics": 1.2,
                "smithing": 1.1
            },
            preferred_actions=["combat", "melee", "defend", "patrol"],
            starting_stats_bonus={
                "max_health": 20,
                "attack_power": 5,
                "defense": 3
            },
            equipment_preferences=["sword", "shield", "heavy_armor"]
        )

    @classmethod
    def create_mage(cls) -> CharacterClass:
        return cls(
            name="Mage",
            description="Wielders of arcane magic and mystical knowledge",
            skill_affinities={
                "magic": 1.6,
                "alchemy": 1.4,
                "research": 1.3,
                "crafting": 1.1
            },
            preferred_actions=["magic", "craft", "research", "study"],
            starting_stats_bonus={
                "max_magic": 30,
                "magic": 30,
                "attack_power": -2,
                "defense": -1
            },
            equipment_preferences=["staff", "robes", "spell_components"]
        )

    @classmethod
    def create_hunter(cls) -> CharacterClass:
        return cls(
            name="Hunter",
            description="Expert trackers and ranged combat specialists",
            skill_affinities={
                "archery": 1.5,
                "tracking": 1.4,
                "foraging": 1.3,
                "stealth": 1.2,
                "woodcutting": 1.1
            },
            preferred_actions=["hunt", "forage", "explore", "track"],
            starting_stats_bonus={
                "speed": 3,
                "stamina": 10,
                "max_stamina": 10
            },
            equipment_preferences=["bow", "leather_armor", "hunting_knife"]
        )

    @classmethod
    def create_alchemist(cls) -> CharacterClass:
        return cls(
            name="Alchemist",
            description="Masters of potion brewing and transmutation",
            skill_affinities={
                "alchemy": 1.6,
                "herbalism": 1.4,
                "foraging": 1.3,
                "crafting": 1.3,
                "magic": 1.1
            },
            preferred_actions=["craft", "forage", "experiment", "trade"],
            starting_stats_bonus={
                "max_magic": 15,
                "magic": 15
            },
            equipment_preferences=["staff", "alchemy_kit", "gathering_tools"]
        )

    @classmethod
    def create_blacksmith(cls) -> CharacterClass:
        return cls(
            name="Blacksmith",
            description="Skilled crafters of weapons and armor",
            skill_affinities={
                "smithing": 1.6,
                "mining": 1.4,
                "crafting": 1.4,
                "trading": 1.2
            },
            preferred_actions=["craft", "mine", "trade", "repair"],
            starting_stats_bonus={
                "max_health": 10,
                "attack_power": 2,
                "max_stamina": 15,
                "stamina": 15
            },
            equipment_preferences=["hammer", "anvil", "pickaxe", "apron"]
        )

    @classmethod
    def create_trader(cls) -> CharacterClass:
        return cls(
            name="Trader",
            description="Merchants focused on commerce and negotiation",
            skill_affinities={
                "trading": 1.6,
                "negotiation": 1.5,
                "appraisal": 1.4,
                "exploration": 1.2
            },
            preferred_actions=["trade", "negotiate", "travel", "network"],
            starting_stats_bonus={
                "speed": 2
            },
            equipment_preferences=["coin_purse", "ledger", "traveling_gear"]
        )

    @classmethod
    def create_explorer(cls) -> CharacterClass:
        return cls(
            name="Explorer",
            description="Adventurous souls who seek new territories",
            skill_affinities={
                "exploration": 1.6,
                "survival": 1.4,
                "foraging": 1.2,
                "climbing": 1.3,
                "swimming": 1.2
            },
            preferred_actions=["explore", "map", "forage", "discover"],
            starting_stats_bonus={
                "speed": 4,
                "max_stamina": 20,
                "stamina": 20
            },
            equipment_preferences=["compass", "rope", "rations", "map"]
        )

    @classmethod
    def create_farmer(cls) -> CharacterClass:
        return cls(
            name="Farmer",
            description="Providers of food and agricultural products",
            skill_affinities={
                "farming": 1.6,
                "animal_handling": 1.4,
                "herbalism": 1.2,
                "trading": 1.1
            },
            preferred_actions=["farm", "tend", "harvest", "trade"],
            starting_stats_bonus={
                "max_stamina": 15,
                "stamina": 15
            },
            equipment_preferences=["hoe", "seeds", "watering_can", "sickle"]
        )

    def get_stat_bonus(self, stat_name: str) -> int:
        """Get starting stat bonus for this class"""
        return self.starting_stats_bonus.get(stat_name, 0)

    def is_preferred_skill(self, skill_name: str) -> bool:
        """Check if this skill is preferred by this class"""
        return skill_name in self.skill_affinities and self.skill_affinities[skill_name] > 1.0

    def get_class_specialization(self) -> str:
        """Get the primary specialization of this class"""
        if not self.skill_affinities:
            return "generalist"

        max_skill = max(self.skill_affinities.items(), key=lambda x: x[1])
        return max_skill[0]

    def get_preferred_biome(self) -> Optional[str]:
        """Get the preferred biome for this class"""
        preferences = {
            "Warrior": None,  # No specific preference
            "Mage": "mountain",  # For magical components
            "Hunter": "forest",  # For hunting
            "Alchemist": "forest",  # For herbs
            "Blacksmith": "mountain",  # For mining
            "Trader": None,  # Travels everywhere
            "Explorer": None,  # Explores everywhere
            "Farmer": "grass"  # For farming
        }
        return preferences.get(self.name)

    def calculate_effectiveness(self, activity_type: str, skill_levels: Dict[str, int]) -> float:
        """Calculate how effective this class is at a given activity"""
        base_effectiveness = self.get_action_preference(activity_type)

        # Factor in relevant skills
        relevant_skills = []
        if activity_type == "combat":
            relevant_skills = ["combat", "defense"]
        elif activity_type == "magic":
            relevant_skills = ["magic", "alchemy"]
        elif activity_type == "crafting":
            relevant_skills = ["crafting", "smithing"]
        elif activity_type == "gathering":
            relevant_skills = ["mining", "woodcutting", "foraging", "fishing"]
        elif activity_type == "trading":
            relevant_skills = ["trading", "negotiation"]

        skill_bonus = 0.0
        for skill in relevant_skills:
            skill_level = skill_levels.get(skill, 1)
            skill_modifier = self.get_skill_modifier(skill)
            skill_bonus += (skill_level * skill_modifier - skill_level) * 0.1

        return min(2.0, base_effectiveness + skill_bonus)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "skill_affinities": self.skill_affinities,
            "preferred_actions": self.preferred_actions,
            "starting_stats_bonus": self.starting_stats_bonus,
            "equipment_preferences": self.equipment_preferences
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CharacterClass:
        return cls(
            name=data["name"],
            description=data["description"],
            skill_affinities=data.get("skill_affinities", {}),
            preferred_actions=data.get("preferred_actions", []),
            starting_stats_bonus=data.get("starting_stats_bonus", {}),
            equipment_preferences=data.get("equipment_preferences", [])
        )

    def __str__(self) -> str:
        specialization = self.get_class_specialization()
        return f"{self.name} ({specialization})"

    def __repr__(self) -> str:
        return f"CharacterClass(name='{self.name}', specialization='{self.get_class_specialization()}')"


# Predefined class registry for easy access
CHARACTER_CLASSES = {
    "warrior": CharacterClass.create_warrior,
    "mage": CharacterClass.create_mage,
    "hunter": CharacterClass.create_hunter,
    "alchemist": CharacterClass.create_alchemist,
    "blacksmith": CharacterClass.create_blacksmith,
    "trader": CharacterClass.create_trader,
    "explorer": CharacterClass.create_explorer,
    "farmer": CharacterClass.create_farmer
}


def get_random_character_class() -> CharacterClass:
    """Get a random character class"""
    import random
    class_name = random.choice(list(CHARACTER_CLASSES.keys()))
    return CHARACTER_CLASSES[class_name]()


def get_character_class(name: str) -> Optional[CharacterClass]:
    """Get a character class by name"""
    if name.lower() in CHARACTER_CLASSES:
        return CHARACTER_CLASSES[name.lower()]()
    return None