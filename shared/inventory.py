"""
Inventory system for managing agent items and equipment.

This module provides server-authoritative inventory management with a 64-slot
limit and weight-based restrictions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .items import Item, Equipment, Weapon, Gold, EquipmentSlot


@dataclass
class InventorySlot:
    """Represents a single inventory slot"""

    item: Optional[Item] = None
    quantity: int = 0

    def is_empty(self) -> bool:
        """Check if the slot is empty"""
        return self.item is None or self.quantity <= 0

    def can_add(self, item: Item, quantity: int = 1) -> bool:
        """Check if item can be added to this slot"""
        if self.is_empty():
            return True

        if not self.item.stackable or not item.stackable:
            return False

        if self.item.name != item.name or self.item.__class__ != item.__class__:
            return False

        return self.quantity + quantity <= self.item.max_stack_size

    def add_item(self, item: Item, quantity: int = 1) -> int:
        """Add item to slot, returns quantity actually added"""
        if not self.can_add(item, quantity):
            return 0

        if self.is_empty():
            self.item = item
            self.quantity = quantity
            return quantity

        # Adding to existing stack
        max_add = self.item.max_stack_size - self.quantity
        actual_add = min(quantity, max_add)
        self.quantity += actual_add
        return actual_add

    def remove_item(self, quantity: int = 1) -> Tuple[Optional[Item], int]:
        """Remove item from slot, returns (item, actual_quantity_removed)"""
        if self.is_empty():
            return None, 0

        actual_remove = min(quantity, self.quantity)
        self.quantity -= actual_remove

        item_copy = self.item
        if self.quantity <= 0:
            self.item = None
            self.quantity = 0

        return item_copy, actual_remove

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        if self.is_empty():
            return {"item": None, "quantity": 0}

        return {
            "item": self.item.to_dict(),
            "quantity": self.quantity
        }


class Inventory:
    """Main inventory class with 64-slot limit"""

    MAX_SLOTS = 64

    def __init__(self, max_weight: float = 1000.0):
        self.slots: List[InventorySlot] = [InventorySlot() for _ in range(self.MAX_SLOTS)]
        self.max_weight = max_weight
        self.equipped_items: Dict[EquipmentSlot, Optional[Item]] = {
            slot: None for slot in EquipmentSlot
        }

    def get_current_weight(self) -> float:
        """Calculate current total weight"""
        total_weight = 0.0

        # Weight from inventory slots
        for slot in self.slots:
            if not slot.is_empty():
                total_weight += slot.item.weight * slot.quantity

        # Weight from equipped items
        for equipped_item in self.equipped_items.values():
            if equipped_item:
                total_weight += equipped_item.weight

        return total_weight

    def has_space_for_item(self, item: Item, quantity: int = 1) -> bool:
        """Check if inventory has space for the item"""
        # Check weight
        total_new_weight = item.weight * quantity
        if self.get_current_weight() + total_new_weight > self.max_weight:
            return False

        # Check if we can fit the items
        remaining_quantity = quantity

        # First try to stack with existing items
        if item.stackable:
            for slot in self.slots:
                if slot.can_add(item, remaining_quantity):
                    can_add = min(remaining_quantity, item.max_stack_size - slot.quantity)
                    remaining_quantity -= can_add
                    if remaining_quantity <= 0:
                        return True

        # Then check for empty slots
        empty_slots = sum(1 for slot in self.slots if slot.is_empty())
        slots_needed = (remaining_quantity + (item.max_stack_size - 1)) // item.max_stack_size if item.stackable else remaining_quantity

        return empty_slots >= slots_needed

    def add_item(self, item: Item, quantity: int = 1) -> int:
        """Add item to inventory, returns quantity actually added"""
        if not self.has_space_for_item(item, quantity):
            return 0

        remaining_quantity = quantity

        # First try to stack with existing items
        if item.stackable:
            for slot in self.slots:
                if slot.can_add(item, remaining_quantity):
                    added = slot.add_item(item, remaining_quantity)
                    remaining_quantity -= added
                    if remaining_quantity <= 0:
                        return quantity

        # Then use empty slots
        for slot in self.slots:
            if slot.is_empty() and remaining_quantity > 0:
                add_amount = min(remaining_quantity, item.max_stack_size if item.stackable else 1)
                added = slot.add_item(item, add_amount)
                remaining_quantity -= added
                if remaining_quantity <= 0:
                    break

        return quantity - remaining_quantity

    def remove_item(self, item_name: str, quantity: int = 1) -> int:
        """Remove item by name, returns quantity actually removed"""
        removed_quantity = 0

        for slot in self.slots:
            if not slot.is_empty() and slot.item.name == item_name:
                _, removed = slot.remove_item(min(quantity - removed_quantity, slot.quantity))
                removed_quantity += removed
                if removed_quantity >= quantity:
                    break

        return removed_quantity

    def remove_item_by_id(self, item_id: str) -> Optional[Item]:
        """Remove specific item by ID, returns the item if found"""
        for slot in self.slots:
            if not slot.is_empty() and slot.item.item_id == item_id:
                item, _ = slot.remove_item(1)
                return item
        return None

    def get_item_by_id(self, item_id: str) -> Optional[Item]:
        """Get item by ID without removing it"""
        for slot in self.slots:
            if not slot.is_empty() and slot.item.item_id == item_id:
                return slot.item
        return None

    def get_items_by_type(self, item_type: str) -> List[Item]:
        """Get all items of a specific type"""
        items = []
        for slot in self.slots:
            if not slot.is_empty() and slot.item.item_type.value == item_type:
                items.append(slot.item)
        return items

    def get_item_quantity(self, item_name: str) -> int:
        """
        Get total quantity of an item by name across all inventory slots.

        Args:
            item_name: Name of the item to count (e.g., "fish", "sword", etc.)

        Returns:
            Total quantity of the specified item in inventory
        """
        total_quantity = 0
        found_items = []

        for slot in self.slots:
            if not slot.is_empty():
                found_items.append(f"'{slot.item.name}' ({slot.quantity})")
                if slot.item.name == item_name:
                    total_quantity += slot.quantity

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Searching for '{item_name}' in inventory. Found items: {found_items}. Total '{item_name}': {total_quantity}")

        return total_quantity

    def get_weapons(self) -> List[Weapon]:
        """Get all weapons in inventory"""
        weapons = []
        for slot in self.slots:
            if not slot.is_empty() and isinstance(slot.item, Weapon):
                weapons.append(slot.item)
        return weapons

    def get_equipped_weapon(self, slot: EquipmentSlot = EquipmentSlot.MAIN_HAND) -> Optional[Weapon]:
        """Get equipped weapon from specific slot"""
        equipped = self.equipped_items.get(slot)
        return equipped if isinstance(equipped, Weapon) else None

    def equip_item(self, item_id: str) -> bool:
        """Equip an item from inventory"""
        item = self.get_item_by_id(item_id)
        if not item or not isinstance(item, Equipment):
            return False

        # Unequip current item in that slot if any
        current_equipped = self.equipped_items.get(item.slot)
        if current_equipped:
            self.unequip_item(item.slot)

        # Remove from inventory and equip
        removed_item = self.remove_item_by_id(item_id)
        if removed_item:
            self.equipped_items[item.slot] = removed_item
            return True

        return False

    def unequip_item(self, slot: EquipmentSlot) -> bool:
        """Unequip item from slot back to inventory"""
        equipped_item = self.equipped_items.get(slot)
        if not equipped_item:
            return False

        # Try to add back to inventory
        if self.has_space_for_item(equipped_item, 1):
            self.add_item(equipped_item, 1)
            self.equipped_items[slot] = None
            return True

        return False  # Inventory full

    def get_total_gold(self) -> int:
        """Get total gold amount across all slots"""
        total = 0
        for slot in self.slots:
            if not slot.is_empty() and isinstance(slot.item, Gold):
                total += slot.item.amount * slot.quantity
        return total

    def add_gold(self, amount: int) -> bool:
        """Add gold to inventory (combines with existing gold)"""
        if amount <= 0:
            return False

        # Try to find existing gold stacks to combine with
        for slot in self.slots:
            if not slot.is_empty() and isinstance(slot.item, Gold):
                space_in_stack = slot.item.max_stack_size - slot.quantity
                if space_in_stack > 0:
                    add_to_this_stack = min(amount, space_in_stack * slot.item.amount)
                    # Create new gold item with combined amount
                    new_gold_amount = slot.item.amount + add_to_this_stack
                    if new_gold_amount <= slot.item.amount * slot.item.max_stack_size:
                        # Update existing gold item
                        slot.item.amount = new_gold_amount
                        slot.item.name = f"Gold ({new_gold_amount})"
                        slot.item.weight = 0.01 * new_gold_amount
                        amount -= add_to_this_stack
                        if amount <= 0:
                            return True

        # Create new gold stack if needed
        if amount > 0:
            gold = Gold(amount)
            added = self.add_item(gold, 1)
            return added > 0

        return True

    def remove_gold(self, amount: int) -> bool:
        """Remove gold from inventory"""
        if amount <= 0 or self.get_total_gold() < amount:
            return False

        remaining = amount
        for slot in self.slots:
            if not slot.is_empty() and isinstance(slot.item, Gold) and remaining > 0:
                gold_in_slot = slot.item.amount * slot.quantity
                if gold_in_slot <= remaining:
                    # Remove entire slot
                    remaining -= gold_in_slot
                    slot.item = None
                    slot.quantity = 0
                else:
                    # Partial removal
                    slot.item.amount -= remaining
                    slot.item.name = f"Gold ({slot.item.amount})"
                    slot.item.weight = 0.01 * slot.item.amount
                    remaining = 0

                if remaining <= 0:
                    break

        return remaining == 0

    def get_empty_slot_count(self) -> int:
        """Get number of empty slots"""
        return sum(1 for slot in self.slots if slot.is_empty())

    def get_used_slot_count(self) -> int:
        """Get number of used slots"""
        return self.MAX_SLOTS - self.get_empty_slot_count()

    def to_dict(self) -> Dict[str, Any]:
        """Convert inventory to dictionary for serialization"""
        return {
            "max_slots": self.MAX_SLOTS,
            "max_weight": self.max_weight,
            "current_weight": self.get_current_weight(),
            "used_slots": self.get_used_slot_count(),
            "slots": [slot.to_dict() for slot in self.slots],
            "equipped_items": {
                slot.value: item.to_dict() if item else None
                for slot, item in self.equipped_items.items()
            }
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get inventory summary for client display"""
        return {
            "used_slots": self.get_used_slot_count(),
            "max_slots": self.MAX_SLOTS,
            "current_weight": round(self.get_current_weight(), 2),
            "max_weight": self.max_weight,
            "total_gold": self.get_total_gold(),
            "weapon_count": len(self.get_weapons()),
            "equipped_weapon": self.get_equipped_weapon().name if self.get_equipped_weapon() else None
        }