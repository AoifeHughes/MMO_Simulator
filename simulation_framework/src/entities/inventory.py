from __future__ import annotations
from typing import Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from ..items.item import Item


@dataclass
class InventorySlot:
    item: Item
    quantity: int

    def add(self, amount: int) -> int:
        if not self.item.can_stack():
            return amount

        max_stack = self.item.max_stack_size
        space_available = max_stack - self.quantity
        to_add = min(amount, space_available)
        self.quantity += to_add
        return amount - to_add


class Inventory:
    def __init__(self, capacity: int = 50):
        self.capacity = capacity
        self.items: Dict[str, InventorySlot] = {}
        self.equipped_weapon: Optional[Item] = None
        self.equipped_tools: Dict[str, Item] = {}

    def add_item(self, item: Item, quantity: int = 1) -> int:
        if not item.can_stack() and quantity > 1:
            added = 0
            for _ in range(quantity):
                if self.get_total_items() >= self.capacity:
                    break
                unique_key = f"{item.name}_{id(item)}"
                self.items[unique_key] = InventorySlot(item, 1)
                added += 1
            return quantity - added

        if item.name in self.items:
            slot = self.items[item.name]
            remaining = slot.add(quantity)

            return remaining
        else:
            if self.get_total_items() >= self.capacity:
                return quantity

            self.items[item.name] = InventorySlot(item, min(quantity, item.max_stack_size))
            return max(0, quantity - item.max_stack_size)

    def remove_item(self, item_name: str, quantity: int = 1) -> bool:
        total_available = self.get_item_count(item_name)
        if total_available < quantity:
            return False

        remaining = quantity
        slots_to_remove = []

        for key, slot in self.items.items():
            if slot.item.name == item_name:
                if slot.quantity <= remaining:
                    remaining -= slot.quantity
                    slots_to_remove.append(key)
                else:
                    slot.quantity -= remaining
                    remaining = 0
                    break

        for key in slots_to_remove:
            del self.items[key]

        return True

    def has_item(self, item_name: str, quantity: int = 1) -> bool:
        return self.get_item_count(item_name) >= quantity

    def get_item_count(self, item_name: str) -> int:
        total = 0
        for slot in self.items.values():
            if slot.item.name == item_name:
                total += slot.quantity
        return total

    def get_total_items(self) -> int:
        unique_items = len(self.items)
        return unique_items

    def get_all_items(self) -> List[InventorySlot]:
        return list(self.items.values())

    def equip_weapon(self, weapon: Item) -> Optional[Item]:
        if weapon.item_type != "weapon":
            return None

        old_weapon = self.equipped_weapon
        self.equipped_weapon = weapon

        if weapon.name in self.items:
            self.remove_item(weapon.name, 1)

        if old_weapon:
            self.add_item(old_weapon, 1)

        return old_weapon

    def get_equipped_weapon(self) -> Optional[Item]:
        return self.equipped_weapon

    def equip_tool(self, tool: Item, tool_type: str) -> Optional[Item]:
        if tool.item_type != "tool":
            return None

        old_tool = self.equipped_tools.get(tool_type)
        self.equipped_tools[tool_type] = tool

        if tool.name in self.items:
            self.remove_item(tool.name, 1)

        if old_tool:
            self.add_item(old_tool, 1)

        return old_tool

    def get_equipped_tool(self, tool_type: str) -> Optional[Item]:
        return self.equipped_tools.get(tool_type)

    def to_dict(self) -> Dict:
        return {
            "capacity": self.capacity,
            "items": {
                key: {"item_name": slot.item.name, "quantity": slot.quantity}
                for key, slot in self.items.items()
            },
            "equipped_weapon": self.equipped_weapon.name if self.equipped_weapon else None,
            "equipped_tools": {
                tool_type: tool.name
                for tool_type, tool in self.equipped_tools.items()
            }
        }

    @classmethod
    def from_dict(cls, data: Dict, item_loader) -> Inventory:
        inventory = cls(capacity=data["capacity"])

        for key, item_data in data["items"].items():
            item = item_loader.get_item_by_name(item_data["item_name"])
            if item:
                inventory.items[key] = InventorySlot(item, item_data["quantity"])

        if data["equipped_weapon"]:
            weapon = item_loader.get_item_by_name(data["equipped_weapon"])
            if weapon:
                inventory.equipped_weapon = weapon

        for tool_type, tool_name in data["equipped_tools"].items():
            tool = item_loader.get_item_by_name(tool_name)
            if tool:
                inventory.equipped_tools[tool_type] = tool

        return inventory

    def clear(self) -> None:
        self.items.clear()
        self.equipped_weapon = None
        self.equipped_tools.clear()