import logging
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario

logger = logging.getLogger(__name__)


class PathfindingDemoScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Pathfinding Demo",
            description="Demonstrates pathfinding capabilities with predetermined waypoints",
        )
        self.test_waypoints = [
            (10, 10),  # Start point
            (90, 10),  # Go to top right
            (90, 90),  # Go to bottom right
            (10, 90),  # Go to bottom left
            (50, 50),  # Go to center
            (10, 10),  # Return to start
        ]
        self.current_waypoint_index = 0

    async def setup(self, server):
        """Setup the pathfinding test scenario"""
        self.server = server
        logger.info("Setting up pathfinding test scenario")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn a single test agent for pathfinding"""
        agent_configs = []

        # Spawn a single test agent at the first waypoint
        start_x, start_y = self.test_waypoints[0]

        agent_config = {
            "type": "pathfinding_test",
            "position": (start_x, start_y),
            "name": "PathfindingTestAgent",
            "test_waypoints": self.test_waypoints,
        }
        agent_configs.append(agent_config)

        # Spawn pathfinding test agent
        agent_id = self.server.world.spawn_agent("pathfinding_test", start_x, start_y)
        logger.info(
            f"Spawned pathfinding test agent {agent_id} at ({start_x}, {start_y})"
        )
        logger.info(f"Agent will visit waypoints: {self.test_waypoints}")

        return agent_configs
