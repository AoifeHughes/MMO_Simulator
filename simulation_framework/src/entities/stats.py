from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class Stats:
    max_health: int = 100
    health: int = 100
    max_stamina: int = 100
    stamina: int = 100
    max_magic: int = 50
    magic: int = 50
    attack_power: int = 10
    defense: int = 5
    speed: int = 5

    def take_damage(self, amount: int) -> int:
        actual_damage = max(0, amount - self.defense)
        self.health = max(0, self.health - actual_damage)
        return actual_damage

    def heal(self, amount: int) -> int:
        actual_heal = min(amount, self.max_health - self.health)
        self.health += actual_heal
        return actual_heal

    def restore_stamina(self, amount: int) -> int:
        actual_restore = min(amount, self.max_stamina - self.stamina)
        self.stamina += actual_restore
        return actual_restore

    def restore_magic(self, amount: int) -> int:
        actual_restore = min(amount, self.max_magic - self.magic)
        self.magic += actual_restore
        return actual_restore

    def use_stamina(self, amount: int) -> bool:
        if self.stamina >= amount:
            self.stamina -= amount
            return True
        return False

    def use_magic(self, amount: int) -> bool:
        if self.magic >= amount:
            self.magic -= amount
            return True
        return False

    def is_alive(self) -> bool:
        return self.health > 0

    def get_health_percentage(self) -> float:
        if self.max_health == 0:
            return 0.0
        return self.health / self.max_health

    def get_stamina_percentage(self) -> float:
        if self.max_stamina == 0:
            return 0.0
        return self.stamina / self.max_stamina

    def get_magic_percentage(self) -> float:
        if self.max_magic == 0:
            return 0.0
        return self.magic / self.max_magic

    def reset(self) -> None:
        self.health = self.max_health
        self.stamina = self.max_stamina
        self.magic = self.max_magic

    def to_dict(self) -> Dict:
        return {
            "max_health": self.max_health,
            "health": self.health,
            "max_stamina": self.max_stamina,
            "stamina": self.stamina,
            "max_magic": self.max_magic,
            "magic": self.magic,
            "attack_power": self.attack_power,
            "defense": self.defense,
            "speed": self.speed,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> Stats:
        return cls(**data)
