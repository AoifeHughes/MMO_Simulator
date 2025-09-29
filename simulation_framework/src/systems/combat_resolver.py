from __future__ import annotations
from typing import Dict, Tuple, Optional, TYPE_CHECKING
import random
import math

if TYPE_CHECKING:
    from ..entities.base import Entity


class DamageType:
    PHYSICAL = "physical"
    MAGICAL = "magical"
    FIRE = "fire"
    ICE = "ice"
    POISON = "poison"
    HOLY = "holy"
    DARK = "dark"


class CombatResolver:
    def __init__(self):
        self.damage_type_effectiveness = {
            DamageType.FIRE: {DamageType.ICE: 1.5, DamageType.FIRE: 0.5},
            DamageType.ICE: {DamageType.FIRE: 1.5, DamageType.ICE: 0.5},
            DamageType.HOLY: {DamageType.DARK: 1.5, DamageType.HOLY: 0.5},
            DamageType.DARK: {DamageType.HOLY: 1.5, DamageType.DARK: 0.5},
        }

    def calculate_damage(
        self,
        attacker: Entity,
        defender: Entity,
        base_damage: int,
        damage_type: str = DamageType.PHYSICAL,
        critical_chance: float = 0.0,
        critical_multiplier: float = 2.0
    ) -> Tuple[int, bool, Dict]:
        attack_power = attacker.stats.attack_power
        defense = defender.stats.defense

        raw_damage = base_damage + attack_power

        effectiveness = self._get_damage_effectiveness(damage_type, defender)
        raw_damage = int(raw_damage * effectiveness)

        mitigated_damage = max(1, raw_damage - defense)

        is_critical = random.random() < critical_chance
        if is_critical:
            mitigated_damage = int(mitigated_damage * critical_multiplier)

        final_damage = self._apply_random_variance(mitigated_damage)

        damage_info = {
            "base_damage": base_damage,
            "attack_power": attack_power,
            "raw_damage": raw_damage,
            "defense": defense,
            "effectiveness": effectiveness,
            "damage_type": damage_type,
            "final_damage": final_damage
        }

        return final_damage, is_critical, damage_info

    def _get_damage_effectiveness(self, damage_type: str, defender: Entity) -> float:
        resistances = getattr(defender, 'resistances', {})
        weaknesses = getattr(defender, 'weaknesses', {})

        effectiveness = 1.0

        if damage_type in resistances:
            effectiveness *= (1.0 - resistances[damage_type])

        if damage_type in weaknesses:
            effectiveness *= (1.0 + weaknesses[damage_type])

        base_effectiveness = self.damage_type_effectiveness.get(damage_type, {})
        for defender_type in getattr(defender, 'damage_types', []):
            if defender_type in base_effectiveness:
                effectiveness *= base_effectiveness[defender_type]

        return max(0.1, min(3.0, effectiveness))

    def _apply_random_variance(self, damage: int, variance: float = 0.1) -> int:
        min_damage = int(damage * (1.0 - variance))
        max_damage = int(damage * (1.0 + variance))
        return random.randint(min_damage, max_damage)

    def calculate_hit_chance(
        self,
        attacker: Entity,
        defender: Entity,
        base_accuracy: float = 0.9,
        range_penalty: float = 0.0
    ) -> float:
        attacker_skill = getattr(attacker, 'combat_skill', 0)
        defender_evasion = getattr(defender, 'evasion_skill', 0)

        skill_modifier = (attacker_skill - defender_evasion) * 0.01
        hit_chance = base_accuracy + skill_modifier - range_penalty

        hit_chance = max(0.05, min(0.95, hit_chance))
        return hit_chance

    def resolve_attack(
        self,
        attacker: Entity,
        defender: Entity,
        weapon_damage: int,
        damage_type: str = DamageType.PHYSICAL,
        critical_chance: float = 0.1,
        critical_multiplier: float = 2.0,
        base_accuracy: float = 0.9,
        attack_range: float = 1.0
    ) -> Dict:
        distance = attacker.distance_to(defender)
        range_penalty = max(0, (distance - attack_range) * 0.1)

        hit_chance = self.calculate_hit_chance(attacker, defender, base_accuracy, range_penalty)

        hit = random.random() < hit_chance

        result = {
            "hit": hit,
            "distance": distance,
            "hit_chance": hit_chance,
            "damage": 0,
            "is_critical": False,
            "damage_info": {},
            "target_died": False
        }

        if hit:
            damage, is_critical, damage_info = self.calculate_damage(
                attacker, defender, weapon_damage, damage_type, critical_chance, critical_multiplier
            )

            actual_damage = defender.take_damage(damage, attacker)
            target_died = not defender.stats.is_alive()

            result.update({
                "damage": actual_damage,
                "is_critical": is_critical,
                "damage_info": damage_info,
                "target_died": target_died
            })

        return result

    def get_combat_modifiers(self, entity: Entity) -> Dict:
        modifiers = {
            "attack_bonus": 0,
            "defense_bonus": 0,
            "critical_chance_bonus": 0.0,
            "accuracy_bonus": 0.0,
            "damage_multiplier": 1.0
        }

        for effect in entity.status_effects:
            if effect.effect_type == "strength":
                modifiers["attack_bonus"] += int(effect.power)
            elif effect.effect_type == "defense":
                modifiers["defense_bonus"] += int(effect.power)
            elif effect.effect_type == "precision":
                modifiers["accuracy_bonus"] += effect.power * 0.01
            elif effect.effect_type == "weakness":
                modifiers["damage_multiplier"] *= 0.5
            elif effect.effect_type == "rage":
                modifiers["attack_bonus"] += int(effect.power)
                modifiers["critical_chance_bonus"] += 0.1

        return modifiers