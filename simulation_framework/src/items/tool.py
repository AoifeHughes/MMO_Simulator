from __future__ import annotations
from typing import Dict, Any
from .item import Item


class Tool(Item):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.item_type != "tool":
            self.item_type = "tool"
        if "durability" not in self.properties:
            self.properties["durability"] = 100
        if "max_durability" not in self.properties:
            self.properties["max_durability"] = 100

    def get_tool_type(self) -> str:
        return self.get_property("tool_type", "generic")

    def get_durability(self) -> int:
        return self.get_property("durability", 100)

    def get_max_durability(self) -> int:
        return self.get_property("max_durability", 100)

    def get_efficiency(self) -> float:
        return self.get_property("efficiency", 1.0)

    def use(self, wear_amount: int = 1) -> bool:
        current_durability = self.get_durability()
        if current_durability <= 0:
            return False

        new_durability = max(0, current_durability - wear_amount)
        self.set_property("durability", new_durability)
        return True

    def repair(self, amount: int) -> int:
        current = self.get_durability()
        max_dur = self.get_max_durability()
        repaired = min(amount, max_dur - current)
        self.set_property("durability", current + repaired)
        return repaired

    def is_broken(self) -> bool:
        return self.get_durability() <= 0

    def get_durability_percentage(self) -> float:
        max_dur = self.get_max_durability()
        if max_dur == 0:
            return 0.0
        return self.get_durability() / max_dur

    @classmethod
    def create_pickaxe(cls) -> Tool:
        return cls(
            id=10,
            name="Iron Pickaxe",
            item_type="tool",
            properties={
                "tool_type": "pickaxe",
                "durability": 100,
                "max_durability": 100,
                "efficiency": 1.5,
                "mining_level": 2
            },
            description="A sturdy iron pickaxe for mining",
            value=30,
            weight=4.0,
            max_stack_size=1
        )

    @classmethod
    def create_axe(cls) -> Tool:
        return cls(
            id=11,
            name="Iron Axe",
            item_type="tool",
            properties={
                "tool_type": "axe",
                "durability": 100,
                "max_durability": 100,
                "efficiency": 1.5,
                "woodcutting_level": 2
            },
            description="A sharp iron axe for woodcutting",
            value=25,
            weight=3.5,
            max_stack_size=1
        )

    @classmethod
    def create_fishing_rod(cls) -> Tool:
        return cls(
            id=12,
            name="Fishing Rod",
            item_type="tool",
            properties={
                "tool_type": "fishing_rod",
                "durability": 50,
                "max_durability": 50,
                "efficiency": 1.0,
                "fishing_level": 1
            },
            description="A simple fishing rod",
            value=15,
            weight=1.5,
            max_stack_size=1
        )

    @classmethod
    def create_hoe(cls) -> Tool:
        return cls(
            id=13,
            name="Iron Hoe",
            item_type="tool",
            properties={
                "tool_type": "hoe",
                "durability": 80,
                "max_durability": 80,
                "efficiency": 1.2,
                "farming_level": 1
            },
            description="A hoe for tilling soil",
            value=20,
            weight=2.5,
            max_stack_size=1
        )