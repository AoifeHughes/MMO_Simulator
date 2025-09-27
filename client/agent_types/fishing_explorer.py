import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from client.agent import BaseAgent
from client.behavior_tree.tree_configs import TreeFactory

logger = logging.getLogger(__name__)


class FishingExplorerAgent(BaseAgent):
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "explorer")

        # Explorer configuration
        self.explored_tiles: Set[Tuple[int, int]] = set()
        self.exploration_radius = 40.0  # Larger radius to find water
        self.exploration_mode = "fishing"  # Special fishing mode
        self.home_base = (x, y)
        self.exploration_history = []
        self.max_history = 100

        # Fishing-specific configuration
        self.water_tiles_found: Set[Tuple[int, int]] = set()
        self.fishing_attempts = 0

        # Initialize behavior tree with fishing mode
        self._initialize_behavior_tree()

    def _initialize_behavior_tree(self):
        """Initialize the behavior tree for this Fishing Explorer agent"""
        # Try provider-based initialization first
        if self.behavior_tree_provider:
            success = self.initialize_behavior_tree_from_provider(
                exploration_radius=self.exploration_radius,
                exploration_mode=self.exploration_mode,
            )
            if success:
                logger.info(
                    f"Fishing Explorer {self.id[:8]} initialized with custom scenario behavior tree"
                )
                return
            else:
                logger.warning(
                    f"Fishing Explorer {self.id[:8]} provider failed, falling back to TreeFactory"
                )

        # Fallback to TreeFactory
        tree = TreeFactory.create_tree_for_agent_type(
            "explorer",
            self.home_base[0],
            self.home_base[1],
            exploration_radius=self.exploration_radius,
            exploration_mode=self.exploration_mode,  # This will trigger fishing behavior
        )
        if tree:
            self.set_behavior_tree(tree)
            logger.info(
                f"Fishing Explorer {self.id[:8]} initialized with TreeFactory fishing behavior tree"
            )
        else:
            raise Exception(
                f"Failed to create fishing behavior tree for Explorer {self.id[:8]}"
            )

    def update(self, delta_time: float):
        # Use behavior tree system
        self.update_behavior_tree(delta_time)

    def perceive(self, visible_entities: List[Dict[str, Any]]):
        """Update visible entities and record exploration progress"""
        self.visible_entities = visible_entities

        # Track water discovery for fishing behavior
        if hasattr(self, "agent_map") and self.agent_map:
            # Check recently explored areas for water
            agent_x, agent_y = int(self.x), int(self.y)
            for dy in range(-5, 6):
                for dx in range(-5, 6):
                    check_x, check_y = agent_x + dx, agent_y + dy
                    if self.agent_map.is_explored(check_x, check_y):
                        tile_type = self.agent_map.get_tile_type(check_x, check_y)
                        if hasattr(tile_type, "name") and tile_type.name == "WATER":
                            self.water_tiles_found.add((check_x, check_y))
                            if len(self.water_tiles_found) == 1:  # First water found
                                logger.info(
                                    f"Fishing Explorer {self.id[:8]} discovered water at ({check_x}, {check_y})!"
                                )

        # Call parent perceive method
        super().perceive(visible_entities)
