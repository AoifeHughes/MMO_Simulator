"""
Example implementations showing how easy it is to add new actions
using the TwoPhaseActionNode and ResourceActionNode base classes.

These examples demonstrate the OOP extensibility of the system.
"""

import asyncio
from typing import Optional, Tuple

from shared.actions import ActionType
from world.tiles import TileType

from .two_phase_action import ResourceActionNode, TwoPhaseActionNode


class MineStone(ResourceActionNode):
    """Mine stone from mountain tiles - demonstrates extending ResourceActionNode"""

    def __init__(self, max_distance: float = 5.0):
        # Look for stone/mountain tiles within 5 units
        super().__init__(
            "MineStone", TileType.WALL, max_distance
        )  # Assuming WALL represents stone

    def execute_action(self, agent, target_pos: Tuple[float, float]) -> bool:
        """Execute stone mining at confirmed position"""
        # Send mining request to server (would need to add MINE_STONE action type)
        print(
            f"⛏️ Agent {agent.id[:8]} mining stone at validated position ({target_pos[0]:.2f}, {target_pos[1]:.2f})"
        )

        # For demo purposes, just return True
        # In real implementation:
        # self._request_mining(agent, target_pos[0], target_pos[1])
        return True

    def get_action_name(self) -> str:
        return "stone_mining"

    def get_resource_type(self) -> str:
        return "stone"

    def should_complete_action(self, agent, elapsed_time: float) -> bool:
        return elapsed_time >= 5.0  # Mining takes longer than fishing/wood


