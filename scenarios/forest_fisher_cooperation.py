"""
Forest Fisher Cooperation Scenario

This scenario demonstrates agent cooperation through resource gathering and sharing.
Two agents specialize in different tasks:
- Wood Cutter: Harvests wood from forest tiles, crafts fires when possible
- Fisher: Catches fish, seeks fires for cooking (when fish are available)

Expected behaviors:
- Wood cutter explores to find forest tiles and harvests wood
- When wood cutter has enough wood (2+ pieces), creates fires
- Fisher focuses on fishing but will look for fires when holding fish
- Potential trading between agents if implemented
"""

import logging
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario
from world.terrain_generator import TerrainType

logger = logging.getLogger(__name__)


class ForestFisherCooperationScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Forest Fisher Cooperation",
            description="Two agents cooperate: Wood Cutter harvests wood and creates fires, Fisher catches fish and seeks fires",
            terrain_type=TerrainType.MIXED,  # Mixed terrain with forest and water
            seed=300,  # Seed that generates good forest and water distribution
            world_width=20,  # Small map for close interaction
            world_height=20
        )
        self.map_size = 20  # Small map for close interaction

    async def setup(self, server):
        """Setup the cooperation scenario"""
        self.server = server
        logger.info("Setting up Forest Fisher Cooperation scenario")

        # Create custom terrain layout optimized for cooperation
        self._create_custom_terrain(server.world.world_map)
        logger.info(f"Scenario using custom small {self.map_size}x{self.map_size} map for close cooperation")

    def _create_custom_terrain(self, world_map):
        """Create a custom terrain layout with forest and water areas for cooperation"""
        from world.tiles import TileType

        # Create a custom layout for cooperation
        # Left side: Forest area for wood harvesting
        # Right side: Water areas for fishing
        # Center: Mixed terrain for cooperation

        width, height = world_map.width, world_map.height

        for y in range(height):
            for x in range(width):
                # Define regions
                left_forest = x < width // 3  # Left third is forest
                right_water = x > 2 * width // 3  # Right third has water
                center_area = width // 3 <= x <= 2 * width // 3  # Center third is mixed

                if left_forest:
                    # Forest area for wood harvesting
                    if (x + y) % 3 == 0:
                        world_map.tiles[y][x] = TileType.WOOD  # WOOD tiles for harvesting
                    else:
                        world_map.tiles[y][x] = TileType.GRASS

                elif right_water:
                    # Water area for fishing
                    if abs(y - height // 2) < 3 or (x + y) % 4 == 0:
                        world_map.tiles[y][x] = TileType.WATER
                    else:
                        world_map.tiles[y][x] = TileType.GRASS

                else:  # center_area
                    # Mixed terrain - some forest, some water, mostly grassland
                    tile_value = (x * 7 + y * 11) % 10
                    if tile_value < 2:
                        world_map.tiles[y][x] = TileType.WOOD  # WOOD tiles for harvesting
                    elif tile_value < 3:
                        world_map.tiles[y][x] = TileType.WATER
                    else:
                        world_map.tiles[y][x] = TileType.GRASS

        # Ensure starting positions are on walkable terrain
        center_x, center_y = width // 2, height // 2

        # Wood cutter starting area (left side)
        woodcutter_x, woodcutter_y = center_x - 2, center_y - 1
        world_map.tiles[woodcutter_y][woodcutter_x] = TileType.GRASS

        # Fisher starting area (right side)
        fisher_x, fisher_y = center_x + 2, center_y + 1
        world_map.tiles[fisher_y][fisher_x] = TileType.GRASS

        # Ensure some forest near wood cutter
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                ny, nx = woodcutter_y + dy, woodcutter_x + dx - 2
                if 0 <= ny < height and 0 <= nx < width and (dx != 0 or dy != 0):
                    if abs(dx) == 1 or abs(dy) == 1:
                        world_map.tiles[ny][nx] = TileType.WOOD

        # Ensure some water near fisher
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                ny, nx = fisher_y + dy, fisher_x + dx + 2
                if 0 <= ny < height and 0 <= nx < width and (dx != 0 or dy != 0):
                    if abs(dx) == 1 or abs(dy) == 1:
                        world_map.tiles[ny][nx] = TileType.WATER

        logger.info("Created custom terrain layout:")
        logger.info(f"  Forest area: Left third with concentrated forest near wood cutter")
        logger.info(f"  Water area: Right third with concentrated water near fisher")
        logger.info(f"  Center area: Mixed terrain for cooperation space")

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn the two specialist agents close to each other"""
        agent_configs = []

        # Calculate good starting positions on small map
        center_x, center_y = self.map_size // 2, self.map_size // 2

        # Wood Cutter - starts near center, focuses on finding forest
        woodcutter_x, woodcutter_y = center_x - 2, center_y - 1
        woodcutter_config = {
            "type": "explorer",
            "position": (woodcutter_x, woodcutter_y),
            "name": "WoodCutter",
            "behavior": "wood_harvester",
            "specialization": "wood_harvesting",
            "exploration_mode": "wood_harvesting"  # Use dedicated wood harvesting behavior
        }
        agent_configs.append(woodcutter_config)

        # Spawn wood cutter agent
        woodcutter_id = self.server.world.spawn_agent("explorer", woodcutter_x, woodcutter_y, 45.0)
        woodcutter_state = self.server.agent_registry.register_agent(woodcutter_id, "explorer", woodcutter_x, woodcutter_y)

        # Store exploration mode and specialization in agent state
        if woodcutter_state:
            woodcutter_state.specialization = "wood_harvesting"
            woodcutter_state.exploration_mode = "wood_harvesting"

        # Give wood cutter starting items (with hatchet for wood harvesting)
        if woodcutter_state:
            # Ensure wood cutter has hatchet for wood harvesting
            from shared.items import create_hatchet
            hatchet = create_hatchet()
            if hatchet and not any(hasattr(item, 'tool_type') and item.tool_type == "woodcutting"
                                 for slot in woodcutter_state.inventory.slots
                                 if not slot.is_empty() for item in [slot.item]):
                woodcutter_state.inventory.add_item(hatchet, 1)

        logger.info(f"Spawned Wood Cutter {woodcutter_id} at ({woodcutter_x}, {woodcutter_y})")

        # Fisher - starts near center but different position, focuses on water
        fisher_x, fisher_y = center_x + 2, center_y + 1
        fisher_config = {
            "type": "explorer",
            "position": (fisher_x, fisher_y),
            "name": "Fisher",
            "behavior": "fishing_specialist",
            "specialization": "fishing",
            "exploration_mode": "fishing"  # Use dedicated fishing behavior
        }
        agent_configs.append(fisher_config)

        # Spawn fisher agent
        fisher_id = self.server.world.spawn_agent("explorer", fisher_x, fisher_y, 225.0)
        fisher_state = self.server.agent_registry.register_agent(fisher_id, "explorer", fisher_x, fisher_y)

        # Store exploration mode and specialization in agent state
        if fisher_state:
            fisher_state.specialization = "fishing"
            fisher_state.exploration_mode = "fishing"

        # Fisher keeps fishing rod and gets extra space for fish
        logger.info(f"Spawned Fisher {fisher_id} at ({fisher_x}, {fisher_y})")

        # Log scenario setup details
        logger.info("Forest Fisher Cooperation scenario setup:")
        logger.info(f"  Map Size: {self.map_size}x{self.map_size} for close cooperation")
        logger.info(f"  Wood Cutter: Harvests wood → Crafts fires (basic_fire recipe: 2 wood)")
        logger.info(f"  Fisher: Catches fish → Seeks fires for cooking")
        logger.info(f"  Expected Cooperation: Wood cutter provides fires for fisher")
        logger.info(f"  Distance between agents: ~{((fisher_x - woodcutter_x)**2 + (fisher_y - woodcutter_y)**2)**0.5:.1f} units")

        return agent_configs

    def get_custom_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float) -> Any:
        """Return None to use default agent behaviors with some modifications"""
        # For this scenario, we'll rely on the default explorer behavior
        # The specializations will be handled through the behavior names set above
        # In a more advanced implementation, we could create custom behavior trees here
        return None

    def get_scenario_info(self) -> Dict[str, Any]:
        """Get scenario information for agents"""
        return {
            "scenario_type": "cooperation",
            "map_size": self.map_size,
            "agent_roles": {
                "WoodCutter": {
                    "primary_task": "harvest_wood",
                    "secondary_task": "craft_fire",
                    "required_items": ["wood"],
                    "crafting_recipes": ["basic_fire"]
                },
                "Fisher": {
                    "primary_task": "fishing",
                    "secondary_task": "find_fire",
                    "target_items": ["fish"],
                    "seeks_objects": ["fire", "campfire"]
                }
            },
            "cooperation_mechanics": {
                "wood_to_fire": "2 wood → 1 fire (5 minutes)",
                "fire_benefits": "Enables fish cooking/processing",
                "proximity_required": "Agents spawn within 6 units of each other"
            }
        }