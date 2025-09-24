"""
Server-side attack system with melee and ranged attack definitions.

This module defines attack capabilities for different character types and validates
attack actions to prevent cheating.
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from shared.items import Weapon, WeaponType


class AttackType(Enum):
    MELEE = "melee"
    RANGED = "ranged"


@dataclass
class AttackDefinition:
    """Server-side attack definition"""

    name: str
    attack_type: AttackType
    damage: float
    min_range: float  # Minimum effective range
    max_range: float  # Maximum effective range
    cooldown: float  # Seconds between attacks
    description: str


class AttackSystem:
    """Server-side attack system that manages attack definitions and validation"""

    def __init__(self):
        self.attack_definitions: Dict[str, AttackDefinition] = {}
        self.character_attacks: Dict[
            str, List[str]
        ] = {}  # character_type -> attack_names
        self._initialize_attacks()

    def _initialize_attacks(self):
        """Initialize default attack definitions"""

        # Melee attacks - close range combat
        self.attack_definitions["punch"] = AttackDefinition(
            name="punch",
            attack_type=AttackType.MELEE,
            damage=8.0,
            min_range=0.0,
            max_range=1.5,  # Touching to slightly away
            cooldown=1.0,
            description="Basic melee punch",
        )

        self.attack_definitions["sword_slash"] = AttackDefinition(
            name="sword_slash",
            attack_type=AttackType.MELEE,
            damage=15.0,
            min_range=0.5,
            max_range=2.5,  # Sword reach
            cooldown=1.5,
            description="Sword melee attack",
        )

        self.attack_definitions["claw"] = AttackDefinition(
            name="claw",
            attack_type=AttackType.MELEE,
            damage=12.0,
            min_range=0.0,
            max_range=1.8,
            cooldown=0.8,
            description="Beast claw attack",
        )

        # Ranged attacks - distant combat
        self.attack_definitions["bow_shot"] = AttackDefinition(
            name="bow_shot",
            attack_type=AttackType.RANGED,
            damage=20.0,
            min_range=3.0,  # Minimum range for effectiveness
            max_range=15.0,
            cooldown=2.0,
            description="Bow and arrow attack",
        )

        self.attack_definitions["magic_bolt"] = AttackDefinition(
            name="magic_bolt",
            attack_type=AttackType.RANGED,
            damage=18.0,
            min_range=2.0,
            max_range=12.0,
            cooldown=1.8,
            description="Magical projectile",
        )

        self.attack_definitions["throwing_knife"] = AttackDefinition(
            name="throwing_knife",
            attack_type=AttackType.RANGED,
            damage=10.0,
            min_range=1.5,
            max_range=8.0,
            cooldown=1.2,
            description="Thrown blade",
        )

        # Character type attack assignments (for legacy support)
        self.character_attacks["player"] = ["punch", "sword_slash", "bow_shot"]
        self.character_attacks["enemy"] = ["claw", "throwing_knife"]
        self.character_attacks["npc"] = ["punch"]  # NPCs are peaceful mostly
        self.character_attacks["explorer"] = ["punch", "magic_bolt"]

    def get_weapon_attack_name(self, weapon: Weapon) -> str:
        """Get the appropriate attack name for a weapon"""
        return weapon.get_attack_name()

    def can_use_weapon(self, character_type: str, weapon: Weapon) -> bool:
        """Check if a character type can use a specific weapon"""
        # For now, all characters can use all weapons they possess
        # This can be expanded for class restrictions later
        return True

    def get_best_weapon_for_distance(
        self, weapons: List[Weapon], distance: float
    ) -> Optional[Weapon]:
        """Get the best weapon for attacking at a given distance"""
        usable_weapons = []

        for weapon in weapons:
            if weapon.min_range <= distance <= weapon.max_range:
                usable_weapons.append(weapon)

        if not usable_weapons:
            return None

        # Prefer higher damage weapons
        return max(usable_weapons, key=lambda w: w.damage)

    def get_character_attacks(self, character_type: str) -> List[AttackDefinition]:
        """Get all available attacks for a character type"""
        attack_names = self.character_attacks.get(character_type, [])
        return [
            self.attack_definitions[name]
            for name in attack_names
            if name in self.attack_definitions
        ]

    def get_attack_definition(self, attack_name: str) -> Optional[AttackDefinition]:
        """Get a specific attack definition"""
        return self.attack_definitions.get(attack_name)

    def validate_attack_with_weapon(
        self,
        attacker_id: str,
        weapon: Weapon,
        target_id: str,
        attacker_pos: tuple,
        target_pos: tuple,
        last_attack_time: float = 0,
    ) -> tuple:
        """
        Validate if an attack is legal using a weapon

        Returns: (is_valid: bool, reason: str)
        """
        # Check cooldown based on weapon attack speed
        current_time = time.time()
        cooldown = 1.0 / weapon.attack_speed if weapon.attack_speed > 0 else 1.0
        if current_time - last_attack_time < cooldown:
            remaining = cooldown - (current_time - last_attack_time)
            return False, f"Attack on cooldown ({remaining:.1f}s remaining)"

        # Check range
        dx = target_pos[0] - attacker_pos[0]
        dy = target_pos[1] - attacker_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5

        if distance < weapon.min_range:
            return False, f"Target too close ({distance:.1f} < {weapon.min_range})"

        if distance > weapon.max_range:
            return False, f"Target too far ({distance:.1f} > {weapon.max_range})"

        return True, "Valid attack"

    def validate_attack(
        self,
        attacker_id: str,
        attack_name: str,
        target_id: str,
        attacker_pos: tuple,
        target_pos: tuple,
        character_type: str,
        last_attack_time: float = 0,
    ) -> tuple:
        """
        Validate if an attack is legal

        Returns: (is_valid: bool, reason: str)
        """
        # Check if attack exists
        attack_def = self.get_attack_definition(attack_name)
        if not attack_def:
            return False, f"Unknown attack: {attack_name}"

        # Check if character can use this attack
        available_attacks = self.get_character_attacks(character_type)
        if attack_def not in available_attacks:
            return False, f"Character type {character_type} cannot use {attack_name}"

        # Check cooldown
        current_time = time.time()
        if current_time - last_attack_time < attack_def.cooldown:
            remaining = attack_def.cooldown - (current_time - last_attack_time)
            return False, f"Attack on cooldown ({remaining:.1f}s remaining)"

        # Check range
        dx = target_pos[0] - attacker_pos[0]
        dy = target_pos[1] - attacker_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5

        if distance < attack_def.min_range:
            return False, f"Target too close ({distance:.1f} < {attack_def.min_range})"

        if distance > attack_def.max_range:
            return False, f"Target too far ({distance:.1f} > {attack_def.max_range})"

        return True, "Valid attack"

    def get_all_attacks_for_client(self) -> Dict:
        """Get all attack definitions formatted for client consumption"""
        client_data = {"attacks": {}, "character_attacks": self.character_attacks}

        for name, attack_def in self.attack_definitions.items():
            client_data["attacks"][name] = {
                "name": attack_def.name,
                "type": attack_def.attack_type.value,
                "damage": attack_def.damage,
                "min_range": attack_def.min_range,
                "max_range": attack_def.max_range,
                "cooldown": attack_def.cooldown,
                "description": attack_def.description,
            }

        return client_data
