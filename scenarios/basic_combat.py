import logging
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario

logger = logging.getLogger(__name__)


class BasicCombatScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Basic Combat", description="Players vs enemies in a combat arena"
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

        # Spawn players on one side (close formation for guaranteed combat)
        player_positions = [(40, 45), (42, 52)]  # Close together
        for i in range(self.num_players):
            x, y = player_positions[i]

            agent_config = {
                "type": "player",
                "position": (x, y),
                "name": f"Player_{i+1}",
            }
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("player", x, y)
            logger.info(f"Spawned player {agent_id} at ({x}, {y})")

        # Spawn enemies on other side (very close for guaranteed combat)
        enemy_positions = [
            (52, 47),
            (54, 45),
            (50, 50),
            (56, 52),
        ]  # Very close formation
        for i in range(self.num_enemies):
            x, y = enemy_positions[i]

            agent_config = {"type": "enemy", "position": (x, y), "name": f"Enemy_{i+1}"}
            agent_configs.append(agent_config)

            agent_id = self.server.world.spawn_agent("enemy", x, y)
            logger.info(f"Spawned enemy {agent_id} at ({x}, {y})")

        logger.info("Combat arena setup:")
        logger.info(
            f"  Players: {self.num_players} agents in tight formation (40-42, 45-52)"
        )
        logger.info(
            f"  Enemies: {self.num_enemies} agents in tight formation (50-56, 45-52)"
        )
        logger.info(
            f"  Distance between sides: ~8-16 units (guaranteed detection and combat)"
        )
        logger.info(
            "  Expected behavior: Immediate multi-agent combat with damage/death/respawn"
        )

        return agent_configs
