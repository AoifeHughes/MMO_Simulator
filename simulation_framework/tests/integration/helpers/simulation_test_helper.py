"""Helper utilities for creating controlled, deterministic simulation tests"""

import tempfile
import os
from typing import Tuple, Optional
from src.core.simulation import Simulation
from src.core.config import SimulationConfig
from src.core.world import World
from src.world.tile import Tile, ResourceDeposit
from src.world.terrain import TerrainType, TerrainProperties
from src.entities.agent import Agent
from src.items.weapon import Weapon
from src.items.tool import Tool


def create_test_config(
    world_size: int = 10,
    max_ticks: int = 1000,
    save_interval: int = 10,
    analytics_interval: int = 10,
    seed: int = 12345
) -> SimulationConfig:
    """
    Create a deterministic test configuration.

    Args:
        world_size: Size of square world
        max_ticks: Maximum ticks to run
        save_interval: How often to save snapshots
        analytics_interval: How often to calculate analytics
        seed: Fixed seed for reproducibility

    Returns:
        SimulationConfig configured for testing
    """
    # Create temporary database for this test
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    return SimulationConfig(
        world_width=world_size,
        world_height=world_size,
        world_seed=seed,
        max_ticks=max_ticks,
        database_path=db_path,
        save_interval=save_interval,
        analytics_interval=analytics_interval,
        tick_rate=0,  # Maximum speed for tests
        fog_of_war_enabled=False,  # Disable for simpler testing
        enable_pathfinding_cache=True
    )


def create_controlled_world(
    width: int,
    height: int,
    terrain: str = "plains",
    seed: int = 12345
) -> World:
    """
    Create a controlled world with uniform terrain for predictable testing.

    Args:
        width: World width
        height: World height
        terrain: Terrain type to fill world with (plains, forest, mountain, water)
        seed: Fixed seed

    Returns:
        World with uniform, passable terrain
    """
    world = World(width, height, seed=seed)

    # Map terrain string to TerrainType
    terrain_map = {
        "plains": TerrainType.GRASS,
        "grass": TerrainType.GRASS,
        "forest": TerrainType.FOREST,
        "mountain": TerrainType.MOUNTAIN,
        "water": TerrainType.WATER,
        "desert": TerrainType.DESERT
    }

    terrain_type = terrain_map.get(terrain, TerrainType.GRASS)

    # Override all tiles with specified terrain
    for y in range(height):
        for x in range(width):
            tile = world.tiles[y][x]
            tile.terrain_type = terrain_type

            # Use standard properties for terrain type
            tile.properties = TerrainProperties.for_terrain(terrain_type)

    return world


def force_agent_equipment(agent: Agent, equipment_type: str) -> None:
    """
    Force specific equipment onto an agent for deterministic combat testing.

    Args:
        agent: Agent to equip
        equipment_type: Type of equipment (sword, bow, staff, axe, pickaxe)
    """
    # Clear existing equipment
    agent.inventory.items.clear()

    # Add specified equipment
    if equipment_type == "sword":
        weapon = Weapon.create_sword()
        agent.inventory.add_item(weapon, 1)
        agent.inventory.equip_weapon(weapon)
    elif equipment_type == "bow":
        weapon = Weapon.create_bow()
        agent.inventory.add_item(weapon, 1)
        agent.inventory.equip_weapon(weapon)
    elif equipment_type == "staff":
        weapon = Weapon.create_staff()
        agent.inventory.add_item(weapon, 1)
        agent.inventory.equip_weapon(weapon)
    elif equipment_type == "axe":
        tool = Tool.create_axe()
        agent.inventory.add_item(tool, 1)
        agent.inventory.equip_tool(tool, "axe")
    elif equipment_type == "pickaxe":
        tool = Tool.create_pickaxe()
        agent.inventory.add_item(tool, 1)
        agent.inventory.equip_tool(tool, "pickaxe")
    elif equipment_type == "fishing_rod":
        tool = Tool.create_fishing_rod()
        agent.inventory.add_item(tool, 1)
        agent.inventory.equip_tool(tool, "fishing_rod")


def place_resource_node(
    world: World,
    x: int,
    y: int,
    resource_type: str,
    amount: int = 100
) -> None:
    """
    Place a guaranteed resource node at specific coordinates.

    Args:
        world: World to modify
        x: X coordinate
        y: Y coordinate
        resource_type: Type of resource (wood, stone, iron, food)
        amount: Amount of resource
    """
    if not world.is_valid_position(x, y):
        raise ValueError(f"Invalid position ({x}, {y}) for world {world.width}x{world.height}")

    tile = world.get_tile(x, y)
    if not tile:
        raise ValueError(f"No tile found at ({x}, {y})")

    # Add resource deposit
    deposit = ResourceDeposit(resource_type, amount)
    tile.add_resource(deposit)

    # Set appropriate terrain for resource type
    if resource_type == "wood":
        tile.terrain_type = TerrainType.FOREST
    elif resource_type in ["stone", "iron"]:
        tile.terrain_type = TerrainType.MOUNTAIN


def create_wall_obstacle(
    world: World,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int
) -> None:
    """
    Create a wall of impassable terrain between two points.

    Args:
        world: World to modify
        start_x, start_y: Start coordinates
        end_x, end_y: End coordinates
    """
    # Create vertical or horizontal wall
    if start_x == end_x:
        # Vertical wall
        for y in range(min(start_y, end_y), max(start_y, end_y) + 1):
            if world.is_valid_position(start_x, y):
                tile = world.get_tile(start_x, y)
                tile.terrain_type = TerrainType.MOUNTAIN
                tile.properties.passable = False
    else:
        # Horizontal wall
        for x in range(min(start_x, end_x), max(start_x, end_x) + 1):
            if world.is_valid_position(x, start_y):
                tile = world.get_tile(x, start_y)
                tile.terrain_type = TerrainType.MOUNTAIN
                tile.properties.passable = False


def cleanup_test_database(db_path: str) -> None:
    """Clean up test database file"""
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except Exception:
        pass
