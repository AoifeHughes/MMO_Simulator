#!/usr/bin/env python3
"""
Character-based agents using the new character class system
"""

import asyncio
import random
import logging
import time
from typing import Dict, Any

from client.core.agent_client import AgentClient, AgentConfig
from shared.character import Character, Warrior, Mage, CharacterClass
from shared.math_utils import Vector2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CharacterAgent(AgentClient):
    """Base agent that uses the character class system"""

    def __init__(self, name: str, character_class: str):
        # Map string to character class enum
        char_class_enum = CharacterClass.WARRIOR if character_class.lower() == 'warrior' else CharacterClass.MAGE

        config = AgentConfig(
            name=name,
            agent_class=character_class,
            personality={},
            behavior_params={}
        )
        super().__init__(config)

        # Create character instance
        if char_class_enum == CharacterClass.WARRIOR:
            self.character = Warrior(name)
        else:
            self.character = Mage(name)

        # Focus tracking
        self.last_focus_decision = 0
        self.focus_check_interval = 30.0  # Check focus every 30 seconds

        logger.info(f"CharacterAgent {name} created as {character_class}")

    async def make_decision(self):
        """Make decisions based on character focus and behaviors"""
        current_time = time.time()

        # Update focus periodically
        if current_time - self.last_focus_decision > self.focus_check_interval:
            focus = self.character.decide_focus()
            self.last_focus_decision = current_time
            logger.debug(f"{self.character.name} chose focus: {focus} for {self.character.focus_duration}s")

        # Make decisions based on current focus
        if self.character.current_focus == "exploration":
            await self._exploration_behavior()
        elif self.character.current_focus == "combat":
            await self._combat_behavior()
        else:
            # Fallback to exploration
            await self._exploration_behavior()

        # Update character focus duration
        self.character.focus_duration -= 1

    async def _exploration_behavior(self):
        """Handle exploration-focused behavior"""
        if self.state != "idle":
            return

        current_time = asyncio.get_event_loop().time()

        # Move randomly for exploration
        if random.random() < self.character.behaviors.exploration:
            target = Vector2(
                self.position.x + random.uniform(-200, 200),
                self.position.y + random.uniform(-200, 200)
            )

            self.action_queue.append({
                'type': 'move',
                'target': target
            })

            # Update behavior based on success (simplified)
            self.character.update_focus_progress("exploration", True)
            logger.debug(f"{self.character.name} exploring to {target}")

    async def _combat_behavior(self):
        """Handle combat-focused behavior"""
        # Look for enemies nearby
        nearby_entities = self.world_view.get_nearby_entities(self.position, 100)
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']

        if enemies and self.character.behaviors.combat > 0.5:
            # Move toward nearest enemy
            nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))

            if nearest_enemy.position.distance_to(self.position) > 30:
                # Move closer to enemy
                direction = (nearest_enemy.position - self.position).normalize()
                target = self.position + direction * 50

                self.action_queue.append({
                    'type': 'move',
                    'target': target
                })
                logger.debug(f"{self.character.name} moving toward enemy {nearest_enemy.name}")
            else:
                # Attack the enemy
                self.action_queue.append({
                    'type': 'attack',
                    'target_id': nearest_enemy.id
                })
                logger.info(f"{self.character.name} attacking {nearest_enemy.name}")

            # Update behavior based on engagement
            self.character.update_focus_progress("combat", True)
        else:
            # No enemies found, fall back to exploration
            await self._exploration_behavior()

    async def _handle_action_result(self, message):
        """Enhanced action result handling with character learning"""
        await super()._handle_action_result(message)

        # Update character behaviors based on action results
        if hasattr(message, 'action') and hasattr(message, 'success'):
            if message.action.value == 'MOVE':
                activity = self.character.current_focus or "exploration"
                self.character.update_focus_progress(activity, message.success)
            elif message.action.value == 'ATTACK':
                self.character.update_focus_progress("combat", message.success)


class WarriorAgent(CharacterAgent):
    """Warrior character agent that prefers combat"""

    def __init__(self, name: str):
        super().__init__(name, "warrior")

    async def make_decision(self):
        """Warrior-specific decision making"""
        # Warriors are more aggressive and less cautious
        if self.health < self.max_health * 0.3:  # Low health threshold
            # Even warriors retreat when very low on health
            await self._retreat_behavior()
        else:
            await super().make_decision()

    async def _retreat_behavior(self):
        """Retreat when health is critically low"""
        nearby_entities = self.world_view.get_nearby_entities(self.position, 100)
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']

        if enemies:
            # Run away from nearest enemy
            nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))
            escape_direction = (self.position - nearest_enemy.position).normalize()
            escape_target = self.position + escape_direction * 150

            self.action_queue.append({
                'type': 'move',
                'target': escape_target
            })
            logger.info(f"Warrior {self.character.name} retreating with low health")


class MageAgent(CharacterAgent):
    """Mage character agent that prefers exploration and is more cautious"""

    def __init__(self, name: str):
        super().__init__(name, "mage")

    async def make_decision(self):
        """Mage-specific decision making"""
        # Mages are more cautious
        if self.health < self.max_health * 0.6:  # Higher retreat threshold
            await self._cautious_behavior()
        else:
            await super().make_decision()

    async def _cautious_behavior(self):
        """More cautious behavior for mages"""
        nearby_entities = self.world_view.get_nearby_entities(self.position, 120)  # Longer detection range
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']

        if enemies:
            # Keep distance from enemies
            nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))
            if nearest_enemy.position.distance_to(self.position) < 80:
                # Move away but not necessarily run
                escape_direction = (self.position - nearest_enemy.position).normalize()
                escape_target = self.position + escape_direction * 100

                self.action_queue.append({
                    'type': 'move',
                    'target': escape_target
                })
                logger.debug(f"Mage {self.character.name} maintaining distance from {nearest_enemy.name}")
            else:
                # Safe distance, continue with normal behavior
                await super().make_decision()
        else:
            # No threats, explore freely
            await self._exploration_behavior()

    async def _combat_behavior(self):
        """Mage combat behavior - ranged and strategic"""
        nearby_entities = self.world_view.get_nearby_entities(self.position, 120)  # Longer range
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']

        if enemies and self.character.behaviors.combat > 0.3:  # Lower combat threshold
            nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))
            distance = nearest_enemy.position.distance_to(self.position)

            if distance > 100:
                # Too far for magic, move closer
                direction = (nearest_enemy.position - self.position).normalize()
                target = self.position + direction * 30

                self.action_queue.append({
                    'type': 'move',
                    'target': target
                })
                logger.debug(f"Mage {self.character.name} positioning for spell range")
            elif distance > 50:
                # Good range for magic attack
                self.action_queue.append({
                    'type': 'attack',
                    'target_id': nearest_enemy.id
                })
                logger.info(f"Mage {self.character.name} casting spell at {nearest_enemy.name}")
            else:
                # Too close, back away
                escape_direction = (self.position - nearest_enemy.position).normalize()
                escape_target = self.position + escape_direction * 60

                self.action_queue.append({
                    'type': 'move',
                    'target': escape_target
                })
                logger.debug(f"Mage {self.character.name} backing away from {nearest_enemy.name}")

            self.character.update_focus_progress("combat", True)
        else:
            # No suitable combat targets, explore instead
            await self._exploration_behavior()