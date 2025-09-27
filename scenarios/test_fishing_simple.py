"""
Simple Fishing Test Scenario

A minimal test scenario to verify fishing mechanics work correctly.
- Small 20x20 map with guaranteed water
- Fisher personality agent spawns right next to water (2 units away)
- Simple behavior: move to water -> fish -> check inventory
"""

import logging
from typing import Any, Dict, List, Optional

from client.agent_types.personality_agent import PersonalityAgent
from scenarios.base_scenario import BaseScenario
from shared.inventory import Inventory
from shared.items import FishingRod, ItemType
from shared.personality import PersonalityArchetype

logger = logging.getLogger(__name__)


class FishingSimpleScenario(BaseScenario):
    def __init__(self):
        from world.terrain_generator import TerrainType
        super().__init__(
            name="Test Fishing Simple",
            description="Minimal fishing test with agent spawning next to water",
            terrain_type=TerrainType.ARCHIPELAGO,  # Guaranteed water
        )
        self.world_size = (20, 20)

    async def setup(self, server):
        """Setup the test scenario"""
        logger.info("Setting up simple fishing test scenario with personality agent")

        # Create fisher personality (high fishing, moderate exploration, patient)
        fisher_personality = PersonalityArchetype.fisher()

        # Create a single fisher at position (10, 8)
        # Water will be at approximately (10, 10) with lakes terrain
        agent_configs = []

        fisher_id = server.world.spawn_agent(
            agent_type="explorer",  # Use explorer for server compatibility
            x=10,
            y=8,  # Just 2 units from expected water
            rotation=90  # Facing down toward water
        )

        # Register the agent in the registry
        agent = server.world.get_agent(fisher_id)
        if agent:
            server.agent_registry.register_agent(
                fisher_id, "explorer", agent.x, agent.y
            )
            # Register with AI system
            server.ai_system.register_agent(
                fisher_id, "explorer", agent.x, agent.y
            )

        # Get the agent state and give them a fishing rod
        agent_state = server.agent_registry.get_agent(fisher_id)
        if agent_state:
            # Initialize inventory if not exists
            if not hasattr(agent_state, 'inventory'):
                agent_state.inventory = Inventory(capacity=20)
                logger.info(f"Created inventory for fisher {fisher_id[:8]} with 20 slots")

            # Add fishing rod
            fishing_rod = FishingRod()
            success = agent_state.inventory.add_item(fishing_rod)
            if success:
                logger.info(f"Added fishing rod to fisher {fisher_id[:8]}'s inventory")
            else:
                logger.error(f"Failed to add fishing rod to fisher {fisher_id[:8]}'s inventory!")

            # Log inventory status
            logger.info(f"Fisher inventory: {agent_state.inventory.get_used_slot_count()} items, "
                       f"{agent_state.inventory.get_empty_slot_count()} free slots")

        agent_configs.append({
            "id": fisher_id,
            "type": "explorer",
            "personality": fisher_personality,
            "archetype": "fisher",
            "behavior": "personality_driven"
        })

        # Log the water tiles near spawn
        for y in range(7, 13):
            for x in range(8, 13):
                tile = server.world.world_map.get_tile(x, y)
                if tile and hasattr(tile, 'name') and tile.name == 'WATER':
                    logger.info(f"Water tile found at ({x}, {y}) - distance from spawn: "
                               f"{((x-10)**2 + (y-8)**2)**0.5:.1f} units")

        logger.info(f"Simple fishing test scenario setup complete:")
        logger.info(f"  Fisher (fishing:{fisher_personality.fishing:.1f}) at (10, 8) with fishing rod")
        logger.info(f"  Small map (20x20) with water tiles")
        logger.info(f"  Expected behavior: Move to water (2 units) -> Fish repeatedly")

        return agent_configs

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Implementation of abstract method - agents already spawned in setup"""
        return []

    def get_custom_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float) -> Optional[Any]:
        """
        Personality agents use the personality tree builder instead of custom trees.
        This method returns None to indicate they should use their built-in personality-driven behavior.
        """
        return None