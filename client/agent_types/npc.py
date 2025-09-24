import logging
from typing import Any, Dict, List, Optional

from client.agent import BaseAgent
from client.behavior_tree.tree_configs import TreeFactory

logger = logging.getLogger(__name__)


class NPCAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "npc")

        # NPC configuration
        self.wander_radius = 15.0
        self.home_x = x
        self.home_y = y

        # Don't initialize behavior tree yet - wait for provider injection
        self.behavior_tree_initialized = False

    def _initialize_behavior_tree(self):
        """Initialize the behavior tree for this NPC agent"""
        # Try provider-based initialization first
        if self.behavior_tree_provider:
            success = self.initialize_behavior_tree_from_provider(
                wander_radius=self.wander_radius
            )
            if success:
                logger.info(f"NPC {self.id[:8]} initialized with custom scenario behavior tree")
                self.behavior_tree_initialized = True
                return
            else:
                logger.warning(f"NPC {self.id[:8]} provider failed, falling back to TreeFactory")

        # Fallback to TreeFactory
        tree = TreeFactory.create_tree_for_agent_type(
            "npc", self.home_x, self.home_y, wander_radius=self.wander_radius
        )
        if tree:
            self.set_behavior_tree(tree)
            logger.info(f"NPC {self.id[:8]} initialized with TreeFactory behavior tree")
            self.behavior_tree_initialized = True
        else:
            raise Exception(f"Failed to create behavior tree for NPC {self.id[:8]}")

    def update(self, delta_time: float):
        # Use behavior tree system
        self.update_behavior_tree(delta_time)

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        """Update visible entities for behavior tree conditions"""
        self.visible_entities = visible_entities

    def decide(self) -> Optional[Dict[str, Any]]:
        """Decision making is now handled by the behavior tree"""
        return None
