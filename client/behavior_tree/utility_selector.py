"""
Utility-Based Decision Making for Behavior Trees

This module implements UtilitySelector nodes that choose actions based on utility scoring
rather than rigid priorities, enabling more flexible and context-aware agent behavior.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from .nodes.base import BehaviorNode, NodeStatus

logger = logging.getLogger(__name__)


class UtilityFunction:
    """Represents a utility function for scoring behavior options"""

    def __init__(self, name: str, base_utility: float = 1.0):
        self.name = name
        self.base_utility = base_utility
        self.factors: List[Callable[[Any, BehaviorNode], float]] = []

    def add_factor(self, factor_func: Callable[[Any, BehaviorNode], float]):
        """Add a factor function that modifies utility"""
        self.factors.append(factor_func)
        return self

    def calculate_utility(self, agent: Any, node: BehaviorNode) -> float:
        """Calculate total utility for this node given an agent"""
        utility = self.base_utility

        for factor in self.factors:
            try:
                factor_value = factor(agent, node)
                utility *= factor_value
            except Exception as e:
                logger.warning(f"Error calculating utility factor for {self.name}: {e}")
                # Continue with reduced utility rather than failing
                utility *= 0.5

        return max(0.0, utility)


class UtilitySelector(BehaviorNode):
    """
    Behavior tree node that selects children based on utility scoring.

    Unlike PrioritySelector which has fixed ordering, UtilitySelector
    dynamically evaluates each child's utility and selects the best option.
    """

    def __init__(self, name: str, children: List[BehaviorNode]):
        super().__init__(name)
        self.children = children
        self.utility_functions: Dict[str, UtilityFunction] = {}
        self.last_evaluation_time = 0.0
        self.evaluation_interval = 0.2  # Re-evaluate every 200ms
        self.current_child: Optional[BehaviorNode] = None
        self.utility_cache: Dict[str, float] = {}

        # Initialize default utility functions for each child
        for child in children:
            self._initialize_default_utility(child)

    def _initialize_default_utility(self, child: BehaviorNode):
        """Initialize default utility function for a child node"""
        utility_func = UtilityFunction(f"{child.name}_utility", base_utility=1.0)

        # Add basic factors based on node type
        if "combat" in child.name.lower():
            utility_func.add_factor(self._combat_utility_factor)
        elif "resource" in child.name.lower() or "harvest" in child.name.lower():
            utility_func.add_factor(self._resource_utility_factor)
        elif "fish" in child.name.lower():
            utility_func.add_factor(self._fishing_utility_factor)
        elif "social" in child.name.lower() or "trade" in child.name.lower():
            utility_func.add_factor(self._social_utility_factor)
        elif "exploration" in child.name.lower() or "wander" in child.name.lower():
            utility_func.add_factor(self._exploration_utility_factor)
        elif "emergency" in child.name.lower() or "flee" in child.name.lower():
            utility_func.add_factor(self._emergency_utility_factor)

        # Add common factors
        utility_func.add_factor(self._health_factor)
        utility_func.add_factor(self._opportunity_factor)

        self.utility_functions[child.name] = utility_func

    def set_utility_function(self, child_name: str, utility_func: UtilityFunction):
        """Set a custom utility function for a specific child"""
        self.utility_functions[child_name] = utility_func

    def execute(self, agent: Any, delta_time: float) -> NodeStatus:
        """Execute the utility selector logic"""
        current_time = time.time()

        # Re-evaluate utilities periodically or if no current child
        if (
            current_time - self.last_evaluation_time >= self.evaluation_interval
            or self.current_child is None
            or self.current_child.status in [NodeStatus.SUCCESS, NodeStatus.FAILURE]
        ):
            best_child = self._select_best_child(agent)
            if best_child != self.current_child:
                # Reset previous child
                if self.current_child:
                    self.current_child.reset()
                self.current_child = best_child

            self.last_evaluation_time = current_time

        # Execute current child
        if self.current_child:
            status = self.current_child.execute(agent, delta_time)

            # Update our status based on child status
            if status == NodeStatus.RUNNING:
                self.status = NodeStatus.RUNNING
            elif status == NodeStatus.SUCCESS:
                self.status = NodeStatus.SUCCESS
                self.current_child = None  # Allow re-evaluation
            elif status == NodeStatus.FAILURE:
                # Try next best option
                self.current_child = None
                self.status = NodeStatus.RUNNING
            else:
                self.status = status

            return self.status

        # No valid child found
        self.status = NodeStatus.FAILURE
        return self.status

    def _select_best_child(self, agent: Any) -> Optional[BehaviorNode]:
        """Select the child with highest utility score"""
        best_child = None
        best_utility = -1.0

        for child in self.children:
            utility = self._calculate_child_utility(agent, child)
            self.utility_cache[child.name] = utility

            if utility > best_utility:
                best_utility = utility
                best_child = child

        if best_child:
            logger.debug(
                f"UtilitySelector {self.name} selected {best_child.name} "
                f"with utility {best_utility:.2f}"
            )

        return best_child

    def _calculate_child_utility(self, agent: Any, child: BehaviorNode) -> float:
        """Calculate utility score for a specific child"""
        utility_func = self.utility_functions.get(child.name)
        if not utility_func:
            return 0.0

        return utility_func.calculate_utility(agent, child)

    def reset(self):
        """Reset the utility selector and all children"""
        super().reset()
        if self.current_child:
            self.current_child.reset()
        self.current_child = None
        self.utility_cache.clear()

    def get_debug_info(self, agent: Any) -> Dict[str, Any]:
        """Get debug information about utility calculations"""
        debug_info = {
            "current_child": self.current_child.name if self.current_child else None,
            "utility_scores": {},
            "last_evaluation": self.last_evaluation_time,
        }

        # Calculate current utilities for all children
        for child in self.children:
            utility = self._calculate_child_utility(agent, child)
            debug_info["utility_scores"][child.name] = utility

        return debug_info

    # Utility factor functions
    def _combat_utility_factor(self, agent: Any, node: BehaviorNode) -> float:
        """Calculate combat utility factor based on agent personality and health"""
        base_factor = 1.0

        # Personality influence
        if hasattr(agent, "personality") and hasattr(agent.personality, "combat"):
            base_factor = agent.personality.combat / 5.0  # Normalize to ~0.0-2.0

        # Health influence - don't fight when weak
        if hasattr(agent, "health"):
            if agent.health < 30.0:
                base_factor *= 0.2  # Very low when health is critical
            elif agent.health < 60.0:
                base_factor *= 0.6  # Reduced when health is low

        # Enemy presence influence
        if hasattr(agent, "visible_entities"):
            nearby_enemies = sum(
                1
                for entity in agent.visible_entities
                if entity.get("agent_type") == "enemy"
                and self._distance_to_entity(agent, entity) < 8.0
            )
            if nearby_enemies > 0:
                base_factor *= min(
                    2.0, 1.0 + nearby_enemies * 0.3
                )  # Increase with more enemies

        return base_factor

    def _resource_utility_factor(self, agent: Any, node: BehaviorNode) -> float:
        """Calculate resource gathering utility factor"""
        base_factor = 1.0

        # Personality influence
        if hasattr(agent, "personality") and hasattr(agent.personality, "foraging"):
            base_factor = agent.personality.foraging / 5.0

        # Resource availability influence
        if hasattr(agent, "visible_entities"):
            nearby_resources = sum(
                1
                for entity in agent.visible_entities
                if entity.get("type") in ["wood", "ore", "plant"]
                and self._distance_to_entity(agent, entity) < 10.0
            )
            if nearby_resources > 0:
                base_factor *= min(2.0, 1.0 + nearby_resources * 0.2)

        # Inventory space influence (if available)
        if hasattr(agent, "inventory") and hasattr(agent.inventory, "is_full"):
            if agent.inventory.is_full():
                base_factor *= 0.1  # Very low utility when inventory is full

        return base_factor

    def _fishing_utility_factor(self, agent: Any, node: BehaviorNode) -> float:
        """Calculate fishing utility factor"""
        base_factor = 1.0

        # Personality influence
        if hasattr(agent, "personality") and hasattr(agent.personality, "fishing"):
            base_factor = agent.personality.fishing / 5.0

        # Water proximity influence
        if hasattr(agent, "agent_map") and agent.agent_map:
            # Check for nearby water tiles
            water_nearby = self._check_nearby_water(agent)
            if not water_nearby:
                base_factor *= 0.1  # Very low utility if no water nearby

        # Visible fish influence
        if hasattr(agent, "visible_entities"):
            nearby_fish = sum(
                1
                for entity in agent.visible_entities
                if entity.get("type") == "fish"
                and self._distance_to_entity(agent, entity) < 5.0
            )
            if nearby_fish > 0:
                base_factor *= min(2.0, 1.0 + nearby_fish * 0.3)

        return base_factor

    def _social_utility_factor(self, agent: Any, node: BehaviorNode) -> float:
        """Calculate social interaction utility factor"""
        base_factor = 1.0

        # Personality influence
        if hasattr(agent, "personality"):
            if hasattr(agent.personality, "social"):
                base_factor *= agent.personality.social / 5.0
            if hasattr(agent.personality, "cooperativeness"):
                base_factor *= agent.personality.cooperativeness / 5.0

        # Other agents proximity influence
        if hasattr(agent, "visible_entities"):
            nearby_agents = sum(
                1
                for entity in agent.visible_entities
                if entity.get("agent_type") in ["player", "npc"]
                and entity.get("id") != agent.id
                and self._distance_to_entity(agent, entity) < 15.0
            )
            if nearby_agents == 0:
                base_factor *= 0.2  # Low utility if no one around to interact with
            else:
                base_factor *= min(1.5, 1.0 + nearby_agents * 0.1)

        return base_factor

    def _exploration_utility_factor(self, agent: Any, node: BehaviorNode) -> float:
        """Calculate exploration utility factor"""
        base_factor = 1.0

        # Personality influence
        if hasattr(agent, "personality") and hasattr(agent.personality, "exploration"):
            base_factor = agent.personality.exploration / 5.0

        # Map completion influence
        if hasattr(agent, "agent_map") and agent.agent_map:
            completion = getattr(
                agent.agent_map, "get_map_completion_percentage", lambda: 50.0
            )()
            if completion > 80.0:
                base_factor *= 0.5  # Lower utility when map is mostly complete

        # Current goal influence
        if hasattr(agent, "current_target") and agent.current_target:
            base_factor *= (
                0.7  # Lower exploration utility when we have a specific target
            )

        return base_factor

    def _emergency_utility_factor(self, agent: Any, node: BehaviorNode) -> float:
        """Calculate emergency response utility factor"""
        base_factor = 1.0

        # Health-based emergency
        if hasattr(agent, "health"):
            if agent.health < 25.0:
                base_factor = 10.0  # Very high priority
            elif agent.health < 50.0:
                base_factor = 3.0  # High priority

        # Surrounded by enemies
        if hasattr(agent, "visible_entities"):
            nearby_enemies = sum(
                1
                for entity in agent.visible_entities
                if entity.get("agent_type") == "enemy"
                and self._distance_to_entity(agent, entity) < 5.0
            )
            if nearby_enemies >= 2:
                base_factor = max(
                    base_factor, 8.0
                )  # Very high priority when surrounded

        return base_factor

    def _health_factor(self, agent: Any, node: BehaviorNode) -> float:
        """General health factor that applies to all behaviors"""
        if not hasattr(agent, "health"):
            return 1.0

        health_ratio = agent.health / getattr(agent, "max_health", 100.0)

        # Emergency behaviors get boosted when health is low
        if "emergency" in node.name.lower() or "flee" in node.name.lower():
            return max(1.0, 3.0 - health_ratio * 2.0)

        # Other behaviors get reduced when health is very low
        if health_ratio < 0.3:
            return 0.5
        elif health_ratio < 0.6:
            return 0.8

        return 1.0

    def _opportunity_factor(self, agent: Any, node: BehaviorNode) -> float:
        """Factor based on current opportunities detected by agent"""
        if not hasattr(agent, "opportunity_system") or not agent.opportunity_system:
            return 1.0

        try:
            # Get current opportunities
            opportunities = agent.opportunity_system.current_opportunities

            # Check if there are opportunities relevant to this behavior
            relevant_opportunities = []
            node_name_lower = node.name.lower()

            for opp in opportunities:
                if (
                    "combat" in node_name_lower
                    and opp.opportunity_type.value == "combat"
                ):
                    relevant_opportunities.append(opp)
                elif (
                    "resource" in node_name_lower
                    and opp.opportunity_type.value == "resource"
                ):
                    relevant_opportunities.append(opp)
                elif (
                    "fish" in node_name_lower
                    and opp.opportunity_type.value == "resource"
                ):
                    if opp.data.get("resource_type") == "fish":
                        relevant_opportunities.append(opp)
                elif "social" in node_name_lower and opp.opportunity_type.value in [
                    "social",
                    "trade",
                ]:
                    relevant_opportunities.append(opp)
                elif (
                    "emergency" in node_name_lower
                    and opp.opportunity_type.value == "emergency"
                ):
                    relevant_opportunities.append(opp)

            if relevant_opportunities:
                # Boost utility based on number and urgency of relevant opportunities
                urgency_sum = sum(opp.urgency for opp in relevant_opportunities)
                return min(3.0, 1.0 + (urgency_sum / 10.0))

        except Exception as e:
            logger.debug(f"Error calculating opportunity factor: {e}")

        return 1.0

    # Helper methods
    def _distance_to_entity(self, agent: Any, entity: Dict[str, Any]) -> float:
        """Calculate distance from agent to entity"""
        if not hasattr(agent, "x") or not hasattr(agent, "y"):
            return float("inf")

        dx = entity.get("x", 0) - agent.x
        dy = entity.get("y", 0) - agent.y
        return (dx * dx + dy * dy) ** 0.5

    def _check_nearby_water(self, agent: Any) -> bool:
        """Check if there's water nearby for fishing"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return False

        # Check tiles around agent position
        agent_tile_x = int(agent.x)
        agent_tile_y = int(agent.y)

        for dy in range(-3, 4):
            for dx in range(-3, 4):
                check_x = agent_tile_x + dx
                check_y = agent_tile_y + dy

                if agent.agent_map.is_valid_position(check_x, check_y):
                    try:
                        from world.tiles import TileType

                        if (
                            agent.agent_map.get_tile_type(check_x, check_y)
                            == TileType.WATER
                        ):
                            return True
                    except ImportError:
                        # Fallback for string-based tile types
                        tile_type = agent.agent_map.get_tile_type(check_x, check_y)
                        if str(tile_type).lower() == "water":
                            return True

        return False


