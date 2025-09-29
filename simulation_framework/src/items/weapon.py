from __future__ import annotations
from typing import Dict, Any
from .item import Item


class Weapon(Item):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.item_type != "weapon":
            self.item_type = "weapon"

    def get_damage(self) -> int:
        return self.get_property("damage", 10)

    def get_attack_type(self) -> str:
        return self.get_property("attack_type", "melee")

    def get_range(self) -> int:
        attack_type = self.get_attack_type()
        if attack_type == "melee":
            return 1
        elif attack_type == "ranged":
            return self.get_property("range", 10)
        elif attack_type == "magic":
            return self.get_property("range", 15)
        return 1

    def get_attack_speed(self) -> float:
        return self.get_property("attack_speed", 1.0)

    def get_damage_type(self) -> str:
        return self.get_property("damage_type", "physical")

    def get_magic_cost(self) -> int:
        if self.get_attack_type() == "magic":
            return self.get_property("magic_cost", 10)
        return 0

    def get_stamina_cost(self) -> int:
        return self.get_property("stamina_cost", 5)

    def get_critical_chance(self) -> float:
        return self.get_property("critical_chance", 0.1)

    def get_critical_multiplier(self) -> float:
        return self.get_property("critical_multiplier", 2.0)

    @classmethod
    def create_sword(cls) -> Weapon:
        return cls(
            id=1,
            name="Iron Sword",
            item_type="weapon",
            properties={
                "damage": 15,
                "attack_type": "melee",
                "damage_type": "slashing",
                "stamina_cost": 5,
                "critical_chance": 0.15,
                "attack_speed": 1.2
            },
            description="A basic iron sword",
            value=50,
            weight=3.0,
            max_stack_size=1
        )

    @classmethod
    def create_bow(cls) -> Weapon:
        return cls(
            id=2,
            name="Wooden Bow",
            item_type="weapon",
            properties={
                "damage": 12,
                "attack_type": "ranged",
                "range": 15,
                "damage_type": "piercing",
                "stamina_cost": 4,
                "critical_chance": 0.2,
                "attack_speed": 0.8
            },
            description="A simple wooden bow",
            value=40,
            weight=2.0,
            max_stack_size=1
        )

    @classmethod
    def create_staff(cls) -> Weapon:
        return cls(
            id=3,
            name="Apprentice Staff",
            item_type="weapon",
            properties={
                "damage": 20,
                "attack_type": "magic",
                "range": 20,
                "damage_type": "magical",
                "magic_cost": 10,
                "critical_chance": 0.25,
                "attack_speed": 0.6
            },
            description="A staff imbued with basic magical power",
            value=100,
            weight=2.5,
            max_stack_size=1
        )