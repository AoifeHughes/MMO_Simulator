from __future__ import annotations
from typing import Dict, List, Optional, TYPE_CHECKING

from .base import Action, ActionResult, ResourceCost, Event
from ..items.item import Item

if TYPE_CHECKING:
    from ..entities.base import Entity
    from ..core.world import World


class CraftAction(Action):
    def __init__(self, actor_id: int, item_name: str, quantity: int = 1):
        super().__init__(actor_id)
        self.item_name = item_name
        self.quantity = quantity
        self.recipe = self._get_recipe(item_name)

    def _get_recipe(self, item_name: str) -> Dict:
        """Get crafting recipe for an item (simplified recipes)"""
        recipes = {
            "Wooden Sword": {
                "materials": {"Wood": 2},
                "tool_required": None,
                "skill_required": ("crafting", 1),
                "crafting_time": 3
            },
            "Stone Axe": {
                "materials": {"Wood": 1, "Stone": 2},
                "tool_required": None,
                "skill_required": ("crafting", 2),
                "crafting_time": 4
            },
            "Health Potion": {
                "materials": {"Herbs": 2, "Berries": 1},
                "tool_required": None,
                "skill_required": ("alchemy", 1),
                "crafting_time": 2
            },
            "Bread": {
                "materials": {"Berries": 3},
                "tool_required": None,
                "skill_required": ("cooking", 1),
                "crafting_time": 2
            },
            "Iron Sword": {
                "materials": {"Iron Ore": 3, "Wood": 1},
                "tool_required": "anvil",
                "skill_required": ("smithing", 3),
                "crafting_time": 5
            }
        }
        return recipes.get(item_name, {})

    def can_execute(self, actor: Entity, world: World) -> bool:
        if not self.recipe:
            return False

        # Check materials
        for material, needed in self.recipe.get("materials", {}).items():
            if not actor.inventory.has_item(material, needed * self.quantity):
                return False

        # Check tool requirement
        tool_required = self.recipe.get("tool_required")
        if tool_required and not actor.inventory.get_equipped_tool(tool_required):
            return False

        # Check skill requirement
        skill_req = self.recipe.get("skill_required")
        if skill_req:
            skill_name, min_level = skill_req
            if hasattr(actor, 'skills'):
                current_level = actor.skills.get(skill_name, 0)
                if current_level < min_level:
                    return False

        return self.get_cost().can_afford(actor)

    def execute(self, actor: Entity, world: World) -> ActionResult:
        if not self.can_execute(actor, world):
            return ActionResult.failure(f"Cannot craft {self.item_name}")

        # Consume resources
        cost = self.get_cost()
        if not cost.consume(actor):
            return ActionResult.failure("Insufficient resources")

        # Consume materials
        for material, needed in self.recipe.get("materials", {}).items():
            actor.inventory.remove_item(material, needed * self.quantity)

        # Create the crafted item
        crafted_item = self._create_item(self.item_name)
        if crafted_item:
            remaining = actor.inventory.add_item(crafted_item, self.quantity)
            if remaining > 0:
                return ActionResult.failure(f"Inventory full, lost {remaining} {self.item_name}")

            # Gain skill experience
            skill_req = self.recipe.get("skill_required")
            if skill_req and hasattr(actor, 'skills'):
                skill_name, _ = skill_req
                current_skill = actor.skills.get(skill_name, 0)
                actor.skills[skill_name] = current_skill + 2

            event = Event(
                event_type="craft",
                actor_id=actor.id,
                data={
                    "item": self.item_name,
                    "quantity": self.quantity,
                    "skill_gained": 2
                }
            )

            return ActionResult.success(
                f"Crafted {self.quantity}x {self.item_name}",
                [event]
            )

        return ActionResult.failure(f"Failed to create {self.item_name}")

    def _create_item(self, item_name: str) -> Optional[Item]:
        """Create the specified item"""
        item_data = {
            "Wooden Sword": {
                "id": 1001,
                "type": "weapon",
                "properties": {
                    "damage": 8,
                    "attack_type": "melee",
                    "durability": 30
                },
                "value": 15
            },
            "Stone Axe": {
                "id": 1002,
                "type": "tool",
                "properties": {
                    "tool_type": "axe",
                    "durability": 40,
                    "efficiency": 1.2
                },
                "value": 20
            },
            "Health Potion": {
                "id": 1003,
                "type": "consumable",
                "properties": {
                    "effect": {"heal": 30}
                },
                "value": 25,
                "max_stack": 10
            },
            "Bread": {
                "id": 1004,
                "type": "consumable",
                "properties": {
                    "effect": {"heal": 15, "restore_stamina": 10}
                },
                "value": 5,
                "max_stack": 20
            },
            "Iron Sword": {
                "id": 1005,
                "type": "weapon",
                "properties": {
                    "damage": 18,
                    "attack_type": "melee",
                    "durability": 80,
                    "critical_chance": 0.15
                },
                "value": 75
            }
        }

        data = item_data.get(item_name)
        if not data:
            return None

        return Item(
            id=data["id"],
            name=item_name,
            item_type=data["type"],
            properties=data["properties"],
            description=f"Crafted {item_name.lower()}",
            value=data["value"],
            max_stack_size=data.get("max_stack", 1)
        )

    def get_duration(self) -> int:
        return self.recipe.get("crafting_time", 1)

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=5)

    def __repr__(self) -> str:
        return f"CraftAction({self.item_name}x{self.quantity})"