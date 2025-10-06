from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..systems.combat_resolver import CombatResolver, DamageType
from .base import Action, ActionResult, Event, ResourceCost

if TYPE_CHECKING:
    from ..core.world import World
    from ..entities.base import Entity


class CombatAction(Action):
    def __init__(
        self,
        actor_id: int,
        target_id: int,
        damage_type: str = DamageType.PHYSICAL,
        base_range: float = 1.0,
    ):
        super().__init__(actor_id)
        self.target_id = target_id
        self.damage_type = damage_type
        self.base_range = base_range
        self.combat_resolver = CombatResolver()

    def can_execute(self, actor: Entity, world: World) -> bool:
        target = world.entities.get(self.target_id)
        if not target:
            return False

        if not target.stats.is_alive():
            return False

        distance = actor.distance_to(target)
        # Add small epsilon for floating-point tolerance
        if distance > self.base_range + 0.01:
            return False

        return self.get_cost().can_afford(actor)

    def execute(self, actor: Entity, world: World) -> ActionResult:
        target = world.entities.get(self.target_id)
        if not target:
            return ActionResult.failure("Target not found")

        if not self.can_execute(actor, world):
            return ActionResult.failure("Cannot execute attack")

        cost = self.get_cost()
        if not cost.consume(actor):
            return ActionResult.failure("Insufficient resources for attack")

        weapon_damage, critical_chance, critical_multiplier, accuracy = (
            self._get_weapon_stats(actor)
        )

        combat_result = self.combat_resolver.resolve_attack(
            attacker=actor,
            defender=target,
            weapon_damage=weapon_damage,
            damage_type=self.damage_type,
            critical_chance=critical_chance,
            critical_multiplier=critical_multiplier,
            base_accuracy=accuracy,
            attack_range=self.base_range,
        )

        events = []
        if combat_result["hit"]:
            damage = combat_result["damage"]
            is_critical = combat_result["is_critical"]
            target_died = combat_result["target_died"]

            attack_event = Event(
                event_type="attack_hit",
                actor_id=actor.id,
                target_id=target.id,
                data={
                    "damage": damage,
                    "is_critical": is_critical,
                    "damage_type": self.damage_type,
                    "target_died": target_died,
                    **combat_result["damage_info"],
                },
            )
            events.append(attack_event)

            if target_died:
                death_event = Event(
                    event_type="entity_death",
                    actor_id=target.id,
                    target_id=actor.id,
                    data={"killed_by": actor.id, "cause": "combat"},
                )
                events.append(death_event)

                message = (
                    f"Killed {target.name} with {damage} {self.damage_type} damage"
                )
                if is_critical:
                    message += " (Critical Hit!)"
            else:
                message = f"Hit {target.name} for {damage} {self.damage_type} damage"
                if is_critical:
                    message += " (Critical Hit!)"

            return ActionResult.success(message, events)
        else:
            miss_event = Event(
                event_type="attack_miss",
                actor_id=actor.id,
                target_id=target.id,
                data={
                    "hit_chance": combat_result["hit_chance"],
                    "distance": combat_result["distance"],
                },
            )
            events.append(miss_event)
            return ActionResult.success(f"Missed attack on {target.name}", events)

    def _get_weapon_stats(self, actor: Entity) -> tuple[int, float, float, float]:
        weapon = actor.inventory.get_equipped_weapon()

        if weapon:
            damage = weapon.get_damage()
            critical_chance = weapon.get_critical_chance()
            critical_multiplier = weapon.get_critical_multiplier()
            accuracy = 0.9
        else:
            damage = 5
            critical_chance = 0.05
            critical_multiplier = 2.0
            accuracy = 0.8

        modifiers = self.combat_resolver.get_combat_modifiers(actor)
        damage += modifiers["attack_bonus"]
        critical_chance += modifiers["critical_chance_bonus"]
        damage = int(damage * modifiers["damage_multiplier"])
        accuracy += modifiers["accuracy_bonus"]

        return damage, critical_chance, critical_multiplier, accuracy

    def get_duration(self) -> int:
        return 2

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=3)

    def __repr__(self) -> str:
        return f"CombatAction(target={self.target_id}, type={self.damage_type})"


class MeleeAttack(CombatAction):
    def __init__(self, actor_id: int, target_id: int):
        super().__init__(
            actor_id=actor_id,
            target_id=target_id,
            damage_type=DamageType.PHYSICAL,
            base_range=1.5,  # Changed from 1.0 to allow diagonal attacks
        )

    def can_execute(self, actor: Entity, world: World) -> bool:
        weapon = actor.inventory.get_equipped_weapon()
        if weapon and weapon.get_attack_type() not in ["melee", "weapon"]:
            return False

        return super().can_execute(actor, world)

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=5)


