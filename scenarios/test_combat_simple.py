"""
Simple Combat Test Scenario

A minimal test scenario to verify combat mechanics work correctly.
- Small 20x20 map
- Two personality agents spawn 3 units apart (within attack range)
- Warrior personality vs Enemy personality
- Simple behavior: detect enemy -> attack -> verify damage
"""

import logging
from typing import Any, Dict, List, Optional

from client.agent_types.personality_agent import PersonalityAgent
from scenarios.base_scenario import BaseScenario
from shared.personality import PersonalityArchetype

logger = logging.getLogger(__name__)


class CombatSimpleScenario(BaseScenario):
    def __init__(self):
        from world.terrain_generator import TerrainType

        super().__init__(
            name="Test Combat Simple",
            description="Minimal combat test with agents spawning in attack range",
            terrain_type=TerrainType.GRASSLAND,  # Simple flat terrain
        )
        self.world_size = (20, 20)

    async def setup(self, server):
        """Setup the test scenario"""
        logger.info("Setting up simple combat test scenario with personality agents")

        agent_configs = []

        # Create warrior personality (high combat, low exploration)
        warrior_personality = PersonalityArchetype.warrior()

        # Spawn warrior at (10, 10)
        warrior_id = server.world.spawn_agent(
            agent_type="player",  # Still use legacy type for server compatibility
            x=10,
            y=10,
            rotation=0,
        )

        # Register the warrior agent with personality
        warrior_agent = server.world.get_agent(warrior_id)
        if warrior_agent:
            server.agent_registry.register_agent(
                warrior_id, "player", warrior_agent.x, warrior_agent.y
            )
            server.ai_system.register_agent(
                warrior_id, "player", warrior_agent.x, warrior_agent.y
            )

        agent_configs.append(
            {
                "id": warrior_id,
                "type": "player",
                "personality": warrior_personality,
                "archetype": "warrior",
                "behavior": "personality_driven",
            }
        )

        # Create aggressive enemy personality (very high combat, low cooperativeness)
        enemy_personality = PersonalityArchetype.warrior()
        # Make enemy more aggressive and less cooperative than warrior
        enemy_personality.combat = 10.0
        enemy_personality.risk_tolerance = 9.0
        enemy_personality.cooperativeness = 1.0
        enemy_personality.social = 0.0

        # Spawn enemy at (10, 13) - exactly 3 units away
        enemy_id = server.world.spawn_agent(
            agent_type="enemy", x=10, y=13, rotation=180
        )

        # Register the enemy agent with personality
        enemy_agent = server.world.get_agent(enemy_id)
        if enemy_agent:
            server.agent_registry.register_agent(
                enemy_id, "enemy", enemy_agent.x, enemy_agent.y
            )
            server.ai_system.register_agent(
                enemy_id, "enemy", enemy_agent.x, enemy_agent.y
            )

        agent_configs.append(
            {
                "id": enemy_id,
                "type": "enemy",
                "personality": enemy_personality,
                "archetype": "aggressive_enemy",
                "behavior": "personality_driven",
            }
        )

        logger.info(f"Simple combat test scenario setup complete:")
        logger.info(f"  Warrior (combat:{warrior_personality.combat:.1f}) at (10, 10)")
        logger.info(
            f"  Aggressive Enemy (combat:{enemy_personality.combat:.1f}) at (10, 13)"
        )
        logger.info(f"  Distance: 3 units apart (within attack range)")
        logger.info(f"  Expected behavior: Immediate combat engagement")

        # Log initial health
        warrior = server.world.get_agent(warrior_id)
        enemy = server.world.get_agent(enemy_id)
        if warrior and enemy:
            logger.info(f"  Warrior health: {warrior.health}/{warrior.max_health}")
            logger.info(f"  Enemy health: {enemy.health}/{enemy.max_health}")

        return agent_configs

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Implementation of abstract method - agents already spawned in setup"""
        return []

    def get_custom_behavior_tree(
        self, agent_type: str, agent_x: float, agent_y: float
    ) -> Optional[Any]:
        """
        Personality agents use the personality tree builder instead of custom trees.
        This method returns None to indicate they should use their built-in personality-driven behavior.
        """
        return None
