import logging
import math
import random
import time
from typing import Any, Dict, List, Optional

from client.agent import BaseAgent
from client.behavior_tree.tree_configs import TreeFactory

logger = logging.getLogger(__name__)


class EnemyAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "enemy")

        # Enemy configuration
        self.attack_range = 2.0
        self.chase_range = 15.0
        self.attack_cooldown = 1.0
        self.last_attack_time = 0
        self.aggression_level = random.uniform(0.5, 1.0)

        # Initialize behavior tree
        self._initialize_behavior_tree()

    def _initialize_behavior_tree(self):
        """Initialize the behavior tree for this Enemy agent"""
        tree = TreeFactory.create_tree_for_agent_type(
            "enemy", self.x, self.y, patrol_radius=10.0
        )
        if tree:
            self.set_behavior_tree(tree)
            logger.info(f"Enemy {self.id[:8]} initialized with behavior tree")
        else:
            raise Exception(f"Failed to create behavior tree for Enemy {self.id[:8]}")

    def update(self, delta_time: float):
        # Use behavior tree system
        self.update_behavior_tree(delta_time)

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        """Update visible entities for behavior tree conditions"""
        self.visible_entities = visible_entities

    def decide(self) -> Optional[Dict[str, Any]]:
        """Decision making is now handled by the behavior tree"""
        return None
