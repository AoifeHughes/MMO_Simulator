"""
Handles action requests from clients
"""

import time
import logging
from typing import Optional

from server.core.game_state import GameState
from shared.messages import (
    ActionMessage, ActionResultMessage, ActionType,
    EventMessage, EventType
)
from shared.math_utils import Vector2
from shared.constants import (
    MAX_MOVE_SPEED, DEFAULT_ATTACK_RANGE, DEFAULT_ATTACK_COOLDOWN
)

logger = logging.getLogger(__name__)


class ActionHandler:
    """Processes and validates client actions"""

    def __init__(self, game_state: GameState):
        self.game_state = game_state

    async def handle_action(self, client_id: str, action_msg: ActionMessage) -> ActionResultMessage:
        """Process an action from a client"""
        # Get agent entity
        entity_id = self.game_state.agents.get(client_id)
        if not entity_id:
            return ActionResultMessage(
                action=action_msg.action,
                success=False,
                error_message="Agent entity not found"
            )

        entity = self.game_state.get_entity(entity_id)
        if not entity:
            return ActionResultMessage(
                action=action_msg.action,
                success=False,
                error_message="Entity not found"
            )

        # Touch player to update activity
        self.game_state.touch_player(entity_id)

        # Route to specific handler
        if action_msg.action == ActionType.MOVE:
            return await self._handle_move(entity, action_msg.data)
        elif action_msg.action == ActionType.ATTACK:
            return await self._handle_attack(entity, action_msg.data)
        elif action_msg.action == ActionType.INTERACT:
            return await self._handle_interact(entity, action_msg.data)
        elif action_msg.action == ActionType.USE_ABILITY:
            return await self._handle_use_ability(entity, action_msg.data)
        elif action_msg.action == ActionType.CHAT:
            return await self._handle_chat(entity, action_msg.data)
        else:
            return ActionResultMessage(
                action=action_msg.action,
                success=False,
                error_message=f"Unknown action type: {action_msg.action}"
            )

    async def _handle_move(self, entity, data: dict) -> ActionResultMessage:
        """Handle movement action"""
        # Validate data
        if 'target' not in data:
            return ActionResultMessage(
                action=ActionType.MOVE,
                success=False,
                error_message="Missing target position"
            )

        try:
            target_pos = Vector2(data['target'][0], data['target'][1])
        except:
            return ActionResultMessage(
                action=ActionType.MOVE,
                success=False,
                error_message="Invalid target format"
            )

        # Calculate direction and speed
        direction = (target_pos - entity.position).normalize()
        speed = data.get('speed', 'walk')

        # Set speed based on mode
        move_speed = 50.0  # Default walk speed
        if speed == 'run':
            move_speed = 100.0
        elif speed == 'sneak':
            move_speed = 25.0

        # Validate speed (anti-cheat)
        if move_speed > MAX_MOVE_SPEED:
            return ActionResultMessage(
                action=ActionType.MOVE,
                success=False,
                error_message="Invalid movement speed"
            )

        # Update entity velocity
        entity.velocity = direction * move_speed
        entity.state = 'moving'

        logger.debug(f"Entity {entity.id} moving to {target_pos} at {move_speed} u/s")

        return ActionResultMessage(
            action=ActionType.MOVE,
            success=True,
            result={
                'target': data['target'],
                'speed': move_speed,
                'eta': entity.position.distance_to(target_pos) / move_speed
            }
        )

    async def _handle_attack(self, entity, data: dict) -> ActionResultMessage:
        """Handle attack action"""
        # Check if alive
        if not entity.alive:
            return ActionResultMessage(
                action=ActionType.ATTACK,
                success=False,
                error_message="Cannot attack while dead"
            )

        # Validate target
        if 'target_id' not in data:
            return ActionResultMessage(
                action=ActionType.ATTACK,
                success=False,
                error_message="Missing target"
            )

        target = self.game_state.get_entity(data['target_id'])
        if not target:
            return ActionResultMessage(
                action=ActionType.ATTACK,
                success=False,
                error_message="Target not found"
            )

        if not target.alive:
            return ActionResultMessage(
                action=ActionType.ATTACK,
                success=False,
                error_message="Target is already dead"
            )

        # Check range
        distance = entity.position.distance_to(target.position)
        attack_range = data.get('range', DEFAULT_ATTACK_RANGE)

        if distance > attack_range:
            return ActionResultMessage(
                action=ActionType.ATTACK,
                success=False,
                error_message=f"Target out of range ({distance:.1f} > {attack_range})"
            )

        # Check cooldown
        current_time = time.time()
        cooldown = data.get('cooldown', DEFAULT_ATTACK_COOLDOWN)
        if current_time - entity.last_attack_time < cooldown:
            return ActionResultMessage(
                action=ActionType.ATTACK,
                success=False,
                error_message="Attack on cooldown"
            )

        # Calculate damage (simplified)
        import random
        base_damage = entity.level * 5
        damage = random.randint(int(base_damage * 0.8), int(base_damage * 1.2))

        # Apply damage
        self.game_state.apply_damage(target.id, damage, entity.id)
        entity.last_attack_time = current_time

        # Broadcast combat event
        from server.core.world_server import EventMessage, EventType
        combat_event = EventMessage(
            event=EventType.COMBAT,
            data={
                'attacker_id': entity.id,
                'target_id': target.id,
                'damage': damage,
                'target_health': target.health
            },
            position=entity.position.to_tuple()
        )
        # Note: In real implementation, would get world_server reference
        # await self.world_server.broadcast_event(combat_event, entity.position)

        logger.info(f"Entity {entity.id} attacked {target.id} for {damage} damage")

        return ActionResultMessage(
            action=ActionType.ATTACK,
            success=True,
            result={
                'damage': damage,
                'target_health': target.health,
                'target_alive': target.alive
            }
        )

    async def _handle_interact(self, entity, data: dict) -> ActionResultMessage:
        """Handle interaction action"""
        # Validate target
        if 'target_id' not in data:
            return ActionResultMessage(
                action=ActionType.INTERACT,
                success=False,
                error_message="Missing interaction target"
            )

        target = self.game_state.get_entity(data['target_id'])
        if not target:
            return ActionResultMessage(
                action=ActionType.INTERACT,
                success=False,
                error_message="Target not found"
            )

        # Check distance
        distance = entity.position.distance_to(target.position)
        if distance > 10.0:  # Interaction range
            return ActionResultMessage(
                action=ActionType.INTERACT,
                success=False,
                error_message="Target too far away"
            )

        # Process interaction based on target type
        result = {}
        if target.entity_type == 'npc':
            # NPC interaction
            result = {
                'type': 'dialogue',
                'npc_name': target.name,
                'message': f"Hello, {entity.name}! How can I help you?"
            }
        elif target.entity_type == 'object':
            # Object interaction
            result = {
                'type': 'object',
                'object_name': target.name,
                'action': 'examined'
            }

        entity.state = 'interacting'

        return ActionResultMessage(
            action=ActionType.INTERACT,
            success=True,
            result=result
        )

    async def _handle_use_ability(self, entity, data: dict) -> ActionResultMessage:
        """Handle ability use"""
        # Simplified ability system
        ability_name = data.get('ability', 'unknown')

        # Check if entity has mana
        if not hasattr(entity, 'mana'):
            return ActionResultMessage(
                action=ActionType.USE_ABILITY,
                success=False,
                error_message="Cannot use abilities"
            )

        # Mock ability execution
        return ActionResultMessage(
            action=ActionType.USE_ABILITY,
            success=True,
            result={
                'ability': ability_name,
                'cooldown': 5.0
            }
        )

    async def _handle_chat(self, entity, data: dict) -> ActionResultMessage:
        """Handle chat message"""
        message = data.get('message', '')
        channel = data.get('channel', 'local')

        if not message:
            return ActionResultMessage(
                action=ActionType.CHAT,
                success=False,
                error_message="Empty message"
            )

        # Broadcast chat event
        chat_event = EventMessage(
            event=EventType.CHAT,
            data={
                'sender_id': entity.id,
                'sender_name': entity.name,
                'message': message[:256],  # Limit length
                'channel': channel
            },
            position=entity.position.to_tuple() if channel == 'local' else None
        )

        # Note: Would broadcast through world_server
        logger.info(f"{entity.name} [{channel}]: {message}")

        return ActionResultMessage(
            action=ActionType.CHAT,
            success=True,
            result={'message_sent': True}
        )