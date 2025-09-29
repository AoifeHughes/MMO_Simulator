from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Tuple, Optional, List, Dict, TYPE_CHECKING
import math

from .stats import Stats
from .inventory import Inventory

if TYPE_CHECKING:
    from ..core.world import World


class Entity(ABC):
    _next_id = 1

    def __init__(
        self,
        position: Tuple[int, int],
        name: str = "Entity",
        stats: Optional[Stats] = None,
        inventory_capacity: int = 50
    ):
        self.id = Entity._next_id
        Entity._next_id += 1
        self.name = name
        self.position = position
        self.stats = stats or Stats()
        self.inventory = Inventory(capacity=inventory_capacity)
        self.status_effects: List[StatusEffect] = []
        self.vision_range = 10

    def move_to(self, x: int, y: int, world: World) -> bool:
        return world.move_entity(self, x, y)

    def distance_to(self, other: Entity) -> float:
        x1, y1 = self.position
        x2, y2 = other.position
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    def distance_to_position(self, x: int, y: int) -> float:
        x1, y1 = self.position
        return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)

    def can_see(self, other: Entity, range_override: Optional[float] = None) -> bool:
        max_range = range_override if range_override is not None else self.vision_range
        return self.distance_to(other) <= max_range

    def can_see_position(self, x: int, y: int, range_override: Optional[float] = None) -> bool:
        max_range = range_override if range_override is not None else self.vision_range
        return self.distance_to_position(x, y) <= max_range

    def apply_status_effect(self, effect: StatusEffect) -> None:
        existing = next((e for e in self.status_effects if e.name == effect.name), None)
        if existing:
            existing.refresh(effect.duration)
        else:
            self.status_effects.append(effect)

    def update_status_effects(self) -> None:
        self.status_effects = [
            effect for effect in self.status_effects
            if effect.update(self)
        ]

    def has_status_effect(self, effect_name: str) -> bool:
        return any(effect.name == effect_name for effect in self.status_effects)

    def remove_status_effect(self, effect_name: str) -> None:
        self.status_effects = [
            effect for effect in self.status_effects
            if effect.name != effect_name
        ]

    @abstractmethod
    def update(self, world: World) -> None:
        pass

    @abstractmethod
    def on_death(self, killer: Optional[Entity] = None) -> None:
        pass

    def take_damage(self, amount: int, attacker: Optional[Entity] = None) -> int:
        actual_damage = self.stats.take_damage(amount)

        if not self.stats.is_alive():
            self.on_death(attacker)

        return actual_damage

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, name='{self.name}', pos={self.position})"


class StatusEffect:
    def __init__(
        self,
        name: str,
        duration: int,
        effect_type: str = "neutral",
        power: float = 0
    ):
        self.name = name
        self.duration = duration
        self.remaining_duration = duration
        self.effect_type = effect_type
        self.power = power

    def update(self, entity: Entity) -> bool:
        self.apply_effect(entity)
        self.remaining_duration -= 1
        return self.remaining_duration > 0

    def apply_effect(self, entity: Entity) -> None:
        if self.effect_type == "poison":
            entity.stats.health = max(0, entity.stats.health - int(self.power))
        elif self.effect_type == "regeneration":
            entity.stats.heal(int(self.power))
        elif self.effect_type == "slow":
            pass
        elif self.effect_type == "haste":
            pass

    def refresh(self, additional_duration: int) -> None:
        self.remaining_duration = max(self.remaining_duration, additional_duration)

    def __repr__(self) -> str:
        return f"StatusEffect({self.name}, {self.remaining_duration}/{self.duration})"