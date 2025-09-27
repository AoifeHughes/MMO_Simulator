"""
Context Manager for Agent Environmental Awareness

This module provides agents with sophisticated environmental awareness by tracking
and analyzing contextual information about their surroundings, including danger levels,
resource density, social dynamics, and strategic opportunities.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DangerLevel(Enum):
    """Levels of danger in the environment"""
    SAFE = "safe"           # No threats detected
    LOW = "low"             # Minor threats, manageable
    MODERATE = "moderate"   # Significant threats, caution advised
    HIGH = "high"           # Major threats, evasive action recommended
    CRITICAL = "critical"   # Extreme danger, immediate escape required


class ContextType(Enum):
    """Types of environmental context"""
    DANGER = "danger"
    RESOURCE = "resource"
    SOCIAL = "social"
    STRATEGIC = "strategic"
    EXPLORATION = "exploration"


@dataclass
class ContextualArea:
    """Represents a contextual area with specific properties"""
    area_id: str
    center: Tuple[float, float]
    radius: float
    context_type: ContextType

    # Context properties
    danger_level: DangerLevel = DangerLevel.SAFE
    resource_density: float = 0.0
    social_activity: float = 0.0
    strategic_value: float = 0.0

    # Metadata
    created_time: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    confidence: float = 1.0  # How confident we are in this assessment

    # Associated entities
    entities: Set[str] = field(default_factory=set)

    def is_position_inside(self, x: float, y: float) -> bool:
        """Check if a position is inside this contextual area"""
        dx = x - self.center[0]
        dy = y - self.center[1]
        distance = math.sqrt(dx * dx + dy * dy)
        return distance <= self.radius

    def get_distance_to(self, x: float, y: float) -> float:
        """Get distance from position to area center"""
        dx = x - self.center[0]
        dy = y - self.center[1]
        return math.sqrt(dx * dx + dy * dy)

    def is_expired(self, max_age: float = 300.0) -> bool:
        """Check if this context area is too old to be reliable"""
        return (time.time() - self.last_updated) > max_age

    def update_from_entities(self, entities: List[Dict[str, Any]]):
        """Update context properties based on current entities"""
        self.last_updated = time.time()
        self.entities.clear()

        enemy_count = 0
        resource_count = 0
        ally_count = 0

        for entity in entities:
            if self.is_position_inside(entity.get("x", 0), entity.get("y", 0)):
                self.entities.add(entity.get("id", "unknown"))

                entity_type = entity.get("agent_type", entity.get("type", ""))

                if entity_type == "enemy":
                    enemy_count += 1
                elif entity_type in ["wood", "fish", "ore", "plant"]:
                    resource_count += 1
                elif entity_type in ["player", "npc"]:
                    ally_count += 1

        # Update danger level based on enemies
        if enemy_count >= 3:
            self.danger_level = DangerLevel.CRITICAL
        elif enemy_count >= 2:
            self.danger_level = DangerLevel.HIGH
        elif enemy_count >= 1:
            self.danger_level = DangerLevel.MODERATE
        else:
            self.danger_level = DangerLevel.SAFE

        # Update resource density (normalize by area)
        area_size = math.pi * self.radius * self.radius
        self.resource_density = resource_count / max(1.0, area_size / 100.0)

        # Update social activity
        self.social_activity = ally_count / max(1.0, area_size / 50.0)


@dataclass
class ContextSnapshot:
    """A snapshot of environmental context at a specific time and location"""
    timestamp: float
    position: Tuple[float, float]

    # Context metrics
    local_danger: DangerLevel = DangerLevel.SAFE
    resource_availability: float = 0.0
    social_density: float = 0.0
    exploration_potential: float = 0.0

    # Specific entity counts
    nearby_enemies: int = 0
    nearby_resources: int = 0
    nearby_allies: int = 0

    # Movement recommendations
    safe_directions: List[float] = field(default_factory=list)  # Angles in degrees
    resource_directions: List[float] = field(default_factory=list)
    social_directions: List[float] = field(default_factory=list)


class EnvironmentAnalyzer:
    """Analyzes environmental conditions and provides contextual insights"""

    def __init__(self):
        self.danger_detection_range = 15.0
        self.resource_detection_range = 12.0
        self.social_detection_range = 20.0

    def analyze_position(self, agent_x: float, agent_y: float,
                        visible_entities: List[Dict[str, Any]]) -> ContextSnapshot:
        """Analyze environmental context at agent's current position"""
        snapshot = ContextSnapshot(
            timestamp=time.time(),
            position=(agent_x, agent_y)
        )

        # Analyze entities by distance and type
        enemies = []
        resources = []
        allies = []

        for entity in visible_entities:
            entity_x = entity.get("x", 0)
            entity_y = entity.get("y", 0)
            distance = math.sqrt((entity_x - agent_x) ** 2 + (entity_y - agent_y) ** 2)

            entity_type = entity.get("agent_type", entity.get("type", ""))

            if entity_type == "enemy" and distance <= self.danger_detection_range:
                enemies.append((entity, distance))
            elif entity_type in ["wood", "fish", "ore", "plant"] and distance <= self.resource_detection_range:
                resources.append((entity, distance))
            elif entity_type in ["player", "npc"] and distance <= self.social_detection_range:
                allies.append((entity, distance))

        # Update counts
        snapshot.nearby_enemies = len(enemies)
        snapshot.nearby_resources = len(resources)
        snapshot.nearby_allies = len(allies)

        # Analyze danger level
        snapshot.local_danger = self._assess_danger_level(enemies, agent_x, agent_y)

        # Analyze resource availability
        snapshot.resource_availability = self._assess_resource_availability(resources)

        # Analyze social density
        snapshot.social_density = self._assess_social_density(allies)

        # Calculate movement recommendations
        snapshot.safe_directions = self._calculate_safe_directions(enemies, agent_x, agent_y)
        snapshot.resource_directions = self._calculate_resource_directions(resources, agent_x, agent_y)
        snapshot.social_directions = self._calculate_social_directions(allies, agent_x, agent_y)

        return snapshot

    def _assess_danger_level(self, enemies: List[Tuple[Dict[str, Any], float]],
                           agent_x: float, agent_y: float) -> DangerLevel:
        """Assess danger level based on nearby enemies"""
        if not enemies:
            return DangerLevel.SAFE

        # Count enemies by distance tiers
        close_enemies = sum(1 for _, dist in enemies if dist <= 5.0)
        medium_enemies = sum(1 for _, dist in enemies if 5.0 < dist <= 10.0)
        far_enemies = sum(1 for _, dist in enemies if dist > 10.0)

        # Calculate danger score
        danger_score = close_enemies * 3.0 + medium_enemies * 1.5 + far_enemies * 0.5

        if danger_score >= 6.0:
            return DangerLevel.CRITICAL
        elif danger_score >= 4.0:
            return DangerLevel.HIGH
        elif danger_score >= 2.0:
            return DangerLevel.MODERATE
        elif danger_score >= 1.0:
            return DangerLevel.LOW
        else:
            return DangerLevel.SAFE

    def _assess_resource_availability(self, resources: List[Tuple[Dict[str, Any], float]]) -> float:
        """Assess resource availability in the area"""
        if not resources:
            return 0.0

        # Weight resources by inverse distance (closer = more valuable)
        total_value = 0.0
        for resource, distance in resources:
            proximity_value = max(0.1, 1.0 - (distance / self.resource_detection_range))
            total_value += proximity_value

        # Normalize to 0-1 scale
        return min(1.0, total_value / 5.0)

    def _assess_social_density(self, allies: List[Tuple[Dict[str, Any], float]]) -> float:
        """Assess social activity density in the area"""
        if not allies:
            return 0.0

        # Weight allies by inverse distance
        total_value = 0.0
        for ally, distance in allies:
            proximity_value = max(0.1, 1.0 - (distance / self.social_detection_range))
            total_value += proximity_value

        # Normalize to 0-1 scale
        return min(1.0, total_value / 3.0)

    def _calculate_safe_directions(self, enemies: List[Tuple[Dict[str, Any], float]],
                                 agent_x: float, agent_y: float) -> List[float]:
        """Calculate directions that lead away from enemies"""
        if not enemies:
            return []  # All directions are safe

        safe_directions = []

        # Check 8 cardinal directions
        for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
            direction_safe = True

            # Check if this direction leads toward any enemy
            for enemy, distance in enemies:
                enemy_x = enemy.get("x", 0)
                enemy_y = enemy.get("y", 0)

                # Calculate angle to enemy
                dx = enemy_x - agent_x
                dy = enemy_y - agent_y
                enemy_angle = math.degrees(math.atan2(dy, dx))

                # Normalize angle to 0-360
                enemy_angle = (enemy_angle + 360) % 360

                # Check if this direction is within 45 degrees of enemy direction
                angle_diff = abs(angle - enemy_angle)
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff

                if angle_diff <= 45 and distance <= 8.0:  # Close enemy in this direction
                    direction_safe = False
                    break

            if direction_safe:
                safe_directions.append(angle)

        return safe_directions

    def _calculate_resource_directions(self, resources: List[Tuple[Dict[str, Any], float]],
                                     agent_x: float, agent_y: float) -> List[float]:
        """Calculate directions that lead toward resources"""
        directions = []

        for resource, distance in resources:
            resource_x = resource.get("x", 0)
            resource_y = resource.get("y", 0)

            dx = resource_x - agent_x
            dy = resource_y - agent_y
            angle = math.degrees(math.atan2(dy, dx))
            angle = (angle + 360) % 360  # Normalize to 0-360

            directions.append(angle)

        return directions

    def _calculate_social_directions(self, allies: List[Tuple[Dict[str, Any], float]],
                                   agent_x: float, agent_y: float) -> List[float]:
        """Calculate directions that lead toward social opportunities"""
        directions = []

        for ally, distance in allies:
            ally_x = ally.get("x", 0)
            ally_y = ally.get("y", 0)

            dx = ally_x - agent_x
            dy = ally_y - agent_y
            angle = math.degrees(math.atan2(dy, dx))
            angle = (angle + 360) % 360  # Normalize to 0-360

            directions.append(angle)

        return directions


