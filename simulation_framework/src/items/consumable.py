from __future__ import annotations
from typing import Dict, Any, TYPE_CHECKING
from .item import Item

if TYPE_CHECKING:
    from ..entities.base import Entity, StatusEffect


class Consumable(Item):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.item_type != "consumable":
            self.item_type = "consumable"

    def get_effect(self) -> Dict[str, Any]:
        return self.get_property("effect", {})

    def consume(self, entity: Entity) -> bool:
        effect = self.get_effect()

        if "heal" in effect:
            entity.stats.heal(effect["heal"])

        if "restore_stamina" in effect:
            entity.stats.restore_stamina(effect["restore_stamina"])

        if "restore_magic" in effect:
            entity.stats.restore_magic(effect["restore_magic"])

        if "damage" in effect:
            entity.stats.take_damage(effect["damage"])

        if "status_effect" in effect:
            status = effect["status_effect"]
            from ..entities.base import StatusEffect
            entity.apply_status_effect(
                StatusEffect(
                    name=status.get("name", "effect"),
                    duration=status.get("duration", 10),
                    effect_type=status.get("type", "neutral"),
                    power=status.get("power", 0)
                )
            )

        if "buff" in effect:
            buff = effect["buff"]
            if "attack" in buff:
                entity.stats.attack_power += buff["attack"]
            if "defense" in buff:
                entity.stats.defense += buff["defense"]
            if "speed" in buff:
                entity.stats.speed += buff["speed"]

        return entity.inventory.remove_item(self.name, 1)

    def get_cooldown(self) -> int:
        return self.get_property("cooldown", 0)

    @classmethod
    def create_health_potion(cls) -> Consumable:
        return cls(
            id=20,
            name="Health Potion",
            item_type="consumable",
            properties={
                "effect": {
                    "heal": 50
                },
                "cooldown": 5
            },
            description="Restores 50 health points",
            value=25,
            weight=0.5,
            max_stack_size=20
        )

    @classmethod
    def create_stamina_potion(cls) -> Consumable:
        return cls(
            id=21,
            name="Stamina Potion",
            item_type="consumable",
            properties={
                "effect": {
                    "restore_stamina": 50
                },
                "cooldown": 3
            },
            description="Restores 50 stamina points",
            value=20,
            weight=0.5,
            max_stack_size=20
        )

    @classmethod
    def create_magic_potion(cls) -> Consumable:
        return cls(
            id=22,
            name="Magic Potion",
            item_type="consumable",
            properties={
                "effect": {
                    "restore_magic": 30
                },
                "cooldown": 3
            },
            description="Restores 30 magic points",
            value=30,
            weight=0.5,
            max_stack_size=20
        )

    @classmethod
    def create_poison(cls) -> Consumable:
        return cls(
            id=23,
            name="Poison",
            item_type="consumable",
            properties={
                "effect": {
                    "status_effect": {
                        "name": "poisoned",
                        "type": "poison",
                        "duration": 10,
                        "power": 5
                    }
                },
                "cooldown": 0
            },
            description="Inflicts poison damage over time",
            value=15,
            weight=0.3,
            max_stack_size=10
        )

    @classmethod
    def create_strength_elixir(cls) -> Consumable:
        return cls(
            id=24,
            name="Strength Elixir",
            item_type="consumable",
            properties={
                "effect": {
                    "buff": {
                        "attack": 10
                    },
                    "status_effect": {
                        "name": "strengthened",
                        "type": "buff",
                        "duration": 50,
                        "power": 0
                    }
                },
                "cooldown": 10
            },
            description="Increases attack power temporarily",
            value=50,
            weight=0.5,
            max_stack_size=10
        )

    @classmethod
    def create_food(cls, name: str = "Bread") -> Consumable:
        return cls(
            id=30,
            name=name,
            item_type="consumable",
            properties={
                "effect": {
                    "heal": 10,
                    "restore_stamina": 20
                },
                "cooldown": 0
            },
            description="Basic food that restores health and stamina",
            value=5,
            weight=0.2,
            max_stack_size=50
        )