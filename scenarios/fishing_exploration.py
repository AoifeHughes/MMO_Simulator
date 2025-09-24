import logging
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario
from world.terrain_generator import TerrainType
from client.behavior_tree.nodes import *
from client.behavior_tree.tree import BehaviorTree

logger = logging.getLogger(__name__)


class FishingExplorationScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Fishing Exploration",
            description="Explorer agent explores until finding water, then fishes for food",
            terrain_type=TerrainType.MIXED,  # Mixed terrain with water bodies
            seed=200,  # Seed that generates interesting terrain with water
        )
        self.num_explorers = 1

    async def setup(self, server):
        """Setup fishing exploration scenario"""
        self.server = server
        logger.info("Setting up fishing exploration scenario")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn explorer agent with fishing rod"""
        agent_configs = []

        # Spawn single explorer at starting position
        explorer_x, explorer_y = 50, 50
        explorer_rotation = 0.0

        agent_config = {
            "type": "explorer",
            "position": (explorer_x, explorer_y),
            "name": "Fisher_Explorer",
        }
        agent_configs.append(agent_config)

        # Spawn the agent on the server
        agent_id = self.server.world.spawn_agent("explorer", explorer_x, explorer_y, explorer_rotation)

        # Register agent and give starting items (fishing rod is added automatically for explorers)
        agent_state = self.server.agent_registry.register_agent(agent_id, "explorer", explorer_x, explorer_y)

        # Mark this agent as a fishing explorer
        agent_state.exploration_mode = "fishing"

        logger.info(f"Spawned explorer {agent_id} at ({explorer_x}, {explorer_y})")
        logger.info(f"Explorer inventory: {len(agent_state.inventory.slots)} slots")
        logger.info(f"Explorer has fishing rod: {bool([item for item in agent_state.inventory.get_items_by_type('tool') if hasattr(item, 'tool_type') and item.tool_type == 'fishing'])}")

        # Override the default explorer behavior tree with fishing exploration tree
        self._create_fishing_explorer_tree(explorer_x, explorer_y)

        logger.info("Fishing exploration scenario setup:")
        logger.info(f"  Explorer: 1 agent with fishing rod")
        logger.info(f"  Goal: Explore until water is found, then fish")
        logger.info(f"  Terrain: Mixed terrain with water bodies")
        logger.info(f"  Expected behavior: Explore -> Find water -> Fish repeatedly")

        return agent_configs

    def _create_fishing_explorer_tree(self, home_x: float, home_y: float) -> BehaviorTree:
        """
        Create behavior tree for fishing explorer agent.
        Behavior: Explore until water found -> Fish at water -> Continue exploring/fishing
        """

        root = PrioritySelector(
            "FishingExplorerRoot",
            [
                # Priority 1: Fish at water if we're already close enough and have fishing rod
                Sequence(
                    "FishingBehavior",
                    [
                        HasFishingRod(),
                        WaterNearby(1.2),  # Use same distance as FishAtWater for consistency
                        TimerDecorator(
                            "FishingCommitment",
                            CooldownDecorator(
                                "FishingCooldown",
                                FishAtWater(1.2),
                                cooldown_duration=2.0,
                            ),
                            minimum_duration=10.0,  # Stay fishing for 10 seconds minimum
                        ),
                    ],
                ),

                # Priority 2: Move to water if discovered but not nearby
                Sequence(
                    "MoveToWater",
                    [
                        HasFishingRod(),
                        WaterDiscoveredButNotNearby(1.2),
                        CooldownDecorator(
                            "MoveToWaterCooldown",
                            TimerDecorator(
                                "MoveToWaterTimer",
                                MoveToFishingSpot(1.2),
                                minimum_duration=2.0,
                            ),
                            cooldown_duration=1.0,
                        ),
                    ],
                ),

                # Priority 3: Explore to find water
                CooldownDecorator(
                    "ExplorationCooldown",
                    TimerDecorator(
                        "ExploreTimer",
                        Explore(40.0, "frontier"),  # Large exploration radius
                        minimum_duration=3.0,
                    ),
                    cooldown_duration=1.0,
                ),

                # Priority 4: Wander if stuck or need to move
                Sequence(
                    "UnstuckBehavior",
                    [
                        IsStuck(1.0, 2.0),
                        CooldownDecorator(
                            "UnstuckCooldown",
                            Wander(home_x, home_y, 15.0),
                            cooldown_duration=3.0,
                        ),
                    ],
                ),

                # Priority 5: Default idle
                Idle(1.0),
            ],
        )

        # Store the tree for later use (in a real implementation, this would be
        # passed to the agent when it connects)
        self.fishing_explorer_tree = BehaviorTree(root, "FishingExplorerTree")
        return self.fishing_explorer_tree

    def get_custom_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float) -> BehaviorTree:
        """Return custom behavior tree for this scenario"""
        if agent_type == "explorer":
            return self._create_fishing_explorer_tree(agent_x, agent_y)
        return None