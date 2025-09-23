import logging
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario
from world.terrain_generator import TerrainType

logger = logging.getLogger(__name__)


class SimpleDuelScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Simple Duel",
            description="Two agents in close combat for testing behavior trees",
            terrain_type=TerrainType.GRASSLAND,  # Simple arena for dueling
            seed=500,  # Consistent duel arena
        )

    async def setup(self, server):
        """Setup duel arena"""
        self.server = server
        logger.info("=" * 60)
        logger.info("Setting up Simple Duel scenario")
        logger.info("Two agents will spawn close to each other and engage in combat")
        logger.info("=" * 60)

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn just 2 combat agents"""
        agent_configs = []

        # Spawn first combatant (Player)
        x1, y1 = 45, 50
        agent_config1 = {"type": "player", "position": (x1, y1), "name": "Fighter_1"}
        agent_configs.append(agent_config1)

        agent_id1 = self.server.world.spawn_agent("player", x1, y1)
        logger.info(f"Spawned Player fighter {agent_id1[:8]} at ({x1}, {y1})")

        # Spawn second combatant (Enemy) - close enough to engage
        x2, y2 = 55, 50  # 10 units apart
        agent_config2 = {"type": "enemy", "position": (x2, y2), "name": "Fighter_2"}
        agent_configs.append(agent_config2)

        agent_id2 = self.server.world.spawn_agent("enemy", x2, y2)
        logger.info(f"Spawned Enemy fighter {agent_id2[:8]} at ({x2}, {y2})")

        logger.info(f"Distance between fighters: 10 units")
        logger.info("Expected behavior:")
        logger.info("  - Both should detect each other (within vision range)")
        logger.info("  - Both should approach to attack range")
        logger.info("  - Both should attack when in range")

        return agent_configs
