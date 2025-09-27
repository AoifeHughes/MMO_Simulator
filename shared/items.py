"""
Item system with OOP hierarchy for the MMO Simulator.

This module defines the base item classes and specific item types including
weapons, consumables, tools, and currency (gold).
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ItemType(Enum):
    """Types of items in the game"""

    WEAPON = "weapon"
    EQUIPMENT = "equipment"
    CONSUMABLE = "consumable"
    TOOL = "tool"
    CURRENCY = "currency"
    MISC = "misc"


class WeaponType(Enum):
    """Types of weapons"""

    MELEE = "melee"
    RANGED = "ranged"


class EquipmentSlot(Enum):
    """Equipment slots for wearable items"""

    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    HEAD = "head"
    CHEST = "chest"
    LEGS = "legs"
    FEET = "feet"


@dataclass
class Item(ABC):
    """Base class for all items"""

    item_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Unknown Item"
    description: str = "A mysterious item"
    value: int = 0  # Gold value
    weight: float = 1.0  # Weight for inventory management
    stackable: bool = False  # Whether multiple can occupy one slot
    max_stack_size: int = 1  # Maximum stack size if stackable
    item_type: ItemType = ItemType.MISC

    def to_dict(self) -> Dict[str, Any]:
        """Convert item to dictionary for serialization"""
        return {
            "item_id": self.item_id,
            "name": self.name,
            "description": self.description,
            "value": self.value,
            "weight": self.weight,
            "stackable": self.stackable,
            "max_stack_size": self.max_stack_size,
            "item_type": self.item_type.value,
        }

    @abstractmethod
    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Use the item - returns result dictionary"""
        pass


@dataclass
class Gold(Item):
    """Currency item - always stackable"""

    def __init__(self, amount: int = 1):
        super().__init__(
            name=f"Gold ({amount})",
            description="Standard currency",
            value=amount,
            weight=0.01 * amount,  # Gold is light
            stackable=True,
            max_stack_size=9999,
            item_type=ItemType.CURRENCY,
        )
        self.amount = amount

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["amount"] = self.amount
        return result

    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Gold can't be used directly"""
        return {"success": False, "message": "Gold cannot be used directly"}


@dataclass
class Tool(Item):
    """Base class for tools"""

    def __init__(self, **kwargs):
        super().__init__(item_type=ItemType.TOOL, **kwargs)


@dataclass
class FishingRod(Tool):
    """Fishing rod tool for catching fish"""

    def __init__(self):
        super().__init__(
            name="Fishing Rod",
            description="A simple fishing rod for catching fish",
            value=50,
            weight=2.0,
            stackable=False,
        )

    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Use the fishing rod to catch fish"""
        return {"success": True, "action": "fish", "message": "Casting fishing line..."}


@dataclass
class Equipment(Item):
    """Base class for wearable equipment"""

    slot: EquipmentSlot = EquipmentSlot.MAIN_HAND
    durability: float = 100.0
    max_durability: float = 100.0

    def __init__(self, slot: EquipmentSlot = EquipmentSlot.MAIN_HAND, **kwargs):
        # Extract non-Item kwargs
        equipment_kwargs = {}
        item_kwargs = {}

        item_fields = {
            "item_id",
            "name",
            "description",
            "value",
            "weight",
            "stackable",
            "max_stack_size",
            "item_type",
        }

        for key, value in kwargs.items():
            if key in item_fields:
                item_kwargs[key] = value
            else:
                equipment_kwargs[key] = value

        super().__init__(item_type=ItemType.EQUIPMENT, **item_kwargs)
        self.slot = slot

        # Set equipment-specific attributes
        for key, value in equipment_kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "slot": self.slot.value,
                "durability": self.durability,
                "max_durability": self.max_durability,
            }
        )
        return result

    def repair(self, amount: float = None):
        """Repair the equipment"""
        if amount is None:
            amount = self.max_durability
        self.durability = min(self.max_durability, self.durability + amount)

    def damage(self, amount: float):
        """Damage the equipment"""
        self.durability = max(0.0, self.durability - amount)
        return self.durability <= 0  # Return True if broken

    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Equipment is equipped, not used directly"""
        return {
            "success": True,
            "message": f"Equipped {self.name}",
            "action": "equip",
            "slot": self.slot.value,
        }


