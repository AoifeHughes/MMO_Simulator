import logging
import math
from typing import Any, Dict, List, Optional

from client.agent_types.personality_agent import PersonalityAgent
from scenarios.base_scenario import BaseScenario
from world.terrain_generator import TerrainType
from shared.items import create_item
from shared.personality import PersonalityArchetype, create_personality_variant

logger = logging.getLogger(__name__)


class DualWeaponCombatScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Dual Weapon Combat",
            description="Tactical warriors with personality-driven weapon selection vs aggressive enemies",
            terrain_type=TerrainType.GRASSLAND,  # Open terrain for clear combat
            seed=150,  # Consistent arena layout
        )
        self.num_warriors = 2
        self.num_enemies = 4

    async def setup(self, server):
        """Setup dual weapon combat scenario"""
        self.server = server
        logger.info("Setting up dual weapon combat scenario")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn tactical warriors and aggressive enemies with personalities"""
        agent_configs = []

        # Create tactical warrior personality (high combat + moderate strategy)
        # These warriors should use ranged weapons when possible
        tactical_warrior_base = PersonalityArchetype.warrior()
        tactical_warrior = create_personality_variant(tactical_warrior_base, {
            'combat': 8.0,
            'exploration': 4.0,  # Tactical positioning
            'risk_tolerance': 6.0,  # Calculated risks
            'patience': 7.0,  # Good at waiting for right moment
        })

        # Spawn warriors on one side (they get dual weapons)
        warrior_positions = [(40, 45), (42, 52)]
        for i in range(self.num_warriors):
            x, y = warrior_positions[i]
            rotation = 0.0  # Facing east toward enemies

            agent_config = {
                "type": "player",
                "position": (x, y),
                "name": f"TacticalWarrior_{i+1}",
                "personality": tactical_warrior,
                "archetype": "tactical_warrior",
                "behavior": "personality_driven"
            }
            agent_configs.append(agent_config)

            # Spawn warrior on server
            agent_id = self.server.world.spawn_agent("player", x, y, rotation)

            # Register agent and customize inventory
            agent_state = self.server.agent_registry.register_agent(agent_id, "player", x, y)

            # Give warrior both sword and bow (they start with sword, add bow)
            sword = create_item("iron_sword")
            if sword:
                agent_state.inventory.add_item(sword, 1)
                agent_state.inventory.equip_item(sword.item_id)

            bow = create_item("hunters_bow")
            if bow:
                agent_state.inventory.add_item(bow, 1)

            logger.info(f"Spawned tactical warrior {agent_id} at ({x}, {y}) with sword and bow")
            logger.info(f"Warrior weapons: {[item.name for item in agent_state.inventory.get_weapons()]}")

        # Create aggressive enemy personality (very high combat, reckless)
        aggressive_enemy = create_personality_variant(PersonalityArchetype.warrior(), {
            'combat': 10.0,
            'risk_tolerance': 9.0,
            'cooperativeness': 2.0,
            'patience': 3.0,  # Rush into combat
            'social': 0.0,
        })

        # Spawn enemies on the other side
        enemy_positions = [
            (52, 47),
            (54, 45),
            (50, 50),
            (56, 52),
        ]
        for i in range(self.num_enemies):
            x, y = enemy_positions[i]
            rotation = 180.0  # Facing west toward warriors

            agent_config = {
                "type": "enemy",
                "position": (x, y),
                "name": f"AggressiveEnemy_{i+1}",
                "personality": aggressive_enemy,
                "archetype": "aggressive_enemy",
                "behavior": "personality_driven"
            }
            agent_configs.append(agent_config)

            # Spawn enemy on server
            agent_id = self.server.world.spawn_agent("enemy", x, y, rotation)
            agent_state = self.server.agent_registry.register_agent(agent_id, "enemy", x, y)

            logger.info(f"Spawned aggressive enemy {agent_id} at ({x}, {y})")

        logger.info("Dual weapon combat scenario setup:")
        logger.info(f"  Tactical Warriors: {self.num_warriors} agents (combat:{tactical_warrior.combat:.1f}, patience:{tactical_warrior.patience:.1f}) with sword + bow")
        logger.info(f"  Aggressive Enemies: {self.num_enemies} agents (combat:{aggressive_enemy.combat:.1f}, patience:{aggressive_enemy.patience:.1f}) with claws")
        logger.info(f"  Distance: ~8-16 units between sides")
        logger.info("  Expected behavior: Warriors use personality-driven weapon selection, enemies rush aggressively")

        return agent_configs

    def get_custom_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float) -> Optional[Any]:
        """
        Personality agents use the personality tree builder for weapon selection behavior.
        This method returns None to indicate they should use their built-in personality-driven behavior.
        """
        return None