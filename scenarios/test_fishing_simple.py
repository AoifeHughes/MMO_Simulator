"""
Simple Fishing Test Scenario

A minimal test scenario to verify fishing mechanics work correctly.
- Small 20x20 map with guaranteed water
- Agent spawns right next to water (2 units away)
- Simple behavior: move to water -> fish -> check inventory
"""

import logging
from typing import Any, Dict, List

from client.behavior_tree.nodes.action import MoveToTarget
from client.behavior_tree.nodes.base import NodeStatus
from client.behavior_tree.nodes.composite import PrioritySelector as Selector, Sequence
from client.behavior_tree.nodes.condition import CustomCondition
from client.behavior_tree.nodes.decorator import CooldownDecorator, TimerDecorator
from client.behavior_tree.nodes.fishing_action import FishAtWater
from client.behavior_tree.tree import BehaviorTree
from scenarios.base_scenario import BaseScenario
from shared.inventory import Inventory
from shared.items import FishingRod, ItemType

logger = logging.getLogger(__name__)


class TestFishingSimpleScenario(BaseScenario):
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
        logger.info("Setting up simple fishing test scenario")

        # Create a single fishing explorer at position (10, 8)
        # Water will be at approximately (10, 10) with lakes terrain
        agent_configs = []

        explorer_id = server.world.spawn_agent(
            agent_type="explorer",
            x=10,
            y=8,  # Just 2 units from expected water
            rotation=90  # Facing down toward water
        )

        # Register the agent in the registry so it can be found by clients
        agent = server.world.get_agent(explorer_id)
        if agent:
            server.agent_registry.register_agent(
                explorer_id, "explorer", agent.x, agent.y
            )
            # Register with AI system
            server.ai_system.register_agent(
                explorer_id, "explorer", agent.x, agent.y
            )

        # Get the agent state and give them a fishing rod with proper inventory
        agent_state = server.agent_registry.get_agent(explorer_id)
        if agent_state:
            # Initialize inventory if not exists
            if not hasattr(agent_state, 'inventory'):
                agent_state.inventory = Inventory(capacity=20)
                logger.info(f"Created inventory for explorer {explorer_id[:8]} with 20 slots")

            # Add fishing rod
            fishing_rod = FishingRod()
            success = agent_state.inventory.add_item(fishing_rod)
            if success:
                logger.info(f"Added fishing rod to explorer {explorer_id[:8]}'s inventory")
            else:
                logger.error(f"Failed to add fishing rod to explorer {explorer_id[:8]}'s inventory!")

            # Log inventory status
            logger.info(f"Explorer inventory: {agent_state.inventory.get_used_slot_count()} items, "
                       f"{agent_state.inventory.get_empty_slot_count()} free slots")

            # Mark as fishing mode
            agent_state.exploration_mode = "fishing"

        agent_configs.append({
            "id": explorer_id,
            "type": "explorer",
            "behavior": "fishing_test"
        })

        # Log the water tiles near spawn
        for y in range(7, 13):
            for x in range(8, 13):
                tile = server.world.world_map.get_tile(x, y)
                if tile and hasattr(tile, 'name') and tile.name == 'WATER':
                    logger.info(f"Water tile found at ({x}, {y}) - distance from spawn: "
                               f"{((x-10)**2 + (y-8)**2)**0.5:.1f} units")

        logger.info(f"Simple fishing test scenario setup complete:")
        logger.info(f"  Explorer at (10, 8) with fishing rod")
        logger.info(f"  Small map (20x20) with water tiles")
        logger.info(f"  Expected behavior: Move to water (2 units) -> Fish repeatedly")

        return agent_configs

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Implementation of abstract method - agents already spawned in setup"""
        return []

    def _has_fishing_rod(self, agent) -> bool:
        """Check if agent has a fishing rod in inventory"""
        if not hasattr(agent, 'inventory') or not agent.inventory:
            logger.warning(f"Agent {agent.id[:8]} has no inventory!")
            return False

        items = agent.inventory.get_items_by_type(ItemType.TOOL)
        has_rod = any(isinstance(item, FishingRod) for item in items)

        if has_rod:
            logger.debug(f"Agent {agent.id[:8]} has fishing rod")
        else:
            logger.warning(f"Agent {agent.id[:8]} has NO fishing rod in inventory!")

        return has_rod

    def _is_at_water(self, agent) -> bool:
        """Check if agent is adjacent to water"""
        if not hasattr(agent, 'agent_map') or not agent.agent_map:
            return False

        agent_x, agent_y = int(agent.x), int(agent.y)

        # Check all adjacent tiles for water
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue

                check_x, check_y = agent_x + dx, agent_y + dy
                if agent.agent_map.is_valid_position(check_x, check_y):
                    tile = agent.agent_map.get_tile_type(check_x, check_y)
                    if hasattr(tile, 'name') and tile.name == 'WATER':
                        logger.info(f"Agent {agent.id[:8]} is at water! Water at ({check_x}, {check_y})")
                        return True

        return False

    def _count_fish_in_inventory(self, agent) -> int:
        """Count fish in agent's inventory"""
        if not hasattr(agent, 'inventory') or not agent.inventory:
            return 0

        fish_items = agent.inventory.get_items_by_type(ItemType.FOOD)
        fish_count = sum(1 for item in fish_items if "fish" in item.name.lower())

        if fish_count > 0:
            logger.info(f"Agent {agent.id[:8]} has {fish_count} fish in inventory!")

        return fish_count

    def get_custom_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float) -> BehaviorTree:
        """Create simple fishing test behavior tree"""
        if agent_type == "explorer":
            # Ultra-simple fishing behavior
            root = Sequence(
                "SimpleFishingRoot",
                [
                    # First ensure we have a fishing rod
                    CustomCondition(
                        "HasFishingRod",
                        lambda agent: self._has_fishing_rod(agent)
                    ),

                    # Then either fish if at water, or move to water
                    Selector(
                        "FishOrMove",
                        [
                            # If at water, fish
                            Sequence(
                                "FishingSequence",
                                [
                                    CustomCondition(
                                        "AtWater",
                                        lambda agent: self._is_at_water(agent)
                                    ),
                                    CooldownDecorator(
                                        "FishingCooldown",
                                        TimerDecorator(
                                            "FishingTimer",
                                            FishAtWater(),
                                            minimum_duration=3.0
                                        ),
                                        cooldown_duration=2.0
                                    ),
                                    # Log fish count after fishing
                                    CustomCondition(
                                        "CountFish",
                                        lambda agent: self._count_fish_in_inventory(agent) >= 0  # Always true, just logs
                                    )
                                ]
                            ),

                            # Otherwise move to water (hardcoded position)
                            TimerDecorator(
                                "MoveToWaterTimer",
                                MoveToTarget(10, 10),  # Known water location
                                minimum_duration=2.0
                            )
                        ]
                    )
                ]
            )

            tree = BehaviorTree(root, "SimpleFishingTree")
            logger.info(f"Created simple fishing test tree for explorer at ({agent_x}, {agent_y})")
            return tree

        return None