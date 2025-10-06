from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ..actions.base import Action
    from ..core.world import World
    from ..entities.base import Entity


class Goal(ABC):
    def __init__(self, priority: int = 5, name: str = "Goal"):
        self.priority = priority  # 1-10, higher is more important
        self.name = name
        self.created_tick = 0
        self.last_progress_tick = 0
        self.attempts = 0
        self.max_attempts = 10

    @abstractmethod
    def is_complete(self, agent: Entity, world: World) -> bool:
        """Check if this goal has been completed"""

    @abstractmethod
    def is_valid(self, agent: Entity, world: World) -> bool:
        """Check if this goal is still valid/achievable"""

    @abstractmethod
    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        """Get the next action to work towards this goal"""

    @abstractmethod
    def get_utility(self, agent: Entity, world: World) -> float:
        """Calculate utility score for this goal (0-1)"""

    def on_action_completed(
        self, action: Action, success: bool, agent: Entity, world: World
    ) -> None:
        """Called when an action for this goal completes"""
        if success:
            self.last_progress_tick = world.current_tick

        self.attempts += 1

    def should_abandon(self, agent: Entity, world: World) -> bool:
        """Check if this goal should be abandoned"""
        if self.attempts >= self.max_attempts:
            return True

        if not self.is_valid(agent, world):
            return True

        # Abandon if no progress for too long
        if (world.current_tick - self.last_progress_tick) > 100:
            return True

        return False

    def get_estimated_duration(self, agent: Entity, world: World) -> int:
        """Estimate how many ticks this goal will take"""
        return 10  # Default estimate

    def __lt__(self, other: Goal) -> bool:
        return self.priority > other.priority  # Higher priority = lower in sort

    def __repr__(self) -> str:
        return f"{self.name}(priority={self.priority})"


class ExploreGoal(Goal):
    def __init__(
        self, target_area: Optional[Tuple[int, int, int]] = None, priority: int = 4
    ):
        super().__init__(priority, "Explore")
        self.target_area = target_area  # (center_x, center_y, radius)
        self.explored_tiles = 0
        self.target_explored_tiles = 20

    def is_complete(self, agent: Entity, world: World) -> bool:
        if hasattr(agent, "known_map"):
            explored_count = len(
                agent.known_map.get_explored_tiles()
                if hasattr(agent.known_map, "get_explored_tiles")
                else []
            )
            return explored_count >= self.target_explored_tiles
        return False

    def is_valid(self, agent: Entity, world: World) -> bool:
        return True  # Always valid

    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        from ..actions.movement import PathfindAction, WanderAction

        if self.target_area:
            center_x, center_y, radius = self.target_area

            # If already in target area, wander
            agent_x, agent_y = agent.position
            distance_to_center = math.sqrt(
                (agent_x - center_x) ** 2 + (agent_y - center_y) ** 2
            )

            if distance_to_center <= radius:
                return WanderAction(agent.id, (center_x, center_y), radius)
            else:
                return PathfindAction(agent.id, (center_x, center_y))
        else:
            # General exploration - wander around current area
            return WanderAction(agent.id, agent.position, 5)

    def get_utility(self, agent: Entity, world: World) -> float:
        base_utility = (
            agent.personality.get_exploration_desire(0.5)
            if hasattr(agent, "personality")
            else 0.5
        )

        # Higher utility if haven't explored much
        if hasattr(agent, "known_map"):
            known_percentage = 0.1  # Simplified calculation
            base_utility *= 1.0 - known_percentage * 0.5

        return base_utility


