"""
Dynamic Condition Nodes

These nodes use server-provided game data to make decisions rather than hardcoded values.
This eliminates the need for data duplication and ensures consistency with server logic.
"""

import logging
import math
import time
from typing import Any, Dict, List, Optional

from .base import ConditionNode

logger = logging.getLogger(__name__)


class DynamicEnemyInRange(ConditionNode):
    """Check if any enemy is within range using server-provided attack data"""

    def __init__(self, attack_name: str, enemy_types: List[str] = None):
        super().__init__(f"DynamicEnemyInRange_{attack_name}")
        self.attack_name = attack_name
        self.enemy_types = enemy_types or ["enemy", "player"]  # Default enemy types
        self.detected_enemy: Optional[Dict[str, Any]] = None

    def check_condition(self, agent) -> bool:
        self.detected_enemy = None

        # Get attack range from server data
        attack_data = agent.get_attack_data(self.attack_name)
        if not attack_data:
            logger.warning(f"[DYNAMIC] Agent {agent.id[:8]} has no server data for attack '{self.attack_name}'")
            return False

        attack_range = attack_data.get('max_range', 1.0)

        visible_entities = getattr(agent, "visible_entities", [])
        visible_count = len(visible_entities)

        # Always log visibility info for debugging
        logger.debug(
            f"[DYNAMIC] Agent {agent.id[:8]} ({agent.agent_type}) checking {self.attack_name} range {attack_range:.1f} with {visible_count} visible entities"
        )

        if visible_count == 0:
            logger.debug(
                f"[DYNAMIC] Agent {agent.id[:8]} ({agent.agent_type}) cannot see ANY entities"
            )

        for entity in getattr(agent, "visible_entities", []):
            entity_type = entity.get("agent_type")
            entity_id = entity.get("id")

            # Debug logging to understand what we're seeing
            logger.debug(
                f"[DYNAMIC] Agent {agent.id[:8]} sees entity {entity_id[:8] if entity_id else 'unknown'} of type '{entity_type}'"
            )

            # Check if this is an enemy type we care about
            if entity_type in self.enemy_types and entity_id != agent.id:
                dx = entity["x"] - agent.x
                dy = entity["y"] - agent.y
                distance = math.sqrt(dx * dx + dy * dy)

                logger.debug(
                    f"[DYNAMIC] Agent {agent.id[:8]} sees {entity_type} at distance {distance:.1f} (attack range: {attack_range:.1f})"
                )

                if distance <= attack_range:
                    self.detected_enemy = entity
                    logger.info(
                        f"[DYNAMIC] Agent {agent.id[:8]} ({agent.agent_type}) can attack {entity_type} {entity_id[:8]} with {self.attack_name} at {distance:.1f} units!"
                    )
                    return True

        return False

    def get_detected_enemy(self) -> Optional[Dict[str, Any]]:
        """Get the last detected enemy for use in actions"""
        return self.detected_enemy


class DynamicEnemyInChaseRange(ConditionNode):
    """Check if any enemy is within chase range (typically larger than attack range)"""

    def __init__(self, chase_range: float, enemy_types: List[str] = None):
        super().__init__(f"DynamicEnemyInChaseRange_{chase_range}")
        self.chase_range = chase_range
        self.enemy_types = enemy_types or ["enemy", "player"]
        self.detected_enemy: Optional[Dict[str, Any]] = None

    def check_condition(self, agent) -> bool:
        self.detected_enemy = None

        visible_entities = getattr(agent, "visible_entities", [])

        for entity in visible_entities:
            entity_type = entity.get("agent_type")
            entity_id = entity.get("id")

            if entity_type in self.enemy_types and entity_id != agent.id:
                dx = entity["x"] - agent.x
                dy = entity["y"] - agent.y
                distance = math.sqrt(dx * dx + dy * dy)

                if distance <= self.chase_range:
                    self.detected_enemy = entity
                    logger.debug(
                        f"[DYNAMIC] Agent {agent.id[:8]} can chase {entity_type} {entity_id[:8]} at {distance:.1f} units!"
                    )
                    return True

        return False

    def get_detected_enemy(self) -> Optional[Dict[str, Any]]:
        """Get the last detected enemy for use in actions"""
        return self.detected_enemy


class HasServerGameData(ConditionNode):
    """Check if agent has received server game data"""

    def __init__(self):
        super().__init__("HasServerGameData")

    def check_condition(self, agent) -> bool:
        has_data = (
            hasattr(agent, 'server_game_data') and
            agent.server_game_data is not None and
            'attacks' in agent.server_game_data
        )

        if not has_data:
            logger.warning(f"[DYNAMIC] Agent {agent.id[:8]} has no server game data - using fallback behavior")

        return has_data