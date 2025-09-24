"""
Weapon selection and combat nodes for behavior trees.
"""

from typing import List, Optional

from shared.actions import ActionRequest, ActionType, attack_target_params, equip_item_params
from shared.items import Weapon, WeaponType

from .base import ActionNode, ConditionNode, NodeStatus


class SelectBestWeapon(ActionNode):
    """Action node that selects and equips the best weapon for a given distance"""

    def __init__(self, target_distance: float):
        super().__init__("SelectBestWeapon")
        self.target_distance = target_distance
        self.last_equipped_weapon = None

    def start_action(self, agent) -> bool:
        """Start weapon selection"""
        return True

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Select and equip the best weapon for the target distance"""
        # For now, simulate weapon selection based on distance
        # In a full implementation, this would query the agent's inventory

        best_weapon_type = self._get_best_weapon_type_for_distance(self.target_distance)

        # Check if we need to switch weapons
        if self.last_equipped_weapon != best_weapon_type:
            self._request_weapon_equip(agent, best_weapon_type)
            self.last_equipped_weapon = best_weapon_type

        return NodeStatus.SUCCESS

    def stop_action(self, agent):
        """Stop weapon selection"""
        pass

    def _get_best_weapon_type_for_distance(self, distance: float) -> str:
        """Get the best weapon type for a given distance"""
        # Bow range: 3-15 units
        if 3.0 <= distance <= 15.0:
            return "bow"
        # Sword range: 0.5-2.5 units
        elif 0.5 <= distance <= 2.5:
            return "sword"
        # Default to punch if nothing else works
        else:
            return "punch"

    def _request_weapon_equip(self, agent, weapon_type: str):
        """Request weapon equipment from server"""
        # This is a simplified implementation
        # In reality, we'd need to find the weapon in inventory by ID
        if hasattr(agent, 'action_manager') and agent.action_manager:
            # For now, just store the preferred weapon type
            # The combat action will use this information
            if not hasattr(agent, 'preferred_weapon'):
                agent.preferred_weapon = weapon_type
            else:
                agent.preferred_weapon = weapon_type

    def set_target_distance(self, distance: float):
        """Update the target distance for weapon selection"""
        self.target_distance = distance

    def reset(self):
        """Reset weapon selection state"""
        super().reset()
        self.last_equipped_weapon = None


class HasWeaponForRange(ConditionNode):
    """Condition node that checks if agent has a weapon suitable for given range"""

    def __init__(self, min_range: float, max_range: float):
        super().__init__("HasWeaponForRange")
        self.min_range = min_range
        self.max_range = max_range

    def check_condition(self, agent) -> bool:
        """Check if agent has weapon suitable for the range"""
        # Simplified check - assume players have both sword and bow
        if agent.agent_type == "player":
            # Bow range: 3-15, Sword range: 0.5-2.5
            bow_overlaps = not (self.max_range < 3.0 or self.min_range > 15.0)
            sword_overlaps = not (self.max_range < 0.5 or self.min_range > 2.5)

            if bow_overlaps or sword_overlaps:
                return True

        return False


class AttackWithBestWeapon(ActionNode):
    """Action node that attacks with the best weapon for target distance"""

    def __init__(self, enemy_types: List[str]):
        super().__init__("AttackWithBestWeapon")
        self.enemy_types = enemy_types
        self.last_attack_time = 0
        self.attack_cooldown = 1.5  # Base cooldown

    def start_action(self, agent) -> bool:
        """Start attack action"""
        return True

    def update_action(self, agent, dt: float) -> NodeStatus:
        """Attack with the best weapon for current target distance"""
        # Use unified target manager for consistent target selection
        target_manager = agent.get_target_manager()
        target = target_manager.update_target_selection(
            agent,
            agent.visible_entities,
            self.enemy_types,
            max_range=20.0  # Large range for weapon selection
        )
        if not target:
            return NodeStatus.FAILURE

        # Calculate distance
        distance = ((target["x"] - agent.x) ** 2 + (target["y"] - agent.y) ** 2) ** 0.5

        # Select weapon based on distance using server data
        weapon_info = self._select_weapon_for_distance(distance, agent)
        if not weapon_info:
            return NodeStatus.FAILURE

        # Check if target is in weapon range
        if distance < weapon_info["min_range"] or distance > weapon_info["max_range"]:
            return NodeStatus.FAILURE

        # Check cooldown
        import time
        current_time = time.time()
        if current_time - self.last_attack_time < weapon_info["cooldown"]:
            return NodeStatus.RUNNING

        # Perform attack
        self._request_attack(agent, target["id"], weapon_info["attack_name"])
        self.last_attack_time = current_time

        return NodeStatus.SUCCESS

    def stop_action(self, agent):
        """Stop attack action"""
        pass

    # Removed _find_nearest_enemy - now using unified TargetManager

    def _select_weapon_for_distance(self, distance: float, agent) -> Optional[dict]:
        """Select the best weapon for the given distance using server data"""
        if not hasattr(agent, 'server_game_data') or not agent.server_game_data:
            # Fallback to hardcoded values if no server data
            return self._select_fallback_weapon_for_distance(distance)

        attacks = agent.server_game_data.get('attacks', {})
        character_attacks = agent.server_game_data.get('character_attacks', {})
        available_attacks = character_attacks.get(agent.agent_type, [])

        # Find attacks that can hit at this distance
        usable_weapons = []
        for attack_name in available_attacks:
            if attack_name in attacks:
                attack_data = attacks[attack_name]
                min_range = attack_data.get('min_range', 0.0)
                max_range = attack_data.get('max_range', 1.0)

                if min_range <= distance <= max_range:
                    weapon_info = {
                        "name": attack_name,
                        "attack_name": attack_name,
                        "min_range": min_range,
                        "max_range": max_range,
                        "damage": attack_data.get('damage', 1.0),
                        "cooldown": attack_data.get('cooldown', 1.0)
                    }
                    usable_weapons.append(weapon_info)

        if not usable_weapons:
            return None

        # Return weapon with highest damage
        return max(usable_weapons, key=lambda w: w["damage"])

    def _select_fallback_weapon_for_distance(self, distance: float) -> Optional[dict]:
        """Fallback weapon selection if no server data available"""
        weapons = [
            {
                "name": "bow",
                "attack_name": "bow_shot",
                "min_range": 3.0,
                "max_range": 15.0,
                "damage": 20.0,
                "cooldown": 2.0
            },
            {
                "name": "sword",
                "attack_name": "sword_slash",
                "min_range": 0.5,
                "max_range": 2.5,
                "damage": 15.0,
                "cooldown": 1.5
            },
            {
                "name": "punch",
                "attack_name": "punch",
                "min_range": 0.0,
                "max_range": 1.5,
                "damage": 8.0,
                "cooldown": 1.0
            }
        ]

        usable_weapons = []
        for weapon in weapons:
            if weapon["min_range"] <= distance <= weapon["max_range"]:
                usable_weapons.append(weapon)

        if not usable_weapons:
            return None

        return max(usable_weapons, key=lambda w: w["damage"])

    def _request_attack(self, agent, target_id: str, attack_name: str):
        """Request attack action from server"""
        if hasattr(agent, 'action_manager') and agent.action_manager:
            import asyncio
            asyncio.create_task(agent.action_manager.request_action(
                action_type=ActionType.ATTACK_TARGET,
                parameters=attack_target_params(target_id, attack_name)
            ))
        else:
            # Fallback for legacy system
            if hasattr(agent, 'client') and agent.client:
                import asyncio
                asyncio.create_task(agent.client.request_action(
                    ActionType.ATTACK_TARGET,
                    attack_target_params(target_id, attack_name)
                ))

    def reset(self):
        """Reset attack state"""
        super().reset()
        self.last_attack_time = 0


class IsInWeaponRange(ConditionNode):
    """Condition node that checks if target is in range of any weapon"""

    def __init__(self, enemy_types: List[str]):
        super().__init__("IsInWeaponRange")
        self.enemy_types = enemy_types

    def check_condition(self, agent) -> bool:
        """Check if any enemy is in weapon range"""
        if not hasattr(agent, 'visible_entities') or not agent.visible_entities:
            return False

        # Check each visible enemy
        for entity in agent.visible_entities:
            if entity.get("agent_type") in self.enemy_types:
                distance = ((entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2) ** 0.5

                # Check if any weapon can reach this target
                if self._can_attack_at_distance(distance):
                    return True

        return False

    def _can_attack_at_distance(self, distance: float) -> bool:
        """Check if we have a weapon that can attack at this distance"""
        weapon_ranges = [
            (3.0, 15.0),  # Bow
            (0.5, 2.5),   # Sword
            (0.0, 1.5),   # Punch
        ]

        for min_range, max_range in weapon_ranges:
            if min_range <= distance <= max_range:
                return True

        return False