class OpenChest(TwoPhaseActionNode):
    """Open a chest - demonstrates extending TwoPhaseActionNode for non-resource actions"""

    def __init__(self):
        super().__init__("OpenChest", required_distance=1.5)
        self.chest_entities = []

    def find_action_target(self, agent) -> Optional[Tuple[float, float]]:
        """Find the nearest chest entity"""
        nearest_chest = None
        nearest_distance = float("inf")

        # Look through visible entities for chests
        for entity in getattr(agent, "visible_entities", []):
            if entity.get("type") == "chest":
                distance = (
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                ) ** 0.5
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_chest = (entity["x"], entity["y"])

        return nearest_chest

    def calculate_optimal_position(
        self, agent, target_pos: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """Calculate position to stand next to chest"""
        # Similar to ResourceActionNode but for entities instead of tiles
        target_x, target_y = target_pos

        # Position agent 1.0 unit away from chest
        dx = agent.x - target_x
        dy = agent.y - target_y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance < 0.1:
            return (target_x + 1.0, target_y)  # Default offset

        normalized_dx = dx / distance
        normalized_dy = dy / distance

        optimal_x = target_x + normalized_dx * 1.0
        optimal_y = target_y + normalized_dy * 1.0

        return (optimal_x, optimal_y)

    def execute_action(self, agent, target_pos: Tuple[float, float]) -> bool:
        """Execute chest opening"""
        print(
            f"📦 Agent {agent.id[:8]} opening chest at ({target_pos[0]:.2f}, {target_pos[1]:.2f})"
        )

        # Send chest interaction request
        # self._request_chest_interaction(agent, target_pos[0], target_pos[1])
        return True

    def get_action_name(self) -> str:
        return "chest_opening"

    def get_resource_type(self) -> str:
        return "chest"

    def should_complete_action(self, agent, elapsed_time: float) -> bool:
        return elapsed_time >= 2.0  # Quick action


class AttackEnemy(TwoPhaseActionNode):
    """Attack an enemy - demonstrates combat action with positioning"""

    def __init__(self, attack_range: float = 2.0):
        super().__init__("AttackEnemy", required_distance=attack_range)
        self.target_enemy_id = None

    def find_action_target(self, agent) -> Optional[Tuple[float, float]]:
        """Find nearest enemy to attack"""
        nearest_enemy = None
        nearest_distance = float("inf")
        nearest_enemy_id = None

        for entity in getattr(agent, "visible_entities", []):
            if entity.get("agent_type") == "enemy":
                distance = (
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                ) ** 0.5
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_enemy = (entity["x"], entity["y"])
                    nearest_enemy_id = entity.get("id")

        self.target_enemy_id = nearest_enemy_id
        return nearest_enemy

    def calculate_optimal_position(
        self, agent, target_pos: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """Position for optimal attack angle"""
        # For combat, we might want to position for tactical advantage
        target_x, target_y = target_pos

        # Position at attack range
        dx = agent.x - target_x
        dy = agent.y - target_y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance < 0.1:
            return (target_x + self.required_distance, target_y)

        normalized_dx = dx / distance
        normalized_dy = dy / distance

        # Position at exact attack range
        optimal_x = target_x + normalized_dx * self.required_distance
        optimal_y = target_y + normalized_dy * self.required_distance

        return (optimal_x, optimal_y)

    def execute_action(self, agent, target_pos: Tuple[float, float]) -> bool:
        """Execute attack"""
        if not self.target_enemy_id:
            return False

        print(
            f"⚔️ Agent {agent.id[:8]} attacking enemy {self.target_enemy_id[:8]} from validated position"
        )

        # Send attack request
        # self._request_attack(agent, self.target_enemy_id)
        return True

    def get_action_name(self) -> str:
        return "combat_attack"

    def get_resource_type(self) -> str:
        return "enemy"

    def should_complete_action(self, agent, elapsed_time: float) -> bool:
        return elapsed_time >= 1.0  # Quick attack


# Example of extending for special positioning requirements
class PlantSeed(TwoPhaseActionNode):
    """Plant seed - requires empty ground and precise positioning"""

    def __init__(self):
        super().__init__("PlantSeed", required_distance=0.5, positioning_tolerance=0.1)

    def find_action_target(self, agent) -> Optional[Tuple[float, float]]:
        """Find suitable ground for planting"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        # Look for empty grass tiles near agent
        agent_x, agent_y = int(agent.x), int(agent.y)

        for dy in range(-3, 4):
            for dx in range(-3, 4):
                check_x = agent_x + dx
                check_y = agent_y + dy

                if agent.agent_map.is_tile_known(check_x, check_y):
                    tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                    if tile_type == TileType.GRASS:
                        # Found suitable planting spot
                        return (check_x + 0.5, check_y + 0.5)

        return None

    def calculate_optimal_position(
        self, agent, target_pos: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """For planting, agent needs to be right next to the target tile"""
        # Position very close to target for precise planting
        return (target_pos[0] + 0.3, target_pos[1])

    def execute_action(self, agent, target_pos: Tuple[float, float]) -> bool:
        """Execute planting"""
        print(
            f"🌱 Agent {agent.id[:8]} planting seed at ({target_pos[0]:.2f}, {target_pos[1]:.2f})"
        )
        return True

    def get_action_name(self) -> str:
        return "seed_planting"

    def get_resource_type(self) -> str:
        return "farmland"

    def should_complete_action(self, agent, elapsed_time: float) -> bool:
        return elapsed_time >= 3.0  # Planting takes time


"""
Benefits of this OOP approach:

1. **No Distance Validation Errors**: Base class handles positioning automatically
2. **Code Reuse**: Common logic is inherited, only unique parts need implementation
3. **Easy Extension**: New actions require only 4-6 methods
4. **Consistent Behavior**: All actions follow the same two-phase pattern
5. **Robust Debugging**: Built-in tracking and logging
6. **Flexible**: Can handle resources, entities, combat, crafting, etc.

To add a new action:
1. Inherit from ResourceActionNode (for resources) or TwoPhaseActionNode (for anything else)
2. Implement find_action_target()
3. Implement execute_action()
4. Implement get_action_name() and get_resource_type()
5. Optionally override calculate_optimal_position() and should_complete_action()

That's it! The base class handles all positioning, movement, validation, timing, and debug tracking.
"""