@dataclass
class Weapon(Equipment):
    """Weapon class for combat items"""

    weapon_type: WeaponType = WeaponType.MELEE
    damage: float = 10.0
    min_range: float = 0.0
    max_range: float = 2.0
    attack_speed: float = 1.0  # Attacks per second
    critical_chance: float = 0.05  # 5% crit chance

    def __init__(self, weapon_type: WeaponType = WeaponType.MELEE, **kwargs):
        # Extract weapon-specific attributes
        weapon_attrs = [
            "damage",
            "min_range",
            "max_range",
            "attack_speed",
            "critical_chance",
        ]
        weapon_kwargs = {}

        for attr in weapon_attrs:
            if attr in kwargs:
                weapon_kwargs[attr] = kwargs.pop(attr)

        super().__init__(slot=EquipmentSlot.MAIN_HAND, **kwargs)
        self.item_type = ItemType.WEAPON
        self.weapon_type = weapon_type

        # Set weapon-specific attributes
        for key, value in weapon_kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "weapon_type": self.weapon_type.value,
                "damage": self.damage,
                "min_range": self.min_range,
                "max_range": self.max_range,
                "attack_speed": self.attack_speed,
                "critical_chance": self.critical_chance,
            }
        )
        return result

    def get_attack_name(self) -> str:
        """Get the attack name for this weapon"""
        if self.weapon_type == WeaponType.MELEE:
            if "sword" in self.name.lower():
                return "sword_slash"
            elif "claw" in self.name.lower():
                return "claw"
            else:
                return "punch"
        else:  # RANGED
            if "bow" in self.name.lower():
                return "bow_shot"
            elif "magic" in self.name.lower():
                return "magic_bolt"
            else:
                return "throwing_knife"

    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Using a weapon equips it"""
        return super().use(agent_id, world_context)


@dataclass
class Consumable(Item):
    """Consumable items that are destroyed when used"""

    effect_type: str = "heal"  # heal, mana, buff, etc.
    effect_value: float = 20.0  # Amount of effect
    effect_duration: float = 0.0  # Duration in seconds (0 = instant)

    def __init__(self, **kwargs):
        # Extract consumable-specific attributes
        consumable_attrs = ["effect_type", "effect_value", "effect_duration"]
        consumable_kwargs = {}

        for attr in consumable_attrs:
            if attr in kwargs:
                consumable_kwargs[attr] = kwargs.pop(attr)

        super().__init__(stackable=True, max_stack_size=10, **kwargs)
        self.item_type = ItemType.CONSUMABLE

        # Set consumable-specific attributes
        for key, value in consumable_kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "effect_type": self.effect_type,
                "effect_value": self.effect_value,
                "effect_duration": self.effect_duration,
            }
        )
        return result

    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Use the consumable item"""
        return {
            "success": True,
            "message": f"Used {self.name}",
            "action": "consume",
            "effect_type": self.effect_type,
            "effect_value": self.effect_value,
            "effect_duration": self.effect_duration,
        }


