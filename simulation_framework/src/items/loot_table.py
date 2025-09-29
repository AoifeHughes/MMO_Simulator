from __future__ import annotations
from typing import List, Tuple, Optional, Dict, TYPE_CHECKING
import random

if TYPE_CHECKING:
    from .item import Item


class LootEntry:
    def __init__(
        self,
        item: Item,
        probability: float,
        min_quantity: int = 1,
        max_quantity: int = 1
    ):
        self.item = item
        self.probability = probability
        self.min_quantity = min_quantity
        self.max_quantity = max_quantity

    def roll_quantity(self) -> int:
        return random.randint(self.min_quantity, self.max_quantity)

    def __repr__(self) -> str:
        return f"LootEntry({self.item.name}, {self.probability:.2f}, {self.min_quantity}-{self.max_quantity})"


class LootTable:
    def __init__(self, entries: Optional[List[LootEntry]] = None):
        self.entries = entries or []

    def add_entry(
        self,
        item: Item,
        probability: float,
        min_quantity: int = 1,
        max_quantity: int = 1
    ) -> None:
        entry = LootEntry(item, probability, min_quantity, max_quantity)
        self.entries.append(entry)

    def generate_loot(self, luck_modifier: float = 0.0) -> List[Tuple[Item, int]]:
        loot = []

        for entry in self.entries:
            adjusted_probability = min(1.0, entry.probability + luck_modifier)

            if random.random() < adjusted_probability:
                quantity = entry.roll_quantity()
                loot.append((entry.item, quantity))

        return loot

    def get_guaranteed_loot(self) -> List[Tuple[Item, int]]:
        guaranteed = []
        for entry in self.entries:
            if entry.probability >= 1.0:
                quantity = entry.roll_quantity()
                guaranteed.append((entry.item, quantity))
        return guaranteed

    def get_possible_loot(self) -> List[Item]:
        return [entry.item for entry in self.entries]

    def get_total_probability(self) -> float:
        return sum(entry.probability for entry in self.entries)

    def is_empty(self) -> bool:
        return len(self.entries) == 0

    def merge(self, other: LootTable) -> LootTable:
        new_table = LootTable()
        new_table.entries = self.entries.copy() + other.entries.copy()
        return new_table

    @classmethod
    def create_basic_monster_loot(cls) -> LootTable:
        from ..items.item import Item
        from ..items.consumable import Consumable

        table = cls()

        coins = Item(
            id=500,
            name="Gold Coins",
            item_type="currency",
            properties={},
            description="Basic currency",
            value=1,
            weight=0.1,
            max_stack_size=999
        )

        health_potion = Consumable.create_health_potion()
        bread = Consumable.create_food("Bread")

        table.add_entry(coins, 0.8, 1, 10)
        table.add_entry(health_potion, 0.3, 1, 2)
        table.add_entry(bread, 0.5, 1, 3)

        return table

    @classmethod
    def create_rare_monster_loot(cls) -> LootTable:
        from ..items.weapon import Weapon
        from ..items.tool import Tool
        from ..items.consumable import Consumable

        table = cls()

        rare_sword = Weapon(
            id=1001,
            name="Enchanted Sword",
            item_type="weapon",
            properties={
                "damage": 25,
                "attack_type": "melee",
                "damage_type": "magical",
                "critical_chance": 0.2,
                "stamina_cost": 6
            },
            description="A magically enhanced sword",
            value=200,
            weight=4.0,
            max_stack_size=1
        )

        magic_potion = Consumable.create_magic_potion()
        strength_elixir = Consumable.create_strength_elixir()

        table.add_entry(rare_sword, 0.1)
        table.add_entry(magic_potion, 0.6, 1, 2)
        table.add_entry(strength_elixir, 0.4)

        basic_loot = cls.create_basic_monster_loot()
        return table.merge(basic_loot)

    @classmethod
    def create_resource_node_loot(cls, resource_type: str) -> LootTable:
        from ..items.item import Item

        table = cls()

        if resource_type == "tree":
            wood = Item(
                id=100,
                name="Wood",
                item_type="material",
                properties={"resource_type": "wood"},
                value=2,
                description="Raw wood material",
                max_stack_size=99
            )
            table.add_entry(wood, 1.0, 2, 5)

            bark = Item(
                id=107,
                name="Tree Bark",
                item_type="material",
                properties={"resource_type": "bark"},
                value=1,
                description="Tree bark for crafting",
                max_stack_size=50
            )
            table.add_entry(bark, 0.3, 1, 2)

        elif resource_type == "ore_vein":
            iron_ore = Item(
                id=102,
                name="Iron Ore",
                item_type="material",
                properties={"resource_type": "iron_ore"},
                value=5,
                description="Iron ore for smelting",
                max_stack_size=99
            )
            table.add_entry(iron_ore, 1.0, 1, 3)

            gems = Item(
                id=108,
                name="Raw Gems",
                item_type="material",
                properties={"resource_type": "gems"},
                value=15,
                description="Uncut gems",
                max_stack_size=20
            )
            table.add_entry(gems, 0.2)

        return table

    def __repr__(self) -> str:
        return f"LootTable({len(self.entries)} entries, total_prob={self.get_total_probability():.2f})"