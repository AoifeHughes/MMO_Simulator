import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from client.agent import BaseAgent
from client.behavior_tree.tree_configs import TreeFactory

logger = logging.getLogger(__name__)


class ExplorerAgent(BaseAgent):
    """
    Autonomous exploration agent with intelligent world discovery capabilities.

    ExplorerAgents are designed to autonomously discover and map game worlds
    through various exploration strategies. They feature:

    Exploration Modes:
    - "spiral": Systematic outward spiral exploration from home base
    - "random": Randomized exploration with bias toward unexplored areas
    - "frontier": Edge-based exploration prioritizing unknown boundaries
    - "fishing": Resource-focused exploration seeking water bodies

    Key Features:
    - Adaptive behavior trees based on exploration mode
    - Tile-based exploration tracking and mapping
    - Intelligent pathfinding around obstacles
    - Resource discovery and interaction
    - Home base navigation and memory

    The agent maintains exploration history and can dynamically switch
    between exploration strategies based on environmental conditions.
    """
    def __init__(self, agent_id: str, x: float, y: float):
        super().__init__(agent_id, x, y, "explorer")

        # Explorer configuration
        self.explored_tiles: Set[Tuple[int, int]] = set()
        self.exploration_radius = 30.0
        self.exploration_mode = "spiral"  # Can be "spiral", "random", "frontier", "fishing"
        self.home_base = (x, y)
        self.exploration_history = []
        self.max_history = 100

        # Don't initialize behavior tree yet - wait for exploration mode to be set
        self.behavior_tree_initialized = False

    def set_exploration_mode(self, mode: str):
        """Set exploration mode and reinitialize behavior tree if needed"""
        if mode != self.exploration_mode:
            self.exploration_mode = mode
            if not self.behavior_tree_initialized:
                self._initialize_behavior_tree()

    def _initialize_behavior_tree(self):
        """
        Initialize the behavior tree for this Explorer agent.

        Uses a two-phase initialization strategy:
        1. Provider-based: Attempts to use custom behavior tree provider
           if available, allowing for dynamic behavior customization
        2. Factory fallback: Uses TreeFactory with standard exploration
           patterns if provider fails or is unavailable

        The initialization process adapts based on exploration_mode:
        - "fishing": Creates specialized resource-seeking behavior trees
        - Other modes: Creates standard exploration behavior trees

        Sets behavior_tree_initialized=True on success, enabling the
        agent to begin autonomous operation.
        """
        # Try provider-based initialization first
        if self.behavior_tree_provider:
            success = self.initialize_behavior_tree_from_provider(
                exploration_radius=self.exploration_radius,
                exploration_mode=self.exploration_mode,
            )
            if success:
                tree_type = "custom" if self.exploration_mode == "fishing" else "provider"
                logger.info(f"Explorer {self.id[:8]} initialized with {tree_type} provider behavior tree")
                self.behavior_tree_initialized = True
                return
            else:
                logger.warning(f"Explorer {self.id[:8]} provider failed, falling back to TreeFactory")

        # Fallback to TreeFactory
        tree = TreeFactory.create_tree_for_agent_type(
            "explorer",
            self.home_base[0],
            self.home_base[1],
            exploration_radius=self.exploration_radius,
            exploration_mode=self.exploration_mode,
        )
        if tree:
            self.set_behavior_tree(tree)
            tree_type = "fishing" if self.exploration_mode == "fishing" else "standard"
            logger.info(f"Explorer {self.id[:8]} initialized with {tree_type} TreeFactory behavior tree")
            self.behavior_tree_initialized = True
        else:
            raise Exception(
                f"Failed to create behavior tree for Explorer {self.id[:8]}"
            )

    def receive_server_data(self, server_data: Dict[str, Any]):
        """Receive server data and check for special exploration modes"""
        super().receive_server_data(server_data)

        # Check if server data contains exploration mode
        if 'exploration_mode' in server_data:
            self.exploration_mode = server_data['exploration_mode']
            logger.info(f"Explorer {self.id[:8]} using exploration mode: {self.exploration_mode}")

        # Also check for specialization which might indicate behavior mode
        if 'specialization' in server_data:
            specialization = server_data['specialization']
            if specialization == "wood_harvesting" and self.exploration_mode == "frontier":
                self.exploration_mode = "wood_harvesting"
                logger.info(f"Explorer {self.id[:8]} switching to wood_harvesting mode based on specialization")
            elif specialization == "fishing" and self.exploration_mode == "frontier":
                self.exploration_mode = "fishing"
                logger.info(f"Explorer {self.id[:8]} switching to fishing mode based on specialization")

        # Initialize behavior tree now that we have server data
        if not self.behavior_tree_initialized:
            self._initialize_behavior_tree()

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
