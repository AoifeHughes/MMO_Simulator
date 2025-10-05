from __future__ import annotations
from typing import Optional, Dict, List, TYPE_CHECKING
import random

from .base import Action, ActionResult, ResourceCost, Event
from ..items.item import Item

if TYPE_CHECKING:
    from ..entities.base import Entity
    from ..core.world import World


class GatherAction(Action):
    def __init__(
        self,
        actor_id: int,
        resource_type: str,
        required_tool: Optional[str] = None,
        required_terrain: Optional[str] = None,
        skill_name: str = "general"
    ):
        super().__init__(actor_id)
        self.resource_type = resource_type
        self.required_tool = required_tool
        self.required_terrain = required_terrain
        self.skill_name = skill_name

    def can_execute(self, actor: Entity, world: World) -> bool:
        tile = world.get_tile(*actor.position)
        if not tile:
            return False

        if self.required_terrain:
            if tile.terrain_type.value != self.required_terrain:
                return False

        if not tile.can_gather(self.resource_type):
            return False

        if self.required_tool:
            tool = actor.inventory.get_equipped_tool(self.required_tool)
            if not tool:
                return False
            if tool.is_broken():
                return False

        return self.get_cost().can_afford(actor)

    def execute(self, actor: Entity, world: World) -> ActionResult:
        if not self.can_execute(actor, world):
            return ActionResult.failure(f"Cannot gather {self.resource_type}")

        cost = self.get_cost()
        if not cost.consume(actor):
            return ActionResult.failure("Not enough resources to gather")

        tile = world.get_tile(*actor.position)
        resource_deposit = None
        for deposit in tile.resources:
            if deposit.resource_type == self.resource_type:
                resource_deposit = deposit
                break

        if not resource_deposit:
            return ActionResult.failure(f"No {self.resource_type} found")

        if not resource_deposit.can_harvest(world.current_tick):
            return ActionResult.failure(f"{self.resource_type} not ready for harvest")

        base_yield = self._calculate_yield(actor)
        tool = None
        if self.required_tool:
            tool = actor.inventory.get_equipped_tool(self.required_tool)

        if tool:
            base_yield = int(base_yield * tool.get_efficiency())
            tool.use(1)

        actual_yield = resource_deposit.harvest(base_yield, world.current_tick)

        if actual_yield > 0:
            item = self._create_resource_item(self.resource_type, actual_yield)
            remaining = actor.inventory.add_item(item, actual_yield)

            if remaining > 0:
                return ActionResult.failure(f"Inventory full, lost {remaining} {self.resource_type}")

            self._gain_experience(actor)

            event = Event(
                event_type="gather",
                actor_id=actor.id,
                data={
                    "resource_type": self.resource_type,
                    "yield": actual_yield,
                    "position": actor.position
                }
            )

            return ActionResult.success(
                f"Gathered {actual_yield} {self.resource_type}",
                [event]
            )
        else:
            return ActionResult.failure(f"Failed to gather {self.resource_type}")

    def _calculate_yield(self, actor: Entity) -> int:
        base_yield = 2
        skill_level = getattr(actor, 'skills', {}).get(self.skill_name, 1)
        skill_bonus = skill_level * 0.1

        random_factor = random.uniform(0.8, 1.2)
        total_yield = base_yield * (1 + skill_bonus) * random_factor

        rare_chance = 0.1 + (skill_level * 0.01)
        if random.random() < rare_chance:
            total_yield *= 2

        return max(1, int(total_yield))

    def _create_resource_item(self, resource_type: str, quantity: int) -> Item:
        item_data = {
            "wood": {"id": 100, "name": "Wood", "value": 2, "description": "Raw wood material"},
            "stone": {"id": 101, "name": "Stone", "value": 1, "description": "Common stone"},
            "iron_ore": {"id": 102, "name": "Iron Ore", "value": 5, "description": "Iron ore for smelting"},
            "gold_ore": {"id": 103, "name": "Gold Ore", "value": 20, "description": "Precious gold ore"},
            "fish": {"id": 104, "name": "Fish", "value": 3, "description": "Fresh fish"},
            "berries": {"id": 105, "name": "Berries", "value": 2, "description": "Wild berries"},
            "herbs": {"id": 106, "name": "Herbs", "value": 4, "description": "Medicinal herbs"}
        }

        data = item_data.get(resource_type, {
            "id": 999, "name": resource_type.title(), "value": 1,
            "description": f"Raw {resource_type}"
        })

        return Item(
            id=data["id"],
            name=data["name"],
            item_type="material",
            properties={"resource_type": resource_type},
            value=data["value"],
            description=data["description"],
            weight=1.0,
            max_stack_size=99
        )

    def _gain_experience(self, actor: Entity) -> None:
        if hasattr(actor, 'skills'):
            current_xp = actor.skills.get(self.skill_name, 0)
            actor.skills[self.skill_name] = current_xp + 1

    def get_duration(self) -> int:
        return 3

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=5)

    def __repr__(self) -> str:
        return f"GatherAction({self.resource_type})"


class FishAction(GatherAction):
    def __init__(self, actor_id: int):
        super().__init__(
            actor_id=actor_id,
            resource_type="fish",
            required_tool="fishing_rod",
            skill_name="fishing"
        )

    def can_execute(self, actor: Entity, world: World) -> bool:
        x, y = actor.position
        water_adjacent = False

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor = world.get_tile(x + dx, y + dy)
            if neighbor and neighbor.terrain_type.value == "water":
                water_adjacent = True
                break

        if not water_adjacent:
            return False

        return super().can_execute(actor, world)


class MineAction(GatherAction):
    def __init__(self, actor_id: int, resource_type: str = "stone"):
        super().__init__(
            actor_id=actor_id,
            resource_type=resource_type,
            required_tool="pickaxe",  # Restored tool requirement
            required_terrain="mountain",
            skill_name="mining"
        )


class ForageAction(GatherAction):
    def __init__(self, actor_id: int, resource_type: str = "berries"):
        super().__init__(
            actor_id=actor_id,
            resource_type=resource_type,
            skill_name="foraging"
        )

    def can_execute(self, actor: Entity, world: World) -> bool:
        tile = world.get_tile(*actor.position)
        if not tile:
            return False

        valid_terrain = tile.terrain_type.value in ["forest", "grass"]
        if not valid_terrain:
            return False

        return tile.can_gather(self.resource_type) and self.get_cost().can_afford(actor)


class WoodcutAction(GatherAction):
    def __init__(self, actor_id: int):
        super().__init__(
            actor_id=actor_id,
            resource_type="wood",
            required_tool="axe",  # Restored tool requirement
            required_terrain="forest",
            skill_name="woodcutting"
        )