import asyncio
import math
import time

import pytest

from server.attack_system import AttackSystem, AttackType


class TestAttackSystem:
    """Test suite for the server-side attack system"""

    def test_attack_system_initialization(self):
        """Test that attack system initializes with proper attacks"""
        attack_system = AttackSystem()

        # Check that we have both melee and ranged attacks
        punch = attack_system.get_attack_definition("punch")
        assert punch is not None
        assert punch.attack_type == AttackType.MELEE
        assert punch.max_range == 1.5

        bow_shot = attack_system.get_attack_definition("bow_shot")
        assert bow_shot is not None
        assert bow_shot.attack_type == AttackType.RANGED
        assert bow_shot.max_range == 15.0

    def test_character_specific_attacks(self):
        """Test that different character types have different attacks"""
        attack_system = AttackSystem()

        # Check player attacks
        player_attacks = attack_system.get_character_attacks("player")
        player_names = [attack.name for attack in player_attacks]
        assert "punch" in player_names
        assert "sword_slash" in player_names
        assert "bow_shot" in player_names

        # Check enemy attacks
        enemy_attacks = attack_system.get_character_attacks("enemy")
        enemy_names = [attack.name for attack in enemy_attacks]
        assert "claw" in enemy_names
        assert "throwing_knife" in enemy_names
        assert "sword_slash" not in enemy_names  # Enemies don't have swords

        # Check NPC attacks (peaceful)
        npc_attacks = attack_system.get_character_attacks("npc")
        npc_names = [attack.name for attack in npc_attacks]
        assert "punch" in npc_names
        assert len(npc_names) == 1  # NPCs only have basic attack

    def test_melee_attack_validation(self):
        """Test melee attack range validation"""
        attack_system = AttackSystem()

        # Test valid melee range (punch)
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "punch",
            "target1",
            (0.0, 0.0),
            (1.0, 0.0),  # 1.0 distance
            "player",
            0,
        )
        assert is_valid, f"Valid melee attack rejected: {reason}"

        # Test too far for melee
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "punch",
            "target1",
            (0.0, 0.0),
            (2.0, 0.0),  # 2.0 distance, punch max is 1.5
            "player",
            0,
        )
        assert not is_valid
        assert "too far" in reason.lower()

    def test_ranged_attack_validation(self):
        """Test ranged attack range validation"""
        attack_system = AttackSystem()

        # Test valid ranged attack
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "bow_shot",
            "target1",
            (0.0, 0.0),
            (10.0, 0.0),  # 10.0 distance
            "player",
            0,
        )
        assert is_valid, f"Valid ranged attack rejected: {reason}"

        # Test too close for ranged (ineffective)
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "bow_shot",
            "target1",
            (0.0, 0.0),
            (1.0, 0.0),  # 1.0 distance, bow min is 3.0
            "player",
            0,
        )
        assert not is_valid
        assert "too close" in reason.lower()

        # Test too far for ranged
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "bow_shot",
            "target1",
            (0.0, 0.0),
            (20.0, 0.0),  # 20.0 distance, bow max is 15.0
            "player",
            0,
        )
        assert not is_valid
        assert "too far" in reason.lower()

    def test_attack_cooldown_validation(self):
        """Test attack cooldown system"""
        attack_system = AttackSystem()

        current_time = time.time()

        # First attack should be valid
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "punch",
            "target1",
            (0.0, 0.0),
            (1.0, 0.0),
            "player",
            0,  # No previous attack
        )
        assert is_valid

        # Attack immediately after should be blocked by cooldown
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "punch",
            "target1",
            (0.0, 0.0),
            (1.0, 0.0),
            "player",
            current_time,  # Just attacked
        )
        assert not is_valid
        assert "cooldown" in reason.lower()

        # Attack after cooldown should be valid
        is_valid, reason = attack_system.validate_attack(
            "attacker1",
            "punch",
            "target1",
            (0.0, 0.0),
            (1.0, 0.0),
            "player",
            current_time - 2.0,  # 2 seconds ago, punch cooldown is 1.0
        )
        assert is_valid

    def test_character_attack_permissions(self):
        """Test that characters can only use their allowed attacks"""
        attack_system = AttackSystem()

        # Player should be able to use sword_slash
        is_valid, reason = attack_system.validate_attack(
            "player1", "sword_slash", "target1", (0.0, 0.0), (2.0, 0.0), "player", 0
        )
        assert is_valid

        # NPC should NOT be able to use sword_slash
        is_valid, reason = attack_system.validate_attack(
            "npc1", "sword_slash", "target1", (0.0, 0.0), (2.0, 0.0), "npc", 0
        )
        assert not is_valid
        assert "cannot use" in reason.lower()

        # Enemy should be able to use claw
        is_valid, reason = attack_system.validate_attack(
            "enemy1", "claw", "target1", (0.0, 0.0), (1.5, 0.0), "enemy", 0
        )
        assert is_valid

    def test_unknown_attack_validation(self):
        """Test validation of unknown attacks"""
        attack_system = AttackSystem()

        is_valid, reason = attack_system.validate_attack(
            "attacker1", "laser_beam", "target1", (0.0, 0.0), (5.0, 0.0), "player", 0
        )
        assert not is_valid
        assert "unknown attack" in reason.lower()

    def test_client_data_format(self):
        """Test that attack data is properly formatted for clients"""
        attack_system = AttackSystem()
        client_data = attack_system.get_all_attacks_for_client()

        # Check structure
        assert "attacks" in client_data
        assert "character_attacks" in client_data

        # Check attack definitions
        attacks = client_data["attacks"]
        assert "punch" in attacks
        assert "sword_slash" in attacks
        assert "bow_shot" in attacks

        # Check punch attack data
        punch_data = attacks["punch"]
        assert punch_data["name"] == "punch"
        assert punch_data["type"] == "melee"
        assert punch_data["damage"] == 8.0
        assert punch_data["min_range"] == 0.0
        assert punch_data["max_range"] == 1.5

        # Check character assignments
        char_attacks = client_data["character_attacks"]
        assert "player" in char_attacks
        assert "sword_slash" in char_attacks["player"]
        assert "enemy" in char_attacks
        assert "claw" in char_attacks["enemy"]

    def test_server_integration(self):
        """Test attack system integration with game server"""
        # This test would require a full server setup, which is complex
        # For now, just test that AttackSystem can be instantiated
        attack_system = AttackSystem()
        assert attack_system is not None

        # Test basic functionality
        punch_def = attack_system.get_attack_definition("punch")
        assert punch_def is not None
        assert punch_def.damage == 8.0