class GatherResourceGoal(Goal):
    def __init__(
        self, resource_type: str, target_quantity: int = 10, priority: int = 6
    ):
        super().__init__(priority, f"Gather {resource_type}")
        self.resource_type = resource_type
        self.target_quantity = target_quantity
        self.current_location: Optional[Tuple[int, int]] = None

    def is_complete(self, agent: Entity, world: World) -> bool:
        return (
            agent.inventory.get_item_count(self.resource_type.title())
            >= self.target_quantity
        )

    def is_valid(self, agent: Entity, world: World) -> bool:
        # First check agent's spatial memory
        if hasattr(agent, "spatial_memory"):
            known_resources = agent.spatial_memory.get_known_resources(
                self.resource_type, agent.position, world.current_tick
            )
            if known_resources:
                return True

        # Then check world resource manager if available
        if hasattr(world, "resource_manager"):
            available = world.resource_manager.get_available_resources(
                self.resource_type, world.current_tick, agent.position, max_distance=30
            )
            if available:
                return True

        # Fallback: quick scan of nearby tiles only (not entire world)
        agent_x, agent_y = agent.position
        search_radius = 15
        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                x, y = agent_x + dx, agent_y + dy
                if 0 <= x < world.width and 0 <= y < world.height:
                    tile = world.get_tile(x, y)
                    if tile and tile.can_gather(self.resource_type, world.current_tick):
                        return True
        return False

    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        from ..actions.gathering import (
            FishAction,
            ForageAction,
            GatherAction,
            MineAction,
            WoodcutAction,
        )
        from ..actions.movement import PathfindAction

        agent_x, agent_y = agent.position
        current_tile = world.get_tile(agent_x, agent_y)

        # If at a resource location, gather
        if current_tile and current_tile.can_gather(
            self.resource_type, world.current_tick
        ):
            # Update spatial memory
            if hasattr(agent, "spatial_memory"):
                for resource in current_tile.resources:
                    if resource.resource_type == self.resource_type:
                        agent.spatial_memory.remember_resource(
                            self.resource_type,
                            agent.position,
                            resource.quantity,
                            world.current_tick,
                        )

            if self.resource_type == "fish":
                return FishAction(agent.id)
            elif self.resource_type in ["stone", "iron_ore", "gold_ore"]:
                return MineAction(agent.id, self.resource_type)
            elif self.resource_type == "wood":
                return WoodcutAction(agent.id)
            elif self.resource_type in ["berries", "herbs"]:
                return ForageAction(agent.id, self.resource_type)
            else:
                return GatherAction(agent.id, self.resource_type)

        # Find nearest resource location (using smart lookups)
        target_position = None

        # Strategy 1: Check spatial memory first
        if hasattr(agent, "spatial_memory"):
            target_position = agent.spatial_memory.get_nearest_known_resource(
                self.resource_type, agent.position, world.current_tick
            )

        # Strategy 2: Use world resource manager if no memory or memory failed
        if not target_position and hasattr(world, "resource_manager"):
            target_position = world.resource_manager.get_nearest_resource(
                self.resource_type, agent.position, world.current_tick
            )

        # Strategy 3: Fallback to limited scanning if both above failed
        if not target_position:
            resource_locations = []
            search_radius = 20
            for dy in range(-search_radius, search_radius + 1):
                for dx in range(-search_radius, search_radius + 1):
                    x, y = agent_x + dx, agent_y + dy
                    if 0 <= x < world.width and 0 <= y < world.height:
                        tile = world.get_tile(x, y)
                        if tile and tile.can_gather(
                            self.resource_type, world.current_tick
                        ):
                            distance = math.sqrt(
                                (x - agent_x) ** 2 + (y - agent_y) ** 2
                            )
                            resource_locations.append((distance, x, y))

            if resource_locations:
                resource_locations.sort()
                target_position = (resource_locations[0][1], resource_locations[0][2])

        if target_position:
            return PathfindAction(agent.id, target_position)

        return None

    def get_utility(self, agent: Entity, world: World) -> float:
        base_utility = 0.6

        # Higher utility if we need this resource
        current_amount = agent.inventory.get_item_count(self.resource_type.title())
        need_factor = max(
            0.1, (self.target_quantity - current_amount) / self.target_quantity
        )

        # Factor in personality
        if hasattr(agent, "personality"):
            base_utility *= agent.personality.industriousness
            if agent.personality.greed > 0.6:
                base_utility *= 1.2

        return base_utility * need_factor


class CraftItemGoal(Goal):
    def __init__(self, item_name: str, quantity: int = 1, priority: int = 5):
        super().__init__(priority, f"Craft {item_name}")
        self.item_name = item_name
        self.quantity = quantity
        self.required_materials: Dict[str, int] = {}
        self.sub_goals: List[Goal] = []

    def is_complete(self, agent: Entity, world: World) -> bool:
        return agent.inventory.get_item_count(self.item_name) >= self.quantity

    def is_valid(self, agent: Entity, world: World) -> bool:
        # Check if agent has the required skills/tools
        return True  # Simplified for now

    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        from ..actions.crafting import CraftAction

        # Check if we have all materials
        if self._has_required_materials(agent):
            return CraftAction(agent.id, self.item_name, self.quantity)

        # Otherwise, we need to gather materials first
        # This would create sub-goals for gathering
        return None

    def _has_required_materials(self, agent: Entity) -> bool:
        for material, needed_qty in self.required_materials.items():
            if agent.inventory.get_item_count(material) < needed_qty:
                return False
        return True

    def get_utility(self, agent: Entity, world: World) -> float:
        base_utility = 0.5

        if hasattr(agent, "personality"):
            base_utility *= (
                agent.personality.industriousness + agent.personality.patience * 0.3
            )

        if hasattr(agent, "character_class"):
            if "craft" in agent.character_class.preferred_actions:
                base_utility *= 1.3

        return base_utility