class WeightedUtilitySelector(UtilitySelector):
    """
    Utility selector that allows setting static weights for children.

    Useful for maintaining some level of priority while still allowing
    dynamic adjustment based on context.
    """

    def __init__(
        self,
        name: str,
        children: List[BehaviorNode],
        weights: Optional[Dict[str, float]] = None,
    ):
        super().__init__(name, children)
        self.weights = weights or {}

    def _calculate_child_utility(self, agent: Any, child: BehaviorNode) -> float:
        """Calculate utility with static weight multiplier"""
        base_utility = super()._calculate_child_utility(agent, child)
        weight = self.weights.get(child.name, 1.0)
        return base_utility * weight


class ThresholdUtilitySelector(UtilitySelector):
    """
    Utility selector that only considers options above a minimum threshold.

    Prevents selection of very low-utility options even if they're the best available.
    """

    def __init__(
        self, name: str, children: List[BehaviorNode], minimum_utility: float = 0.1
    ):
        super().__init__(name, children)
        self.minimum_utility = minimum_utility

    def _select_best_child(self, agent: Any) -> Optional[BehaviorNode]:
        """Select best child that meets minimum utility threshold"""
        best_child = None
        best_utility = -1.0

        for child in self.children:
            utility = self._calculate_child_utility(agent, child)
            self.utility_cache[child.name] = utility

            if utility >= self.minimum_utility and utility > best_utility:
                best_utility = utility
                best_child = child

        if best_child:
            logger.debug(
                f"ThresholdUtilitySelector {self.name} selected {best_child.name} "
                f"with utility {best_utility:.2f} (threshold: {self.minimum_utility})"
            )

        return best_child