@dataclass
class Resource(Item):
    """Resource items for crafting materials"""

    resource_type: str = "generic"  # wood, stone, ore, etc.

    def __init__(self, **kwargs):
        # Extract resource-specific attributes
        resource_attrs = ["resource_type"]
        resource_kwargs = {}

        for attr in resource_attrs:
            if attr in kwargs:
                resource_kwargs[attr] = kwargs.pop(attr)

        super().__init__(stackable=True, max_stack_size=50, **kwargs)
        self.item_type = ItemType.MISC

        # Set resource-specific attributes
        for key, value in resource_kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "resource_type": self.resource_type,
            }
        )
        return result

    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Resources are used in crafting, not directly"""
        return {
            "success": False,
            "message": f"{self.name} is a crafting material and cannot be used directly",
            "action": "none",
        }


@dataclass
class Tool(Item):
    """Tool items for various activities"""

    tool_type: str = "generic"  # fishing, mining, crafting, etc.
    uses: int = -1  # -1 = infinite uses
    max_uses: int = -1

    def __init__(self, **kwargs):
        # Extract tool-specific attributes
        tool_attrs = ["tool_type", "uses", "max_uses"]
        tool_kwargs = {}

        for attr in tool_attrs:
            if attr in kwargs:
                tool_kwargs[attr] = kwargs.pop(attr)

        super().__init__(**kwargs)
        self.item_type = ItemType.TOOL

        # Set tool-specific attributes
        for key, value in tool_kwargs.items():
            setattr(self, key, value)

    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "tool_type": self.tool_type,
                "uses": self.uses,
                "max_uses": self.max_uses,
            }
        )
        return result

    def use_tool(self) -> bool:
        """Use the tool once, returns True if tool is still usable"""
        if self.uses <= 0:
            return True  # Infinite uses

        self.uses -= 1
        return self.uses > 0

    def use(self, agent_id: str, world_context: Optional[Any] = None) -> Dict[str, Any]:
        """Use the tool"""
        if not self.use_tool():
            return {
                "success": False,
                "message": f"{self.name} is broken and cannot be used",
            }

        return {
            "success": True,
            "message": f"Used {self.name}",
            "action": "use_tool",
            "tool_type": self.tool_type,
            "remaining_uses": self.uses,
        }


# Predefined Items


def create_sword() -> Weapon:
    """Create a basic sword weapon"""
    return Weapon(
        name="Iron Sword",
        description="A sturdy iron sword for close combat",
        value=100,  # Iron Sword base value
        weight=3.0,
        weapon_type=WeaponType.MELEE,
        damage=15.0,
        min_range=0.5,
        max_range=2.5,
        attack_speed=0.67,  # 1.5 second cooldown
        durability=80.0,
        max_durability=80.0,
    )


def create_bow() -> Weapon:
    """Create a basic bow weapon"""
    return Weapon(
        name="Hunter's Bow",
        description="A reliable bow for ranged combat",
        value=80,  # Hunter's Bow base value
        weight=2.0,
        weapon_type=WeaponType.RANGED,
        damage=20.0,
        min_range=3.0,
        max_range=15.0,
        attack_speed=0.5,  # 2 second cooldown
        durability=60.0,
        max_durability=60.0,
    )


def create_fishing_rod() -> Tool:
    """Create a fishing rod tool"""
    return Tool(
        name="Fishing Rod",
        description="A tool for catching fish at water sources",
        value=30,  # Fishing Rod base value
        weight=1.5,
        tool_type="fishing",
        uses=-1,  # Infinite uses
    )


def create_hatchet() -> Tool:
    """Create a hatchet tool for wood harvesting"""
    return Tool(
        name="Hatchet",
        description="A tool for harvesting wood from trees",
        value=40,  # Hatchet base value
        weight=2.0,
        tool_type="woodcutting",
        uses=-1,  # Infinite uses
    )


def create_fish() -> Consumable:
    """Create a fish consumable"""
    return Consumable(
        name="Fresh Fish",
        description="A nutritious fish that restores health",
        value=5,  # Fresh Fish base value
        weight=0.5,
        effect_type="heal",
        effect_value=25.0,
        effect_duration=0.0,
    )


def create_wood() -> Resource:
    """Create a wood resource item"""
    return Resource(
        name="wood",
        description="Harvested wood from forest trees, useful for crafting",
        value=2,  # Wood base value
        weight=0.8,
        resource_type="wood",
    )


def create_gold_stack(amount: int = 10) -> Gold:
    """Create a gold stack"""
    return Gold(amount)


# Item Factory for creating items by name

ITEM_REGISTRY = {
    "iron_sword": create_sword,
    "hunters_bow": create_bow,
    "fishing_rod": create_fishing_rod,
    "hatchet": create_hatchet,
    "fish": create_fish,
    "wood": create_wood,
    "gold": lambda: create_gold_stack(10),
}


def create_item(item_name: str, **kwargs) -> Optional[Item]:
    """Create an item by name from the registry"""
    if item_name in ITEM_REGISTRY:
        item = ITEM_REGISTRY[item_name]()
        # Apply any overrides from kwargs
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        return item
    return None


def get_available_items() -> Dict[str, str]:
    """Get all available item names and descriptions"""
    items = {}
    for name, creator in ITEM_REGISTRY.items():
        item = creator()
        items[name] = item.description
    return items
