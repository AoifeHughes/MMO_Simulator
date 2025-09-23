import logging
import math
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario

logger = logging.getLogger(__name__)


class PeacefulVillageScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Peaceful Village",
            description="A peaceful village with NPCs wandering around",
        )
        self.num_npcs = 10
        self.num_explorers = 2

    async def setup(self, server):
        """Setup village scenario"""
        self.server = server
        logger.info("Setting up peaceful village scenario")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn village NPCs in circular pattern"""
        agent_configs = []

        # Create village center
        village_center_x = 50
        village_center_y = 50
        village_radius = 20

        # Spawn NPCs in circular pattern around village
        for i in range(self.num_npcs):
            angle = (2 * math.pi / self.num_npcs) * i
            x = village_center_x + math.cos(angle) * village_radius
            y = village_center_y + math.sin(angle) * village_radius

            agent_config = {
                "type": "npc",
                "position": (x, y),
                "name": f"Villager_{i+1}",
            }
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("npc", x, y)
            logger.info(f"Spawned villager {agent_id} at ({x:.1f}, {y:.1f})")

        # Add explorers to visit the village
        for i in range(self.num_explorers):
            x = village_center_x + (i - 0.5) * 30
            y = village_center_y

            agent_config = {
                "type": "explorer",
                "position": (x, y),
                "exploration_mode": "random",
                "name": f"Visitor_{i+1}",
            }
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("explorer", x, y)
            logger.info(f"Spawned visitor {agent_id} at ({x:.1f}, {y:.1f})")

        return agent_configs