class ContextManager:
    """
    Main context management system that tracks environmental awareness
    and provides contextual decision-making support for agents.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.analyzer = EnvironmentAnalyzer()

        # Contextual areas
        self.contextual_areas: Dict[str, ContextualArea] = {}
        self.area_counter = 0

        # History tracking
        self.context_history: List[ContextSnapshot] = []
        self.max_history_size = 50

        # Caching
        self.last_snapshot: Optional[ContextSnapshot] = None
        self.last_analysis_time = 0.0
        self.analysis_interval = 0.5  # Analyze every 500ms

        # Configuration
        self.area_cleanup_interval = 30.0  # Clean up old areas every 30 seconds
        self.last_cleanup_time = time.time()

    def update_context(self, agent_x: float, agent_y: float,
                      visible_entities: List[Dict[str, Any]],
                      terrain_data: Optional[Dict[Tuple[int, int], Any]] = None) -> ContextSnapshot:
        """
        Update contextual awareness and return current snapshot

        Args:
            agent_x: Agent's current X position
            agent_y: Agent's current Y position
            visible_entities: List of entities the agent can see
            terrain_data: Optional terrain data for environmental analysis

        Returns:
            Current context snapshot
        """
        current_time = time.time()

        # Check if we need to analyze (throttled for performance)
        if current_time - self.last_analysis_time < self.analysis_interval:
            return self.last_snapshot or self._create_empty_snapshot(agent_x, agent_y)

        # Perform environmental analysis
        snapshot = self.analyzer.analyze_position(agent_x, agent_y, visible_entities)

        # Update contextual areas
        self._update_contextual_areas(agent_x, agent_y, visible_entities)

        # Add to history
        self.context_history.append(snapshot)
        if len(self.context_history) > self.max_history_size:
            self.context_history.pop(0)

        # Cleanup old areas periodically
        if current_time - self.last_cleanup_time > self.area_cleanup_interval:
            self._cleanup_old_areas()
            self.last_cleanup_time = current_time

        # Cache and return
        self.last_snapshot = snapshot
        self.last_analysis_time = current_time

        logger.debug(f"Agent {self.agent_id[:8]} context: danger={snapshot.local_danger.value}, "
                    f"resources={snapshot.resource_availability:.2f}, "
                    f"social={snapshot.social_density:.2f}")

        return snapshot

    def get_danger_assessment(self, target_x: float, target_y: float) -> DangerLevel:
        """Get danger assessment for a specific location"""
        # Check contextual areas for danger
        max_danger = DangerLevel.SAFE

        for area in self.contextual_areas.values():
            if area.context_type == ContextType.DANGER and area.is_position_inside(target_x, target_y):
                if area.danger_level.value == "critical":
                    return DangerLevel.CRITICAL
                elif area.danger_level.value == "high" and max_danger.value in ["safe", "low", "moderate"]:
                    max_danger = DangerLevel.HIGH
                elif area.danger_level.value == "moderate" and max_danger.value in ["safe", "low"]:
                    max_danger = DangerLevel.MODERATE
                elif area.danger_level.value == "low" and max_danger.value == "safe":
                    max_danger = DangerLevel.LOW

        return max_danger

    def get_resource_density(self, center_x: float, center_y: float, radius: float = 10.0) -> float:
        """Get resource density in a specific area"""
        total_density = 0.0
        area_count = 0

        for area in self.contextual_areas.values():
            if area.context_type == ContextType.RESOURCE:
                distance = area.get_distance_to(center_x, center_y)
                if distance <= radius:
                    # Weight by proximity
                    weight = max(0.1, 1.0 - (distance / radius))
                    total_density += area.resource_density * weight
                    area_count += 1

        return total_density / max(1, area_count)

    def get_social_activity(self, center_x: float, center_y: float, radius: float = 15.0) -> float:
        """Get social activity level in a specific area"""
        total_activity = 0.0
        area_count = 0

        for area in self.contextual_areas.values():
            if area.context_type == ContextType.SOCIAL:
                distance = area.get_distance_to(center_x, center_y)
                if distance <= radius:
                    weight = max(0.1, 1.0 - (distance / radius))
                    total_activity += area.social_activity * weight
                    area_count += 1

        return total_activity / max(1, area_count)

    def find_safe_position(self, current_x: float, current_y: float,
                          search_radius: float = 20.0) -> Optional[Tuple[float, float]]:
        """Find a safe position within search radius"""
        if not self.last_snapshot or not self.last_snapshot.safe_directions:
            return None

        # Try safe directions from last snapshot
        for direction in self.last_snapshot.safe_directions:
            # Calculate position at half search radius in safe direction
            distance = search_radius * 0.5
            angle_rad = math.radians(direction)
            safe_x = current_x + distance * math.cos(angle_rad)
            safe_y = current_y + distance * math.sin(angle_rad)

            # Check if this position is actually safe
            if self.get_danger_assessment(safe_x, safe_y) in [DangerLevel.SAFE, DangerLevel.LOW]:
                return (safe_x, safe_y)

        return None

    def get_context_factors_for_behavior(self, behavior_name: str) -> Dict[str, float]:
        """Get context factors that should influence a specific behavior"""
        if not self.last_snapshot:
            return {}

        factors = {}
        behavior_lower = behavior_name.lower()

        # Combat behaviors
        if "combat" in behavior_lower or "attack" in behavior_lower:
            factors["danger_level"] = self._danger_to_numeric(self.last_snapshot.local_danger)
            factors["enemy_count"] = min(1.0, self.last_snapshot.nearby_enemies / 3.0)

        # Resource gathering behaviors
        elif "resource" in behavior_lower or "harvest" in behavior_lower or "fish" in behavior_lower:
            factors["resource_availability"] = self.last_snapshot.resource_availability
            factors["danger_modifier"] = 1.0 - (self._danger_to_numeric(self.last_snapshot.local_danger) * 0.3)

        # Social behaviors
        elif "social" in behavior_lower or "trade" in behavior_lower:
            factors["social_density"] = self.last_snapshot.social_density
            factors["ally_count"] = min(1.0, self.last_snapshot.nearby_allies / 2.0)

        # Exploration behaviors
        elif "exploration" in behavior_lower or "wander" in behavior_lower:
            factors["exploration_potential"] = self.last_snapshot.exploration_potential
            factors["safety_factor"] = 1.0 - (self._danger_to_numeric(self.last_snapshot.local_danger) * 0.5)

        # Emergency behaviors
        elif "emergency" in behavior_lower or "flee" in behavior_lower:
            factors["urgency"] = self._danger_to_numeric(self.last_snapshot.local_danger)
            factors["safe_directions_available"] = min(1.0, len(self.last_snapshot.safe_directions) / 4.0)

        return factors

    def get_movement_recommendation(self, goal_x: float, goal_y: float) -> Dict[str, Any]:
        """Get movement recommendation considering context"""
        if not self.last_snapshot:
            return {"recommended": True, "alternative": None, "reason": "no_context"}

        # Check if direct path to goal is safe
        danger_at_goal = self.get_danger_assessment(goal_x, goal_y)

        recommendation = {
            "recommended": danger_at_goal in [DangerLevel.SAFE, DangerLevel.LOW],
            "danger_level": danger_at_goal.value,
            "alternative": None,
            "reason": ""
        }

        if not recommendation["recommended"]:
            # Find alternative safe position
            if self.last_snapshot.position:
                current_x, current_y = self.last_snapshot.position
                safe_pos = self.find_safe_position(current_x, current_y)
                if safe_pos:
                    recommendation["alternative"] = safe_pos
                    recommendation["reason"] = f"goal_area_dangerous_{danger_at_goal.value}"
                else:
                    recommendation["reason"] = f"no_safe_alternative_{danger_at_goal.value}"

        return recommendation

    def _update_contextual_areas(self, agent_x: float, agent_y: float,
                               visible_entities: List[Dict[str, Any]]):
        """Update contextual areas based on current observations"""
        # Create or update danger areas around enemies
        self._update_danger_areas(visible_entities)

        # Create or update resource areas
        self._update_resource_areas(visible_entities)

        # Create or update social areas
        self._update_social_areas(visible_entities)

    def _update_danger_areas(self, visible_entities: List[Dict[str, Any]]):
        """Update danger areas based on enemy positions"""
        enemy_positions = []

        for entity in visible_entities:
            if entity.get("agent_type") == "enemy":
                enemy_positions.append((entity.get("x", 0), entity.get("y", 0)))

        # Create danger areas around enemy clusters
        for i, (ex, ey) in enumerate(enemy_positions):
            area_id = f"danger_{i}"

            if area_id in self.contextual_areas:
                area = self.contextual_areas[area_id]
                area.center = (ex, ey)
                area.update_from_entities(visible_entities)
            else:
                area = ContextualArea(
                    area_id=area_id,
                    center=(ex, ey),
                    radius=8.0,  # Danger radius around enemy
                    context_type=ContextType.DANGER
                )
                area.update_from_entities(visible_entities)
                self.contextual_areas[area_id] = area

    def _update_resource_areas(self, visible_entities: List[Dict[str, Any]]):
        """Update resource areas based on resource positions"""
        # Group resources by proximity
        resource_clusters = self._cluster_entities_by_proximity(
            [e for e in visible_entities if e.get("type") in ["wood", "fish", "ore", "plant"]],
            cluster_radius=5.0
        )

        # Update resource areas
        for i, cluster in enumerate(resource_clusters):
            area_id = f"resource_{i}"
            center_x = sum(e.get("x", 0) for e in cluster) / len(cluster)
            center_y = sum(e.get("y", 0) for e in cluster) / len(cluster)

            if area_id in self.contextual_areas:
                area = self.contextual_areas[area_id]
                area.center = (center_x, center_y)
                area.update_from_entities(visible_entities)
            else:
                area = ContextualArea(
                    area_id=area_id,
                    center=(center_x, center_y),
                    radius=6.0,
                    context_type=ContextType.RESOURCE
                )
                area.update_from_entities(visible_entities)
                self.contextual_areas[area_id] = area

    def _update_social_areas(self, visible_entities: List[Dict[str, Any]]):
        """Update social areas based on ally positions"""
        ally_clusters = self._cluster_entities_by_proximity(
            [e for e in visible_entities if e.get("agent_type") in ["player", "npc"]],
            cluster_radius=8.0
        )

        for i, cluster in enumerate(ally_clusters):
            area_id = f"social_{i}"
            center_x = sum(e.get("x", 0) for e in cluster) / len(cluster)
            center_y = sum(e.get("y", 0) for e in cluster) / len(cluster)

            if area_id in self.contextual_areas:
                area = self.contextual_areas[area_id]
                area.center = (center_x, center_y)
                area.update_from_entities(visible_entities)
            else:
                area = ContextualArea(
                    area_id=area_id,
                    center=(center_x, center_y),
                    radius=10.0,
                    context_type=ContextType.SOCIAL
                )
                area.update_from_entities(visible_entities)
                self.contextual_areas[area_id] = area

    def _cluster_entities_by_proximity(self, entities: List[Dict[str, Any]],
                                     cluster_radius: float) -> List[List[Dict[str, Any]]]:
        """Group entities into clusters based on proximity"""
        if not entities:
            return []

        clusters = []
        remaining = entities.copy()

        while remaining:
            # Start new cluster with first remaining entity
            seed = remaining.pop(0)
            cluster = [seed]
            seed_x, seed_y = seed.get("x", 0), seed.get("y", 0)

            # Find all entities within cluster radius
            i = 0
            while i < len(remaining):
                entity = remaining[i]
                entity_x, entity_y = entity.get("x", 0), entity.get("y", 0)

                distance = math.sqrt((entity_x - seed_x) ** 2 + (entity_y - seed_y) ** 2)

                if distance <= cluster_radius:
                    cluster.append(remaining.pop(i))
                else:
                    i += 1

            clusters.append(cluster)

        return clusters

    def _cleanup_old_areas(self):
        """Remove expired contextual areas"""
        current_time = time.time()
        expired_areas = []

        for area_id, area in self.contextual_areas.items():
            if area.is_expired():
                expired_areas.append(area_id)

        for area_id in expired_areas:
            del self.contextual_areas[area_id]

        if expired_areas:
            logger.debug(f"Context manager cleaned up {len(expired_areas)} expired areas")

    def _create_empty_snapshot(self, agent_x: float, agent_y: float) -> ContextSnapshot:
        """Create an empty context snapshot"""
        return ContextSnapshot(
            timestamp=time.time(),
            position=(agent_x, agent_y)
        )

    def _danger_to_numeric(self, danger_level: DangerLevel) -> float:
        """Convert danger level to numeric value (0.0-1.0)"""
        mapping = {
            DangerLevel.SAFE: 0.0,
            DangerLevel.LOW: 0.2,
            DangerLevel.MODERATE: 0.4,
            DangerLevel.HIGH: 0.7,
            DangerLevel.CRITICAL: 1.0
        }
        return mapping.get(danger_level, 0.0)

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about current context state"""
        return {
            "agent_id": self.agent_id,
            "active_areas": len(self.contextual_areas),
            "history_size": len(self.context_history),
            "last_snapshot": {
                "danger": self.last_snapshot.local_danger.value if self.last_snapshot else "none",
                "resources": self.last_snapshot.resource_availability if self.last_snapshot else 0.0,
                "social": self.last_snapshot.social_density if self.last_snapshot else 0.0,
            } if self.last_snapshot else None,
            "contextual_areas": {
                area_id: {
                    "type": area.context_type.value,
                    "danger": area.danger_level.value,
                    "center": area.center,
                    "radius": area.radius
                }
                for area_id, area in self.contextual_areas.items()
            }
        }