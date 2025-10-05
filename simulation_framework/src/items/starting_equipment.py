"""
Starting equipment helper functions for agents.
Provides appropriate tools and items based on agent goals and character class.
"""

from typing import List, Optional, TYPE_CHECKING
from .tool import Tool
from .item import Item

if TYPE_CHECKING:
    from ..entities.agent import Agent
    from ..ai.goal import Goal


def give_starting_equipment(agent: 'Agent') -> None:
    """
    Give an agent appropriate starting equipment based on their goals and class.

    Args:
        agent: The agent to equip
    """
    # Get equipment based on character class
    class_equipment = get_class_equipment(agent.character_class.name if hasattr(agent, 'character_class') else "Explorer")

    # Get equipment based on goals
    goal_equipment = get_goal_equipment(agent.current_goals if hasattr(agent, 'current_goals') else [])

    # Add all equipment to inventory
    all_equipment = class_equipment + goal_equipment
    for item in all_equipment:
        if hasattr(agent, 'inventory'):
            agent.inventory.add_item(item, 1)
            # Auto-equip tools
            if isinstance(item, Tool):
                tool_type = item.get_tool_type()
                agent.inventory.equip_tool(item, tool_type)


def get_class_equipment(class_name: str) -> List[Item]:
    """
    Get starting equipment based on character class.

    Args:
        class_name: Name of the character class

    Returns:
        List of starting items for the class
    """
    equipment = []

    if class_name == "Warrior":
        # Warriors get basic combat equipment
        weapon = Item(
            id=100,
            name="Iron Sword",
            item_type="weapon",
            properties={"damage": 10, "weapon_type": "sword"},
            description="A basic iron sword",
            value=50,
            weight=3.0
        )
        equipment.append(weapon)

    elif class_name == "Explorer":
        # Explorers get basic survival tools
        knife = Item(
            id=101,
            name="Survival Knife",
            item_type="tool",
            properties={"damage": 3, "tool_type": "knife"},
            description="A versatile survival knife",
            value=20,
            weight=0.5
        )
        equipment.append(knife)

    # All classes get basic supplies
    equipment.append(Item(
        id=102,
        name="Bread",
        item_type="consumable",
        properties={"healing": 10},
        description="Basic food ration",
        value=5,
        weight=0.2,
        max_stack_size=10
    ))

    return equipment


def get_goal_equipment(goals: List['Goal']) -> List[Item]:
    """
    Get equipment based on agent's current goals.

    Args:
        goals: List of agent's current goals

    Returns:
        List of tools needed for the goals
    """
    equipment = []
    tools_added = set()

    for goal in goals:
        goal_type = goal.__class__.__name__

        # Check for resource gathering goals
        if "GatherResourceGoal" in goal_type:
            resource_type = getattr(goal, 'resource_type', None)

            if resource_type == "wood" and "axe" not in tools_added:
                equipment.append(Tool.create_axe())
                tools_added.add("axe")

            elif resource_type == "stone" and "pickaxe" not in tools_added:
                equipment.append(Tool.create_pickaxe())
                tools_added.add("pickaxe")

            elif resource_type in ["fish", "fishing"] and "fishing_rod" not in tools_added:
                equipment.append(Tool.create_fishing_rod())
                tools_added.add("fishing_rod")

        # Check for combat goals
        elif "AttackEnemyGoal" in goal_type or "CombatGoal" in goal_type:
            if "weapon" not in tools_added:
                weapon = Item(
                    id=103,
                    name="Basic Spear",
                    item_type="weapon",
                    properties={"damage": 7, "weapon_type": "spear", "range": 2},
                    description="A simple wooden spear",
                    value=15,
                    weight=2.0
                )
                equipment.append(weapon)
                tools_added.add("weapon")

    return equipment


def create_basic_tool_set() -> List[Tool]:
    """
    Create a basic set of tools for testing.

    Returns:
        List containing one of each basic tool type
    """
    return [
        Tool.create_axe(),
        Tool.create_pickaxe(),
        Tool.create_fishing_rod()
    ]


def equip_agent_for_task(agent: 'Agent', task: str) -> bool:
    """
    Equip an agent with the appropriate tool for a specific task.

    Args:
        agent: The agent to equip
        task: The task type (e.g., "woodcutting", "mining", "fishing")

    Returns:
        True if the agent was successfully equipped, False otherwise
    """
    if not hasattr(agent, 'inventory'):
        return False

    tool_map = {
        "woodcutting": Tool.create_axe(),
        "mining": Tool.create_pickaxe(),
        "fishing": Tool.create_fishing_rod()
    }

    if task in tool_map:
        tool = tool_map[task]
        agent.inventory.add_item(tool, 1)
        tool_type = tool.get_tool_type()
        agent.inventory.equip_tool(tool, tool_type)
        return True

    return False