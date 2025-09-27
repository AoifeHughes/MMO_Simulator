import logging
from typing import Any, Dict, List, Optional

from client.agent_types.personality_agent import PersonalityAgent
from scenarios.base_scenario import BaseScenario
from shared.personality import PersonalityArchetype, create_personality_variant
from world.terrain_generator import TerrainType

logger = logging.getLogger(__name__)


class FishingExplorationScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Fishing Exploration",
            description="Explorer-fisher personality agent explores until finding water, then fishes for food",
            terrain_type=TerrainType.MIXED,  # Mixed terrain with water bodies
            seed=200,  # Seed that generates interesting terrain with water
        )
        self.num_explorers = 1

    async def setup(self, server):
        """Setup fishing exploration scenario"""
        self.server = server
        logger.info("Setting up fishing exploration scenario")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn explorer-fisher personality agent with fishing rod"""
        agent_configs = []

        # Create explorer-fisher personality (high exploration and fishing)
        explorer_fisher = create_personality_variant(
            PersonalityArchetype.explorer(),
            {
                "exploration": 7.0,
                "fishing": 8.0,
                "patience": 8.0,  # Patient enough for both exploration and fishing
                "foraging": 5.0,  # Some interest in resource gathering
            },
        )

        # Spawn single explorer-fisher at starting position
        explorer_x, explorer_y = 50, 50
        explorer_rotation = 0.0

        agent_config = {
            "type": "explorer",
            "position": (explorer_x, explorer_y),
            "name": "ExplorerFisher",
            "personality": explorer_fisher,
            "archetype": "explorer_fisher",
            "behavior": "personality_driven",
        }
        agent_configs.append(agent_config)

        # Spawn the agent on the server
        agent_id = self.server.world.spawn_agent(
            "explorer", explorer_x, explorer_y, explorer_rotation
        )

        # Register agent and give starting items
        agent_state = self.server.agent_registry.register_agent(
            agent_id, "explorer", explorer_x, explorer_y
        )

        # Store personality configuration on agent state for server-to-client communication
        if agent_state:
            agent_state.personality_config = {
                "personality": explorer_fisher.to_dict(),
                "archetype": "explorer_fisher",
                "behavior": "personality_driven",
            }

        logger.info(
            f"Spawned explorer-fisher {agent_id} at ({explorer_x}, {explorer_y})"
        )
        logger.info(
            f"Explorer-fisher personality: exploration={explorer_fisher.exploration:.1f}, fishing={explorer_fisher.fishing:.1f}"
        )

        logger.info("Fishing exploration scenario setup:")
        logger.info(
            f"  Explorer-Fisher: 1 personality agent with balanced exploration/fishing desires"
        )
        logger.info(
            f"  Goal: Explore until water is found, then switch focus to fishing"
        )
        logger.info(f"  Terrain: Mixed terrain with water bodies")
        logger.info(
            f"  Expected behavior: Dynamic priority switching between exploration and fishing"
        )

        return agent_configs

    def get_custom_behavior_tree(
        self, agent_type: str, agent_x: float, agent_y: float
    ) -> Optional[Any]:
        """
        Personality agents use the personality tree builder for exploration/fishing behavior.
        This method returns None to indicate they should use their built-in personality-driven behavior.
        """
        return None
