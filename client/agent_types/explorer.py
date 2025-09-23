import logging
import math
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from client.agent import BaseAgent
from client.behavior_tree.tree_configs import TreeFactory

logger = logging.getLogger(__name__)


class ExplorerAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "explorer")

        # Explorer configuration
        self.explored_tiles: Set[Tuple[int, int]] = set()
        self.exploration_radius = 30.0
        self.exploration_mode = "spiral"  # Can be "spiral", "random", "frontier"
        self.home_base = (x, y)
        self.exploration_history = []
        self.max_history = 100

        # Initialize behavior tree
        self._initialize_behavior_tree()

    def _initialize_behavior_tree(self):
        """Initialize the behavior tree for this Explorer agent"""
        tree = TreeFactory.create_tree_for_agent_type(
            "explorer",
            self.home_base[0],
            self.home_base[1],
            exploration_radius=self.exploration_radius,
            exploration_mode=self.exploration_mode,
        )
        if tree:
            self.set_behavior_tree(tree)
            logger.info(f"Explorer {self.id[:8]} initialized with behavior tree")
        else:
            raise Exception(
                f"Failed to create behavior tree for Explorer {self.id[:8]}"
            )

    def update(self, delta_time: float):
        # Use behavior tree system
        self.update_behavior_tree(delta_time)

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        """Update visible entities and record exploration progress"""
        self.visible_entities = visible_entities

        # Record visible tiles as explored
        for entity in visible_entities:
            tile_x = int(entity.get("x", 0))
            tile_y = int(entity.get("y", 0))
            self.explored_tiles.add((tile_x, tile_y))

    def decide(self) -> Optional[Dict[str, Any]]:
        """Decision making is now handled by the behavior tree"""
        # Report exploration progress periodically
        if len(self.explored_tiles) > 0 and len(self.explored_tiles) % 10 == 0:
            return {
                "type": "exploration_report",
                "explored_count": len(self.explored_tiles),
                "current_mode": self.exploration_mode,
                "position": (self.x, self.y),
            }
        return None

    def get_exploration_stats(self) -> Dict[str, Any]:
        """Get exploration statistics"""
        return {
            "tiles_explored": len(self.explored_tiles),
            "exploration_mode": self.exploration_mode,
            "coverage_percentage": (
                len(self.explored_tiles) / (math.pi * self.exploration_radius**2)
            )
            * 100,
        }
