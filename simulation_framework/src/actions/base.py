from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..core.world import World
    from ..entities.base import Entity


@dataclass
class Event:
    event_type: str
    actor_id: int
    target_id: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: int = 0


@dataclass
class ResourceCost:
    stamina: int = 0
    magic: int = 0
    health: int = 0
    items: Dict[str, int] = field(default_factory=dict)

    def can_afford(self, entity: Entity) -> bool:
        if self.stamina > entity.stats.stamina:
            return False
        if self.magic > entity.stats.magic:
            return False
        if self.health > entity.stats.health:
            return False

        for item_name, quantity in self.items.items():
            if not entity.inventory.has_item(item_name, quantity):
                return False

        return True

    def consume(self, entity: Entity) -> bool:
        if not self.can_afford(entity):
            return False

        entity.stats.use_stamina(self.stamina)
        entity.stats.use_magic(self.magic)
        if self.health > 0:
            entity.stats.health = max(0, entity.stats.health - self.health)

        for item_name, quantity in self.items.items():
            entity.inventory.remove_item(item_name, quantity)

        return True


@dataclass
class ActionResult:
    success: bool
    message: str = ""
    events: List[Event] = field(default_factory=list)
    interrupted: bool = False

    @classmethod
    def success(
        cls, message: str = "Action completed successfully", events: List[Event] = None
    ) -> ActionResult:
        return cls(success=True, message=message, events=events or [])

    @classmethod
    def failure(
        cls, message: str = "Action failed", events: List[Event] = None
    ) -> ActionResult:
        return cls(success=False, message=message, events=events or [])

    @classmethod
    def create_interrupted(
        cls, message: str = "Action was interrupted"
    ) -> ActionResult:
        return cls(success=False, message=message, interrupted=True)


class Action(ABC):
    def __init__(self, actor_id: int):
        self.actor_id = actor_id
        self.start_tick = 0
        self.is_active = False

    @abstractmethod
    def can_execute(self, actor: Entity, world: World) -> bool:
        pass

    @abstractmethod
    def execute(self, actor: Entity, world: World) -> ActionResult:
        pass

    @abstractmethod
    def get_duration(self) -> int:
        pass

    @abstractmethod
    def get_cost(self) -> ResourceCost:
        pass

    def start(self, current_tick: int) -> None:
        self.start_tick = current_tick
        self.is_active = True

    def is_complete(self, current_tick: int) -> bool:
        if not self.is_active:
            return False
        return current_tick >= self.start_tick + self.get_duration()

    def get_progress(self, current_tick: int) -> float:
        if not self.is_active:
            return 0.0
        duration = self.get_duration()
        if duration == 0:
            return 1.0
        elapsed = current_tick - self.start_tick
        return min(1.0, elapsed / duration)

    def can_interrupt(self) -> bool:
        return True

    def interrupt(self) -> ActionResult:
        self.is_active = False
        return ActionResult.create_interrupted(
            f"{self.__class__.__name__} was interrupted"
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(actor_id={self.actor_id})"
