import logging
import random
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario

logger = logging.getLogger(__name__)


class ExplorationDemoScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Exploration Demo",
            description="Demonstrates explorer agents mapping the world using different strategies",
        )
        self.num_explorers = 5
        self.num_npcs = 3
        self.num_enemies = 2

    async def setup(self, server):
        """Setup the exploration scenario"""
        self.server = server
        logger.info(
            f"Setting up exploration scenario with {self.num_explorers} explorers"
        )

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn explorer agents with different strategies"""
        agent_configs = []

        # Spawn explorers with different exploration modes
        exploration_modes = ["spiral", "random", "frontier", "spiral", "random"]
        for i in range(self.num_explorers):
            # Spread explorers across the map
            x = random.uniform(20, 80)
            y = random.uniform(20, 80)

            agent_config = {
                "type": "explorer",
                "position": (x, y),
                "exploration_mode": exploration_modes[i % len(exploration_modes)],
                "name": f"Explorer_{i+1}",
            }
            agent_configs.append(agent_config)

            # Spawn on server
            agent_id = self.server.world.spawn_agent("explorer", x, y)
            logger.info(
                f"Spawned explorer {agent_id} at ({x:.1f}, {y:.1f}) with {exploration_modes[i]} mode"
            )

        # Add some NPCs for variety
        for i in range(self.num_npcs):
            x = random.uniform(10, 90)
            y = random.uniform(10, 90)

            agent_config = {"type": "npc", "position": (x, y), "name": f"NPC_{i+1}"}
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("npc", x, y)
            logger.info(f"Spawned NPC {agent_id} at ({x:.1f}, {y:.1f})")

        # Add some enemies
        for i in range(self.num_enemies):
            x = random.uniform(10, 90)
            y = random.uniform(10, 90)

            agent_config = {"type": "enemy", "position": (x, y), "name": f"Enemy_{i+1}"}
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("enemy", x, y)
            logger.info(f"Spawned enemy {agent_id} at ({x:.1f}, {y:.1f})")

        logger.info(f"Total agents spawned: {len(agent_configs)}")
        return agent_configs