class AttackEnemyGoal(Goal):
    def __init__(self, target_id: int, priority: int = 8):
        super().__init__(priority, "Attack Enemy")
        self.target_id = target_id
        self.last_seen_position: Optional[Tuple[int, int]] = None

    def is_complete(self, agent: Entity, world: World) -> bool:
        target = world.entities.get(self.target_id)
        return not target or not target.stats.is_alive()

    def is_valid(self, agent: Entity, world: World) -> bool:
        target = world.entities.get(self.target_id)
        if not target or not target.stats.is_alive():
            return False

        # Check if target is too far away
        if agent.distance_to(target) > 20:
            return False

        return True

    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        from ..actions.combat import MagicAttack, MeleeAttack, RangedAttack
        from ..actions.movement import PathfindAction

        target = world.entities.get(self.target_id)
        if not target:
            return None

        self.last_seen_position = target.position
        distance = agent.distance_to(target)

        # Choose attack type based on equipped weapon and distance
        weapon = agent.inventory.get_equipped_weapon()

        if weapon:
            if weapon.get_attack_type() == "ranged" and distance <= weapon.get_range():
                return RangedAttack(agent.id, self.target_id)
            elif weapon.get_attack_type() == "magic" and distance <= weapon.get_range():
                return MagicAttack(agent.id, self.target_id)
            elif distance <= 1.5:  # Changed from 2.0 to match MeleeAttack range
                return MeleeAttack(agent.id, self.target_id)
        else:
            # Unarmed combat
            if distance <= 1.5:  # Changed from 2.0 to match MeleeAttack range
                return MeleeAttack(agent.id, self.target_id)

        # Move closer to target
        return PathfindAction(agent.id, target.position)

    def get_utility(self, agent: Entity, world: World) -> float:
        target = world.entities.get(self.target_id)
        if not target:
            return 0.0

        base_utility = 0.7

        if hasattr(agent, "personality"):
            combat_desire = (
                agent.personality.bravery * 0.4 + agent.personality.aggression * 0.6
            )
            base_utility *= combat_desire

        # Consider strength difference
        agent_power = agent.stats.attack_power + agent.stats.defense
        target_power = target.stats.attack_power + target.stats.defense

        if agent_power > target_power * 1.2:
            base_utility *= 1.2  # More likely to attack if stronger
        elif agent_power < target_power * 0.8:
            base_utility *= 0.6  # Less likely if weaker

        return base_utility


class FleeFromDangerGoal(Goal):
    def __init__(self, danger_source_id: int, priority: int = 9):
        super().__init__(priority, "Flee from Danger")
        self.danger_source_id = danger_source_id
        self.safe_distance = 10

    def is_complete(self, agent: Entity, world: World) -> bool:
        danger_source = world.entities.get(self.danger_source_id)
        if not danger_source:
            return True  # Danger is gone

        distance = agent.distance_to(danger_source)
        return distance >= self.safe_distance

    def is_valid(self, agent: Entity, world: World) -> bool:
        danger_source = world.entities.get(self.danger_source_id)
        return danger_source is not None and danger_source.stats.is_alive()

    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        from ..actions.combat import FleeAction

        return FleeAction(agent.id, flee_distance=self.safe_distance)

    def get_utility(self, agent: Entity, world: World) -> float:
        danger_source = world.entities.get(self.danger_source_id)
        if not danger_source:
            return 0.0

        # High utility if in immediate danger
        distance = agent.distance_to(danger_source)
        if distance < 3:
            return 0.95

        base_utility = 0.8

        if hasattr(agent, "personality"):
            base_utility *= agent.personality.caution

        # Consider health
        health_ratio = agent.stats.get_health_percentage()
        if health_ratio < 0.3:
            base_utility *= 1.5

        return min(1.0, base_utility)