class RangedAttack(CombatAction):
    def __init__(self, actor_id: int, target_id: int, weapon_range: float = 10.0):
        super().__init__(
            actor_id=actor_id,
            target_id=target_id,
            damage_type=DamageType.PHYSICAL,
            base_range=weapon_range,
        )

    def can_execute(self, actor: Entity, world: World) -> bool:
        weapon = actor.inventory.get_equipped_weapon()
        if not weapon or weapon.get_attack_type() != "ranged":
            return False

        self.base_range = weapon.get_range()
        return super().can_execute(actor, world)

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=4)


class MagicAttack(CombatAction):
    def __init__(
        self,
        actor_id: int,
        target_id: int,
        spell_type: str = DamageType.MAGICAL,
        spell_range: float = 15.0,
    ):
        super().__init__(
            actor_id=actor_id,
            target_id=target_id,
            damage_type=spell_type,
            base_range=spell_range,
        )

    def can_execute(self, actor: Entity, world: World) -> bool:
        weapon = actor.inventory.get_equipped_weapon()
        if weapon:
            if weapon.get_attack_type() == "magic":
                self.base_range = weapon.get_range()
            else:
                self.base_range = 5.0

        magic_cost = self._get_magic_cost(actor)
        if actor.stats.magic < magic_cost:
            return False

        return super().can_execute(actor, world)

    def _get_magic_cost(self, actor: Entity) -> int:
        weapon = actor.inventory.get_equipped_weapon()
        if weapon and weapon.get_attack_type() == "magic":
            return weapon.get_magic_cost()
        return 10

    def get_cost(self) -> ResourceCost:
        magic_cost = 10
        return ResourceCost(stamina=2, magic=magic_cost)


class DefendAction(Action):
    def __init__(self, actor_id: int, duration: int = 3):
        super().__init__(actor_id)
        self.defense_duration = duration

    def can_execute(self, actor: Entity, world: World) -> bool:
        return not actor.has_status_effect("defending")

    def execute(self, actor: Entity, world: World) -> ActionResult:
        if not self.can_execute(actor, world):
            return ActionResult.failure("Already defending")

        from ..entities.base import StatusEffect

        defend_effect = StatusEffect(
            name="defending",
            duration=self.defense_duration,
            effect_type="defense",
            power=actor.stats.defense * 0.5,
        )

        actor.apply_status_effect(defend_effect)

        event = Event(
            event_type="defend",
            actor_id=actor.id,
            data={
                "defense_bonus": defend_effect.power,
                "duration": self.defense_duration,
            },
        )

        return ActionResult.success("Entered defensive stance", [event])

    def get_duration(self) -> int:
        return 1

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=1)


class FleeAction(Action):
    def __init__(self, actor_id: int, flee_distance: int = 3):
        super().__init__(actor_id)
        self.flee_distance = flee_distance

    def can_execute(self, actor: Entity, world: World) -> bool:
        return self.get_cost().can_afford(actor)

    def execute(self, actor: Entity, world: World) -> ActionResult:
        if not self.can_execute(actor, world):
            return ActionResult.failure("Cannot flee")

        cost = self.get_cost()
        if not cost.consume(actor):
            return ActionResult.failure("Not enough stamina to flee")

        current_x, current_y = actor.position
        best_position = None
        max_distance = 0

        for dx in range(-self.flee_distance, self.flee_distance + 1):
            for dy in range(-self.flee_distance, self.flee_distance + 1):
                if dx == 0 and dy == 0:
                    continue

                new_x, new_y = current_x + dx, current_y + dy
                if not world.is_valid_position(new_x, new_y) or not world.is_passable(
                    new_x, new_y
                ):
                    continue

                distance = math.sqrt(dx**2 + dy**2)
                if distance > max_distance:
                    max_distance = distance
                    best_position = (new_x, new_y)

        if best_position:
            success = world.move_entity(actor, best_position[0], best_position[1])
            if success:
                event = Event(
                    event_type="flee",
                    actor_id=actor.id,
                    data={
                        "from": (current_x, current_y),
                        "to": best_position,
                        "distance": max_distance,
                    },
                )
                return ActionResult.success(f"Fled to {best_position}", [event])

        return ActionResult.failure("Could not find safe position to flee to")

    def get_duration(self) -> int:
        return 1

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=10)
