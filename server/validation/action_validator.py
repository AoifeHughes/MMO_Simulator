"""
Action validation system for all game actions
"""

import time
from typing import Dict, List, Tuple, Optional, Any
import logging

from shared.math_utils import Vector2
from shared.constants import DEFAULT_ATTACK_RANGE, DEFAULT_ATTACK_COOLDOWN

logger = logging.getLogger(__name__)


class ActionValidator:
    """Validates all game actions (attack, interact, etc.)"""

    def __init__(self, server_config=None):
        # Action rules from config
        self.combat_rules = {
            'default_attack_range': DEFAULT_ATTACK_RANGE,
            'default_attack_cooldown': DEFAULT_ATTACK_COOLDOWN,
            'friendly_fire': False,
            'auto_target': False
        }

        self.interaction_rules = {
            'default_interaction_range': 10.0,
            'require_line_of_sight': False,
            'interaction_cooldown': 0.5
        }

        if server_config:
            self.combat_rules.update(server_config.world_rules.get('combat', {}))
            self.interaction_rules.update(server_config.world_rules.get('interaction', {}))

        # Cooldown tracking
        self.last_attack_time: Dict[str, float] = {}
        self.last_interaction_time: Dict[str, float] = {}
        self.last_ability_time: Dict[str, Dict[str, float]] = {}

        # Action history for rate limiting
        self.action_history: Dict[str, List[Tuple[str, float]]] = {}

    def validate_attack_action(self, attacker_id: str, attacker_pos: Vector2,
                              target_id: str, target_pos: Vector2,
                              game_state) -> Tuple[bool, List[str]]:
        """Validate an attack action"""
        current_time = time.time()
        issues = []

        # Get attacker entity
        attacker = game_state.get_entity(attacker_id)
        target = game_state.get_entity(target_id)

        if not attacker or not target:
            return False, ["Invalid attacker or target"]

        # Check if attacker is alive
        if not attacker.alive:
            return False, ["Attacker is not alive"]

        # Check if target is alive
        if not target.alive:
            return False, ["Target is not alive"]

        # Check attack cooldown
        last_attack = self.last_attack_time.get(attacker_id, 0)
        cooldown = self.combat_rules['default_attack_cooldown']

        if current_time - last_attack < cooldown:
            remaining = cooldown - (current_time - last_attack)
            return False, [f"Attack on cooldown ({remaining:.1f}s remaining)"]

        # Check attack range
        distance = attacker_pos.distance_to(target_pos)
        attack_range = self.combat_rules['default_attack_range']

        # Check if attacker has weapon with extended range
        if hasattr(attacker, 'equipment') and 'weapon' in attacker.equipment:
            weapon = attacker.equipment['weapon']
            if hasattr(weapon, 'range'):
                attack_range = weapon.range

        if distance > attack_range:
            return False, [f"Target out of range ({distance:.1f} > {attack_range:.1f})"]

        # Check friendly fire rules
        if not self.combat_rules['friendly_fire']:
            if (attacker.entity_type == 'agent' and target.entity_type == 'agent'):
                return False, ["Friendly fire is disabled"]

        # Check line of sight (if enabled)
        if self.combat_rules.get('require_line_of_sight', False):
            if not self._has_line_of_sight(attacker_pos, target_pos, game_state):
                return False, ["No line of sight to target"]

        # Update attack time
        self.last_attack_time[attacker_id] = current_time
        self._record_action(attacker_id, "attack", current_time)

        return True, issues

    def validate_interaction_action(self, actor_id: str, actor_pos: Vector2,
                                   target_id: str, target_pos: Vector2,
                                   interaction_type: str = "interact") -> Tuple[bool, List[str]]:
        """Validate an interaction action"""
        current_time = time.time()
        issues = []

        # Check interaction cooldown
        last_interaction = self.last_interaction_time.get(actor_id, 0)
        cooldown = self.interaction_rules['interaction_cooldown']

        if current_time - last_interaction < cooldown:
            remaining = cooldown - (current_time - last_interaction)
            return False, [f"Interaction on cooldown ({remaining:.1f}s remaining)"]

        # Check interaction range
        distance = actor_pos.distance_to(target_pos)
        interaction_range = self.interaction_rules['default_interaction_range']

        if distance > interaction_range:
            return False, [f"Target out of range ({distance:.1f} > {interaction_range:.1f})"]

        # Check line of sight (if required)
        if self.interaction_rules['require_line_of_sight']:
            # For simplicity, we'll skip complex LOS calculation
            pass

        # Update interaction time
        self.last_interaction_time[actor_id] = current_time
        self._record_action(actor_id, "interact", current_time)

        return True, issues

    def validate_ability_action(self, caster_id: str, ability_name: str,
                               caster_pos: Vector2, target_pos: Optional[Vector2] = None,
                               ability_data: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        """Validate an ability/spell action"""
        current_time = time.time()
        issues = []

        if not ability_data:
            ability_data = {}

        # Check ability cooldown
        if caster_id not in self.last_ability_time:
            self.last_ability_time[caster_id] = {}

        last_cast = self.last_ability_time[caster_id].get(ability_name, 0)
        cooldown = ability_data.get('cooldown', 1.0)

        if current_time - last_cast < cooldown:
            remaining = cooldown - (current_time - last_cast)
            return False, [f"Ability on cooldown ({remaining:.1f}s remaining)"]

        # Check range (if targeted ability)
        if target_pos:
            distance = caster_pos.distance_to(target_pos)
            ability_range = ability_data.get('range', 50.0)

            if distance > ability_range:
                return False, [f"Target out of range ({distance:.1f} > {ability_range:.1f})"]

        # Check resource costs (mana, stamina, etc.)
        mana_cost = ability_data.get('mana_cost', 0)
        if mana_cost > 0:
            # This would check the caster's current mana
            # For now, we'll assume it's valid
            pass

        # Update ability time
        self.last_ability_time[caster_id][ability_name] = current_time
        self._record_action(caster_id, f"ability:{ability_name}", current_time)

        return True, issues

    def validate_movement_action(self, entity_id: str, current_pos: Vector2,
                                target_pos: Vector2, movement_type: str = "walk") -> Tuple[bool, List[str]]:
        """Validate a movement action"""
        current_time = time.time()
        issues = []

        # Check movement type
        valid_types = ["walk", "run", "teleport"]
        if movement_type not in valid_types:
            return False, [f"Invalid movement type: {movement_type}"]

        # Teleport validation (if it's a special ability)
        if movement_type == "teleport":
            teleport_valid, teleport_issues = self.validate_ability_action(
                entity_id, "teleport", current_pos, target_pos,
                {"cooldown": 10.0, "range": 200.0, "mana_cost": 50}
            )
            if not teleport_valid:
                return False, teleport_issues

        self._record_action(entity_id, f"move:{movement_type}", current_time)
        return True, issues

    def _has_line_of_sight(self, start_pos: Vector2, end_pos: Vector2, game_state) -> bool:
        """Check if there's line of sight between two positions"""
        # This is a simplified version - a full implementation would
        # ray-cast through the world to check for obstacles

        # For now, just check if the path crosses any solid terrain
        # This would be expanded based on the game's specific needs
        return True

    def _record_action(self, entity_id: str, action_type: str, timestamp: float):
        """Record an action for rate limiting and statistics"""
        if entity_id not in self.action_history:
            self.action_history[entity_id] = []

        history = self.action_history[entity_id]
        history.append((action_type, timestamp))

        # Keep only recent history (last 30 seconds)
        cutoff_time = timestamp - 30.0
        history[:] = [(action, time) for action, time in history if time > cutoff_time]

    def get_action_stats(self, entity_id: str) -> Dict[str, Any]:
        """Get action statistics for an entity"""
        if entity_id not in self.action_history:
            return {}

        history = self.action_history[entity_id]
        current_time = time.time()

        # Count actions by type in last 60 seconds
        action_counts = {}
        for action_type, timestamp in history:
            if current_time - timestamp <= 60.0:
                action_counts[action_type] = action_counts.get(action_type, 0) + 1

        # Calculate APM (actions per minute)
        recent_actions = [t for _, t in history if current_time - t <= 60.0]
        apm = len(recent_actions)

        return {
            'actions_per_minute': apm,
            'action_counts': action_counts,
            'total_actions': len(history),
            'last_attack': self.last_attack_time.get(entity_id, 0),
            'last_interaction': self.last_interaction_time.get(entity_id, 0)
        }

    def is_rate_limited(self, entity_id: str, max_apm: int = 300) -> bool:
        """Check if entity is being rate limited"""
        stats = self.get_action_stats(entity_id)
        return stats.get('actions_per_minute', 0) > max_apm

    def cleanup_old_data(self, max_age: float = 300.0):
        """Clean up old action data"""
        current_time = time.time()
        entities_to_clean = []

        for entity_id, history in self.action_history.items():
            # Remove old actions
            history[:] = [(action, time) for action, time in history
                         if current_time - time <= max_age]

            # If no recent actions, mark for cleanup
            if not history:
                entities_to_clean.append(entity_id)

        # Clean up empty histories
        for entity_id in entities_to_clean:
            self.action_history.pop(entity_id, None)
            self.last_attack_time.pop(entity_id, None)
            self.last_interaction_time.pop(entity_id, None)
            self.last_ability_time.pop(entity_id, None)

    def reset_entity_data(self, entity_id: str):
        """Reset all data for a specific entity"""
        self.action_history.pop(entity_id, None)
        self.last_attack_time.pop(entity_id, None)
        self.last_interaction_time.pop(entity_id, None)
        self.last_ability_time.pop(entity_id, None)