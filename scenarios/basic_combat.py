from scenarios.base_scenario import BaseScenario
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class BasicCombatScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Basic Combat",
            description="Players vs enemies in a combat arena"
        )
        self.num_players = 2
        self.num_enemies = 4

    async def setup(self, server):
        """Setup combat arena"""
        self.server = server
        logger.info("Setting up basic combat scenario")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn combat agents"""
        agent_configs = []

        # Spawn players on one side
        for i in range(self.num_players):
            x = 20 + i * 10
            y = 50

            agent_config = {
                'type': 'player',
                'position': (x, y),
                'name': f"Player_{i+1}"
            }
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("player", x, y)
            logger.info(f"Spawned player {agent_id} at ({x}, {y})")

        # Spawn enemies on other side
        for i in range(self.num_enemies):
            x = 80 - i * 5
            y = 50 + (i - 2) * 10

            agent_config = {
                'type': 'enemy',
                'position': (x, y),
                'name': f"Enemy_{i+1}"
            }
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("enemy", x, y)
            logger.info(f"Spawned enemy {agent_id} at ({x}, {y})")

        return agent_configs