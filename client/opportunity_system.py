"""
Opportunity System for Dynamic Agent Behavior

This system allows agents to detect and evaluate opportunities in their environment,
enabling them to dynamically adapt their behavior based on what's available around them.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class OpportunityType(Enum):
    """Types of opportunities agents can detect and pursue"""

    RESOURCE = "resource"  # Resource gathering opportunities (wood, fish, etc.)
    COMBAT = "combat"  # Combat opportunities (enemies to fight)
    TRADE = "trade"  # Trading opportunities (other agents with needed items)
    SOCIAL = "social"  # Social interaction opportunities (cooperation, help)
    EMERGENCY = "emergency"  # Emergency situations (low health, danger)
    EXPLORATION = "exploration"  # Exploration opportunities (unknown areas)


@dataclass
class Opportunity:
    """Represents a single opportunity available to an agent"""

    opportunity_id: str
    opportunity_type: OpportunityType
    position: Tuple[float, float]
    target_id: Optional[str] = None  # For agent-specific opportunities

    # Opportunity properties
    value: float = 1.0  # Base value of the opportunity
    urgency: float = 1.0  # How urgent this opportunity is (0-10)
    duration: float = 30.0  # How long opportunity lasts (seconds)
    required_distance: float = 2.0  # Distance needed to act on opportunity

    # Metadata
    created_time: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)  # Additional opportunity data

    def is_expired(self) -> bool:
        """Check if this opportunity has expired"""
        return (time.time() - self.created_time) > self.duration

    def distance_to(self, agent_x: float, agent_y: float) -> float:
        """Calculate distance from agent to this opportunity"""
        dx = self.position[0] - agent_x
        dy = self.position[1] - agent_y
        return math.sqrt(dx * dx + dy * dy)

    def is_within_range(self, agent_x: float, agent_y: float) -> bool:
        """Check if agent is close enough to act on this opportunity"""
        return self.distance_to(agent_x, agent_y) <= self.required_distance


class OpportunityDetector:
    """Detects opportunities in the agent's environment"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.detection_ranges = {
            OpportunityType.RESOURCE: 8.0,
            OpportunityType.COMBAT: 12.0,
            OpportunityType.TRADE: 10.0,
            OpportunityType.SOCIAL: 15.0,
            OpportunityType.EMERGENCY: 20.0,
            OpportunityType.EXPLORATION: 6.0,
        }

    def detect_opportunities(
        self,
        agent,
        visible_entities: List[Dict[str, Any]],
        terrain_data: Optional[Dict[Tuple[int, int], Any]] = None,
    ) -> List[Opportunity]:
        """
        Detect all opportunities available to the agent

        Args:
            agent: The agent detecting opportunities
            visible_entities: List of entities the agent can see
            terrain_data: Terrain data for resource opportunities

        Returns:
            List of detected opportunities
        """
        opportunities = []
        current_time = time.time()

        # Detect resource opportunities
        opportunities.extend(
            self._detect_resource_opportunities(agent, visible_entities, terrain_data)
        )

        # Detect combat opportunities
        opportunities.extend(self._detect_combat_opportunities(agent, visible_entities))

        # Detect trade opportunities
        opportunities.extend(self._detect_trade_opportunities(agent, visible_entities))

        # Detect social opportunities
        opportunities.extend(self._detect_social_opportunities(agent, visible_entities))

        # Detect emergency situations
        opportunities.extend(
            self._detect_emergency_opportunities(agent, visible_entities)
        )

        # Detect exploration opportunities
        opportunities.extend(self._detect_exploration_opportunities(agent))

        logger.debug(
            f"Agent {agent.id[:8]} detected {len(opportunities)} opportunities"
        )
        return opportunities

    def _detect_resource_opportunities(
        self,
        agent,
        visible_entities: List[Dict[str, Any]],
        terrain_data: Optional[Dict[Tuple[int, int], Any]],
    ) -> List[Opportunity]:
        """Detect resource gathering opportunities"""
        opportunities = []
        detection_range = self.detection_ranges[OpportunityType.RESOURCE]

        # Check for harvestable resources in visible entities
        for entity in visible_entities:
            if entity.get("type") in ["wood", "fish", "ore", "plant"]:
                distance = math.sqrt(
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                )
                if distance <= detection_range:
                    opportunity = Opportunity(
                        opportunity_id=f"resource_{entity['id']}",
                        opportunity_type=OpportunityType.RESOURCE,
                        position=(entity["x"], entity["y"]),
                        target_id=entity["id"],
                        value=self._calculate_resource_value(entity, agent),
                        urgency=3.0,  # Moderate urgency
                        duration=60.0,  # Resources last longer
                        required_distance=2.5,
                        data={"resource_type": entity.get("type"), "entity": entity},
                    )
                    opportunities.append(opportunity)

        # Check for terrain-based resources if we have terrain data
        if terrain_data and hasattr(agent, "agent_map") and agent.agent_map:
            opportunities.extend(
                self._detect_terrain_resources(agent, terrain_data, detection_range)
            )

        return opportunities

    def _detect_combat_opportunities(
        self, agent, visible_entities: List[Dict[str, Any]]
    ) -> List[Opportunity]:
        """Detect combat opportunities"""
        opportunities = []
        detection_range = self.detection_ranges[OpportunityType.COMBAT]

        # Don't look for combat if health is too low
        if agent.health < 30.0:
            return opportunities

        for entity in visible_entities:
            entity_type = entity.get("agent_type", entity.get("type", ""))

            # Check if this is a valid combat target
            if self._is_valid_combat_target(entity_type, agent):
                distance = math.sqrt(
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                )
                if distance <= detection_range:
                    opportunity = Opportunity(
                        opportunity_id=f"combat_{entity['id']}",
                        opportunity_type=OpportunityType.COMBAT,
                        position=(entity["x"], entity["y"]),
                        target_id=entity["id"],
                        value=self._calculate_combat_value(entity, agent),
                        urgency=6.0,  # High urgency
                        duration=10.0,  # Combat opportunities are short-lived
                        required_distance=3.0,
                        data={
                            "enemy_type": entity_type,
                            "enemy_health": entity.get("health", 100),
                        },
                    )
                    opportunities.append(opportunity)

        return opportunities

    def _detect_trade_opportunities(
        self, agent, visible_entities: List[Dict[str, Any]]
    ) -> List[Opportunity]:
        """Detect trading opportunities"""
        opportunities = []
        detection_range = self.detection_ranges[OpportunityType.TRADE]

        for entity in visible_entities:
            # Only consider other agents for trading
            if entity.get("agent_type") and entity["id"] != agent.id:
                distance = math.sqrt(
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                )
                if distance <= detection_range:
                    opportunity = Opportunity(
                        opportunity_id=f"trade_{entity['id']}",
                        opportunity_type=OpportunityType.TRADE,
                        position=(entity["x"], entity["y"]),
                        target_id=entity["id"],
                        value=self._calculate_trade_value(entity, agent),
                        urgency=2.0,  # Low urgency - trades can wait
                        duration=45.0,  # Moderate duration
                        required_distance=5.0,  # Trading range
                        data={
                            "trader_type": entity.get("agent_type"),
                            "trader_id": entity["id"],
                        },
                    )
                    opportunities.append(opportunity)

        return opportunities

    def _detect_social_opportunities(
        self, agent, visible_entities: List[Dict[str, Any]]
    ) -> List[Opportunity]:
        """Detect social interaction opportunities"""
        opportunities = []
        detection_range = self.detection_ranges[OpportunityType.SOCIAL]

        for entity in visible_entities:
            # Look for agents that might need help or cooperation
            if entity.get("agent_type") and entity["id"] != agent.id:
                distance = math.sqrt(
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                )
                if distance <= detection_range:
                    # Check if this agent might need help (low health, being attacked)
                    needs_help = entity.get("health", 100) < 50.0

                    if needs_help or self._should_cooperate_with(entity, agent):
                        opportunity = Opportunity(
                            opportunity_id=f"social_{entity['id']}",
                            opportunity_type=OpportunityType.SOCIAL,
                            position=(entity["x"], entity["y"]),
                            target_id=entity["id"],
                            value=self._calculate_social_value(entity, agent),
                            urgency=4.0 if needs_help else 2.0,
                            duration=30.0,
                            required_distance=8.0,  # Social interaction range
                            data={
                                "needs_help": needs_help,
                                "ally_type": entity.get("agent_type"),
                            },
                        )
                        opportunities.append(opportunity)

        return opportunities

    def _detect_emergency_opportunities(
        self, agent, visible_entities: List[Dict[str, Any]]
    ) -> List[Opportunity]:
        """Detect emergency situations requiring immediate attention"""
        opportunities = []

        # Low health emergency
        if agent.health < 25.0:
            # Look for safe areas or healing opportunities
            safe_x, safe_y = self._find_safe_position(agent, visible_entities)
            opportunity = Opportunity(
                opportunity_id="emergency_low_health",
                opportunity_type=OpportunityType.EMERGENCY,
                position=(safe_x, safe_y),
                value=10.0,  # Very high value
                urgency=10.0,  # Maximum urgency
                duration=5.0,  # Short duration - act now!
                required_distance=1.0,
                data={"emergency_type": "low_health", "current_health": agent.health},
            )
            opportunities.append(opportunity)

        # Being surrounded by enemies
        nearby_enemies = [
            e
            for e in visible_entities
            if self._is_valid_combat_target(
                e.get("agent_type", e.get("type", "")), agent
            )
            and math.sqrt((e["x"] - agent.x) ** 2 + (e["y"] - agent.y) ** 2) < 5.0
        ]

        if len(nearby_enemies) >= 2:
            # Emergency escape
            escape_x, escape_y = self._find_escape_position(agent, nearby_enemies)
            opportunity = Opportunity(
                opportunity_id="emergency_surrounded",
                opportunity_type=OpportunityType.EMERGENCY,
                position=(escape_x, escape_y),
                value=9.0,
                urgency=9.0,
                duration=3.0,
                required_distance=1.0,
                data={
                    "emergency_type": "surrounded",
                    "enemy_count": len(nearby_enemies),
                },
            )
            opportunities.append(opportunity)

        return opportunities

    def _detect_exploration_opportunities(self, agent) -> List[Opportunity]:
        """Detect exploration opportunities"""
        opportunities = []

        # Only detect exploration if agent has a map
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return opportunities

        # Find nearest unexplored area
        frontier = self._find_exploration_frontier(agent)
        if frontier:
            opportunity = Opportunity(
                opportunity_id="exploration_frontier",
                opportunity_type=OpportunityType.EXPLORATION,
                position=frontier,
                value=3.0,
                urgency=1.0,  # Low urgency
                duration=120.0,  # Long duration
                required_distance=2.0,
                data={"frontier_position": frontier},
            )
            opportunities.append(opportunity)

        return opportunities

    def _calculate_resource_value(self, entity: Dict[str, Any], agent) -> float:
        """Calculate the value of a resource opportunity"""
        base_value = 5.0
        resource_type = entity.get("type", "")

        # Adjust value based on agent's personality and needs
        if hasattr(agent, "personality"):
            if resource_type == "wood" and hasattr(agent.personality, "foraging"):
                base_value *= agent.personality.foraging / 5.0
            elif resource_type == "fish" and hasattr(agent.personality, "fishing"):
                base_value *= agent.personality.fishing / 5.0

        # Adjust for distance (closer is better)
        distance = math.sqrt(
            (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
        )
        distance_factor = max(0.1, 1.0 - (distance / 20.0))

        return base_value * distance_factor

    def _calculate_combat_value(self, entity: Dict[str, Any], agent) -> float:
        """Calculate the value of a combat opportunity"""
        if not hasattr(agent, "personality"):
            return 3.0

        base_value = (
            agent.personality.combat if hasattr(agent.personality, "combat") else 3.0
        )

        # Adjust based on enemy health (weaker enemies are more valuable)
        enemy_health = entity.get("health", 100)
        health_factor = max(0.5, 2.0 - (enemy_health / 100.0))

        # Adjust based on agent's health (don't fight when weak)
        agent_health_factor = min(1.0, agent.health / 50.0)

        return base_value * health_factor * agent_health_factor

    def _calculate_trade_value(self, entity: Dict[str, Any], agent) -> float:
        """Calculate the value of a trade opportunity"""
        if not hasattr(agent, "personality"):
            return 2.0

        base_value = (
            agent.personality.social if hasattr(agent.personality, "social") else 2.0
        )

        # Higher value if we have complementary needs
        # This is a simplified calculation - could be enhanced with inventory analysis
        return base_value

    def _calculate_social_value(self, entity: Dict[str, Any], agent) -> float:
        """Calculate the value of a social opportunity"""
        if not hasattr(agent, "personality"):
            return 2.0

        base_value = (
            agent.personality.cooperativeness
            if hasattr(agent.personality, "cooperativeness")
            else 2.0
        )

        # Higher value if the other agent needs help
        if entity.get("health", 100) < 50.0:
            base_value *= 1.5

        return base_value

    def _is_valid_combat_target(self, entity_type: str, agent) -> bool:
        """Check if an entity type is a valid combat target"""
        if not hasattr(agent, "personality"):
            return entity_type == "enemy"

        # Cooperative agents only fight designated enemies
        if (
            hasattr(agent.personality, "cooperativeness")
            and agent.personality.cooperativeness > 7.0
        ):
            return entity_type == "enemy"

        # Less cooperative agents might fight other players too
        return entity_type in ["enemy", "player", "npc"]

    def _should_cooperate_with(self, entity: Dict[str, Any], agent) -> bool:
        """Check if agent should consider cooperating with another agent"""
        if not hasattr(agent, "personality"):
            return True

        cooperation = getattr(agent.personality, "cooperativeness", 5.0)
        return cooperation > 4.0

    def _find_safe_position(
        self, agent, visible_entities: List[Dict[str, Any]]
    ) -> Tuple[float, float]:
        """Find a safe position away from enemies"""
        # Simple implementation - move away from nearest enemy
        nearest_enemy = None
        nearest_distance = float("inf")

        for entity in visible_entities:
            if self._is_valid_combat_target(
                entity.get("agent_type", entity.get("type", "")), agent
            ):
                distance = math.sqrt(
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                )
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_enemy = entity

        if nearest_enemy:
            # Move in opposite direction
            dx = agent.x - nearest_enemy["x"]
            dy = agent.y - nearest_enemy["y"]
            length = math.sqrt(dx * dx + dy * dy)
            if length > 0:
                dx /= length
                dy /= length
                return (agent.x + dx * 10.0, agent.y + dy * 10.0)

        # Default safe position
        return (agent.x, agent.y)

    def _find_escape_position(
        self, agent, enemies: List[Dict[str, Any]]
    ) -> Tuple[float, float]:
        """Find an escape position away from multiple enemies"""
        # Calculate center of enemies
        center_x = sum(e["x"] for e in enemies) / len(enemies)
        center_y = sum(e["y"] for e in enemies) / len(enemies)

        # Move away from center
        dx = agent.x - center_x
        dy = agent.y - center_y
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            dx /= length
            dy /= length
            return (agent.x + dx * 15.0, agent.y + dy * 15.0)

        # Default escape position
        return (agent.x + 10.0, agent.y + 10.0)

    def _find_exploration_frontier(self, agent) -> Optional[Tuple[float, float]]:
        """Find the nearest exploration frontier"""
        if not hasattr(agent, "agent_map") or not agent.agent_map:
            return None

        # This is a simplified implementation
        # In a full implementation, we'd analyze the agent's map for unexplored areas
        return (agent.x + 5.0, agent.y + 5.0)

    def _detect_terrain_resources(
        self, agent, terrain_data: Dict[Tuple[int, int], Any], detection_range: float
    ) -> List[Opportunity]:
        """Detect resources in terrain data"""
        opportunities = []

        # Check terrain tiles within detection range
        for (tile_x, tile_y), tile_type in terrain_data.items():
            distance = math.sqrt((tile_x - agent.x) ** 2 + (tile_y - agent.y) ** 2)
            if distance <= detection_range:
                if self._is_harvestable_terrain(tile_type):
                    opportunity = Opportunity(
                        opportunity_id=f"terrain_{tile_x}_{tile_y}",
                        opportunity_type=OpportunityType.RESOURCE,
                        position=(float(tile_x), float(tile_y)),
                        value=self._calculate_terrain_value(tile_type, agent),
                        urgency=2.0,
                        duration=90.0,  # Terrain resources last long
                        required_distance=1.5,
                        data={"terrain_type": tile_type, "tile_pos": (tile_x, tile_y)},
                    )
                    opportunities.append(opportunity)

        return opportunities

    def _is_harvestable_terrain(self, tile_type) -> bool:
        """Check if a terrain tile can be harvested"""
        # Import here to avoid circular imports
        try:
            from world.tiles import TileType

            return tile_type in [TileType.WOOD, TileType.WATER]
        except ImportError:
            # Fallback for string-based tile types
            return str(tile_type).lower() in ["wood", "water", "forest"]

    def _calculate_terrain_value(self, tile_type, agent) -> float:
        """Calculate value of terrain-based resources"""
        base_value = 4.0

        if hasattr(agent, "personality"):
            try:
                from world.tiles import TileType

                if tile_type == TileType.WOOD and hasattr(
                    agent.personality, "foraging"
                ):
                    base_value *= agent.personality.foraging / 5.0
                elif tile_type == TileType.WATER and hasattr(
                    agent.personality, "fishing"
                ):
                    base_value *= agent.personality.fishing / 5.0
            except ImportError:
                pass

        return base_value


class OpportunityEvaluator:
    """Evaluates and scores opportunities for an agent"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    def evaluate_opportunities(
        self, agent, opportunities: List[Opportunity]
    ) -> List[Tuple[Opportunity, float]]:
        """
        Evaluate and score all opportunities for an agent

        Returns:
            List of (opportunity, utility_score) tuples sorted by utility (highest first)
        """
        scored_opportunities = []

        for opportunity in opportunities:
            if opportunity.is_expired():
                continue

            utility = self._calculate_utility(agent, opportunity)
            scored_opportunities.append((opportunity, utility))

        # Sort by utility score (highest first)
        scored_opportunities.sort(key=lambda x: x[1], reverse=True)

        logger.debug(
            f"Agent {agent.id[:8]} evaluated {len(scored_opportunities)} opportunities"
        )
        return scored_opportunities

    def _calculate_utility(self, agent, opportunity: Opportunity) -> float:
        """Calculate utility score for an opportunity"""
        base_utility = opportunity.value

        # Distance penalty (closer is better)
        distance = opportunity.distance_to(agent.x, agent.y)
        distance_factor = max(0.1, 1.0 - (distance / 30.0))

        # Urgency multiplier
        urgency_factor = 1.0 + (opportunity.urgency / 10.0)

        # Personality alignment
        personality_factor = self._get_personality_factor(agent, opportunity)

        # Current needs factor
        needs_factor = self._get_needs_factor(agent, opportunity)

        # Context factor (danger, resources nearby, etc.)
        context_factor = self._get_context_factor(agent, opportunity)

        utility = (
            base_utility
            * distance_factor
            * urgency_factor
            * personality_factor
            * needs_factor
            * context_factor
        )

        logger.debug(
            f"Opportunity {opportunity.opportunity_id} utility: {utility:.2f} "
            f"(base:{base_utility:.1f} dist:{distance_factor:.2f} "
            f"urgency:{urgency_factor:.2f} personality:{personality_factor:.2f})"
        )

        return utility

    def _get_personality_factor(self, agent, opportunity: Opportunity) -> float:
        """Get personality alignment factor for an opportunity"""
        if not hasattr(agent, "personality"):
            return 1.0

        personality = agent.personality

        if opportunity.opportunity_type == OpportunityType.COMBAT:
            return getattr(personality, "combat", 5.0) / 5.0
        elif opportunity.opportunity_type == OpportunityType.RESOURCE:
            resource_type = opportunity.data.get("resource_type", "")
            if resource_type == "wood":
                return getattr(personality, "foraging", 5.0) / 5.0
            elif resource_type == "fish":
                return getattr(personality, "fishing", 5.0) / 5.0
            else:
                return 1.0
        elif opportunity.opportunity_type == OpportunityType.TRADE:
            return getattr(personality, "social", 5.0) / 5.0
        elif opportunity.opportunity_type == OpportunityType.SOCIAL:
            return getattr(personality, "cooperativeness", 5.0) / 5.0
        elif opportunity.opportunity_type == OpportunityType.EXPLORATION:
            return getattr(personality, "exploration", 5.0) / 5.0
        elif opportunity.opportunity_type == OpportunityType.EMERGENCY:
            return 2.0  # Emergencies are always important

        return 1.0

    def _get_needs_factor(self, agent, opportunity: Opportunity) -> float:
        """Get factor based on agent's current needs"""
        # Health-based needs
        if opportunity.opportunity_type == OpportunityType.EMERGENCY:
            if opportunity.data.get("emergency_type") == "low_health":
                return 3.0  # Very high need when health is low

        # Combat avoidance when weak
        if (
            opportunity.opportunity_type == OpportunityType.COMBAT
            and agent.health < 40.0
        ):
            return 0.3  # Low need for combat when weak

        # Resource needs based on inventory (simplified)
        if opportunity.opportunity_type == OpportunityType.RESOURCE:
            return 1.2  # Slightly higher need for resources

        return 1.0

    def _get_context_factor(self, agent, opportunity: Opportunity) -> float:
        """Get factor based on current context"""
        context_factor = 1.0

        # Reduce utility if in dangerous area
        if hasattr(agent, "visible_entities"):
            nearby_enemies = sum(
                1
                for entity in agent.visible_entities
                if entity.get("agent_type") == "enemy"
                and math.sqrt(
                    (entity["x"] - agent.x) ** 2 + (entity["y"] - agent.y) ** 2
                )
                < 8.0
            )
            if nearby_enemies > 0:
                # Reduce non-emergency opportunities when enemies nearby
                if opportunity.opportunity_type != OpportunityType.EMERGENCY:
                    context_factor *= max(0.3, 1.0 - (nearby_enemies * 0.2))

        return context_factor


class OpportunitySystem:
    """Main opportunity system coordinator"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.detector = OpportunityDetector(agent_id)
        self.evaluator = OpportunityEvaluator(agent_id)

        self.current_opportunities: List[Opportunity] = []
        self.last_detection_time = 0.0
        self.detection_interval = 0.5  # Detect opportunities every 500ms

    def update(
        self,
        agent,
        visible_entities: List[Dict[str, Any]],
        terrain_data: Optional[Dict[Tuple[int, int], Any]] = None,
    ) -> List[Tuple[Opportunity, float]]:
        """
        Update opportunity system and return scored opportunities

        Returns:
            List of (opportunity, utility_score) tuples sorted by utility
        """
        current_time = time.time()

        # Only detect opportunities at specified intervals
        if current_time - self.last_detection_time >= self.detection_interval:
            self.current_opportunities = self.detector.detect_opportunities(
                agent, visible_entities, terrain_data
            )
            self.last_detection_time = current_time

        # Always evaluate current opportunities (they may change based on agent state)
        return self.evaluator.evaluate_opportunities(agent, self.current_opportunities)

    def get_best_opportunity(
        self,
        agent,
        visible_entities: List[Dict[str, Any]],
        terrain_data: Optional[Dict[Tuple[int, int], Any]] = None,
    ) -> Optional[Tuple[Opportunity, float]]:
        """Get the best opportunity available to the agent"""
        scored_opportunities = self.update(agent, visible_entities, terrain_data)
        return scored_opportunities[0] if scored_opportunities else None

    def get_opportunities_by_type(
        self, opportunity_type: OpportunityType
    ) -> List[Opportunity]:
        """Get all current opportunities of a specific type"""
        return [
            opp
            for opp in self.current_opportunities
            if opp.opportunity_type == opportunity_type
        ]

    def clear_opportunities(self):
        """Clear all current opportunities"""
        self.current_opportunities.clear()

    def set_detection_interval(self, interval: float):
        """Set how often to detect new opportunities"""
        self.detection_interval = max(0.1, interval)