class RestGoal(Goal):
    def __init__(self, priority: int = 3):
        super().__init__(priority, "Rest")
        self.rest_duration = 10  # ticks
        self.rest_start_tick = 0

    def is_complete(self, agent: Entity, world: World) -> bool:
        if self.rest_start_tick == 0:
            return False

        rested_enough = (
            world.current_tick - self.rest_start_tick
        ) >= self.rest_duration
        stats_restored = (
            agent.stats.stamina > agent.stats.max_stamina * 0.8
            and agent.stats.health > agent.stats.max_health * 0.8
        )

        return rested_enough or stats_restored

    def is_valid(self, agent: Entity, world: World) -> bool:
        return (
            agent.stats.stamina < agent.stats.max_stamina * 0.4
            or agent.stats.health < agent.stats.max_health * 0.6
        )

    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        # Resting is passive - just wait
        if self.rest_start_tick == 0:
            self.rest_start_tick = world.current_tick

        # Restore some stats
        agent.stats.restore_stamina(2)
        agent.stats.heal(1)

        return None  # No action needed

    def get_utility(self, agent: Entity, world: World) -> float:
        stamina_ratio = agent.stats.get_stamina_percentage()
        health_ratio = agent.stats.get_health_percentage()

        # Higher utility when more tired/injured
        utility = (2.0 - stamina_ratio - health_ratio) * 0.5

        return max(0.1, min(0.9, utility))


class TradeGoal(Goal):
    """Goal for trading items with other entities"""

    def __init__(
        self,
        target_id: Optional[int] = None,
        offered_items: Optional[List[Tuple[str, int]]] = None,
        requested_items: Optional[List[Tuple[str, int]]] = None,
        priority: int = 5,
    ):
        super().__init__(priority, "Trade")
        self.target_id = target_id
        self.offered_items = offered_items or []
        self.requested_items = requested_items or []
        self.trade_offer_id: Optional[int] = None
        self.waiting_for_response = False
        self.waiting_since_tick = 0

    def is_complete(self, agent: Entity, world: World) -> bool:
        # Check if we successfully obtained the requested items
        if self.requested_items:
            for item_name, quantity in self.requested_items:
                if agent.inventory.get_item_count(item_name) < quantity:
                    return False
            return True
        # If no specific request, complete after making any trade
        return self.trade_offer_id is not None and not self.waiting_for_response

    def is_valid(self, agent: Entity, world: World) -> bool:
        # Check if we still have the offered items
        for item_name, quantity in self.offered_items:
            if not agent.inventory.has_item(item_name, quantity):
                return False

        # Check if target still exists and is nearby
        if self.target_id:
            target = world.entities.get(self.target_id)
            if not target or not target.stats.is_alive():
                return False
            if agent.distance_to(target) > 10:
                return False

        return True

    def get_next_action(self, agent: Entity, world: World) -> Optional[Action]:
        from ..actions.movement import PathfindAction

        # If we don't have a target, find a nearby agent to trade with
        if not self.target_id:
            self._find_trade_partner(agent, world)

        if not self.target_id:
            return None

        target = world.entities.get(self.target_id)
        if not target:
            return None

        # If too far away, move closer
        distance = agent.distance_to(target)
        if distance > 2:
            return PathfindAction(agent.id, target.position)

        # If we're close enough and not waiting for response, create trade offer
        if not self.waiting_for_response and not self.trade_offer_id:
            # This would integrate with the trading system
            # For now, we just mark that we're ready to trade
            self.waiting_for_response = True
            self.waiting_since_tick = world.current_tick
            # In a full implementation, this would create a TradeOffer through the TradingSystem

        # If waiting too long, give up
        if (
            self.waiting_for_response
            and (world.current_tick - self.waiting_since_tick) > 50
        ):
            self.waiting_for_response = False
            self.target_id = None

        return None  # Trading itself doesn't require an action, just proximity

    def _find_trade_partner(self, agent: Entity, world: World) -> None:
        """Find a nearby entity to trade with"""
        min_distance = float("inf")
        best_target = None

        for entity_id, entity in world.entities.items():
            if entity_id == agent.id:
                continue
            if not entity.stats.is_alive():
                continue
            # Only trade with other agents, not hostile NPCs
            if hasattr(entity, "npc_type") and entity.npc_type in [
                "hostile",
                "aggressive",
            ]:
                continue

            distance = agent.distance_to(entity)
            if distance < min_distance and distance < 15:
                min_distance = distance
                best_target = entity_id

        if best_target:
            self.target_id = best_target

    def get_utility(self, agent: Entity, world: World) -> float:
        base_utility = 0.4

        # Higher utility for social agents
        if hasattr(agent, "personality"):
            base_utility *= agent.personality.sociability * 0.8 + 0.4

        # Higher utility if we have excess items to trade
        if self.offered_items:
            base_utility *= 1.2

        # Higher utility if we need the requested items
        if self.requested_items:
            base_utility *= 1.3

        return min(1.0, base_utility)
