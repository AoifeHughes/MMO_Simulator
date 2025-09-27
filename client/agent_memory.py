"""
Agent Memory System

This module implements persistent memory for agents, enabling them to:
- Remember resource locations and their quality over time
- Track danger zones and areas where they've been attacked
- Maintain social memory of other agents (allies, enemies, trading partners)
- Use memory decay and reinforcement to keep information relevant
- Influence decision making through memory-based utility modifications
"""

import logging
import time
import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memories that can be stored"""
    RESOURCE_LOCATION = "resource_location"
    DANGER_ZONE = "danger_zone"
    SOCIAL_INTERACTION = "social_interaction"
    TRADE_RESULT = "trade_result"
    COMBAT_RESULT = "combat_result"
    EXPLORATION_RESULT = "exploration_result"


class MemoryRelevance(Enum):
    """Relevance levels for memories"""
    CRITICAL = 10    # Never forgotten (death locations, major threats)
    HIGH = 7        # Important for survival/success
    MEDIUM = 5      # Useful information
    LOW = 3         # Minor details
    TRIVIAL = 1     # Background information


@dataclass
class Memory:
    """A single memory entry"""
    memory_id: str
    memory_type: MemoryType
    content: Dict[str, Any]
    location: Optional[Tuple[float, float]] = None
    relevance: MemoryRelevance = MemoryRelevance.MEDIUM
    creation_time: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    decay_rate: float = 0.1  # How fast this memory fades
    reinforcement_count: int = 0  # How many times this memory was reinforced
    confidence: float = 1.0  # How confident the agent is in this memory

    def get_strength(self, current_time: Optional[float] = None) -> float:
        """Calculate current memory strength (0.0 to 1.0)"""
        if current_time is None:
            current_time = time.time()

        # Base strength from relevance
        base_strength = float(self.relevance.value) / 10.0

        # Time decay
        time_since_access = current_time - self.last_accessed
        decay_factor = math.exp(-self.decay_rate * time_since_access / 3600.0)  # Decay per hour

        # Reinforcement bonus
        reinforcement_bonus = min(0.5, self.reinforcement_count * 0.1)

        # Access frequency bonus
        access_bonus = min(0.3, self.access_count * 0.02)

        # Confidence modifier
        confidence_modifier = self.confidence

        final_strength = (base_strength + reinforcement_bonus + access_bonus) * decay_factor * confidence_modifier
        return min(1.0, max(0.0, final_strength))

    def access(self):
        """Mark this memory as accessed"""
        self.last_accessed = time.time()
        self.access_count += 1

    def reinforce(self, strength: float = 1.0):
        """Reinforce this memory, making it stronger"""
        self.reinforcement_count += 1
        self.confidence = min(1.0, self.confidence + (strength * 0.1))
        self.last_accessed = time.time()

    def weaken(self, strength: float = 1.0):
        """Weaken this memory (e.g., conflicting information)"""
        self.confidence = max(0.1, self.confidence - (strength * 0.2))


class LocationMemory:
    """Manages location-based memories (resources, dangers, etc.)"""

    def __init__(self, spatial_resolution: float = 5.0):
        self.spatial_resolution = spatial_resolution  # Grid size for spatial indexing
        self.location_grid: Dict[Tuple[int, int], List[str]] = defaultdict(list)
        self.memories: Dict[str, Memory] = {}

    def _get_grid_coords(self, x: float, y: float) -> Tuple[int, int]:
        """Convert world coordinates to grid coordinates"""
        return (int(x // self.spatial_resolution), int(y // self.spatial_resolution))

    def add_memory(self, memory: Memory):
        """Add a location-based memory"""
        if memory.location:
            grid_coords = self._get_grid_coords(*memory.location)
            self.location_grid[grid_coords].append(memory.memory_id)
            self.memories[memory.memory_id] = memory

    def get_memories_near(self, x: float, y: float, radius: float = 10.0,
                         memory_type: Optional[MemoryType] = None,
                         min_strength: float = 0.1) -> List[Memory]:
        """Get memories near a location"""
        current_time = time.time()
        nearby_memories = []

        # Calculate grid range to search
        grid_radius = int(math.ceil(radius / self.spatial_resolution))
        center_grid = self._get_grid_coords(x, y)

        for dx in range(-grid_radius, grid_radius + 1):
            for dy in range(-grid_radius, grid_radius + 1):
                grid_coords = (center_grid[0] + dx, center_grid[1] + dy)

                for memory_id in self.location_grid.get(grid_coords, []):
                    memory = self.memories.get(memory_id)
                    if not memory or not memory.location:
                        continue

                    # Check distance
                    distance = math.sqrt((memory.location[0] - x)**2 + (memory.location[1] - y)**2)
                    if distance > radius:
                        continue

                    # Check type filter
                    if memory_type and memory.memory_type != memory_type:
                        continue

                    # Check strength threshold
                    if memory.get_strength(current_time) < min_strength:
                        continue

                    nearby_memories.append(memory)

        # Sort by distance and strength
        nearby_memories.sort(key=lambda m: (
            math.sqrt((m.location[0] - x)**2 + (m.location[1] - y)**2),
            -m.get_strength(current_time)
        ))

        return nearby_memories

    def cleanup_weak_memories(self, min_strength: float = 0.05):
        """Remove memories that have decayed below threshold"""
        current_time = time.time()
        to_remove = []

        for memory_id, memory in self.memories.items():
            if memory.get_strength(current_time) < min_strength:
                to_remove.append(memory_id)

        for memory_id in to_remove:
            memory = self.memories[memory_id]
            if memory.location:
                grid_coords = self._get_grid_coords(*memory.location)
                if memory_id in self.location_grid[grid_coords]:
                    self.location_grid[grid_coords].remove(memory_id)
            del self.memories[memory_id]


class SocialMemory:
    """Manages memories about other agents"""

    def __init__(self):
        self.agent_memories: Dict[str, Dict[str, Memory]] = defaultdict(dict)
        self.relationship_scores: Dict[str, float] = defaultdict(float)  # -1.0 to 1.0
        self.trust_levels: Dict[str, float] = defaultdict(lambda: 0.5)  # 0.0 to 1.0

    def add_interaction_memory(self, agent_id: str, interaction_type: str,
                             outcome: str, details: Dict[str, Any]) -> Memory:
        """Add a memory of interaction with another agent"""
        # Use time with microseconds to avoid collisions
        memory_id = f"{agent_id}_{interaction_type}_{int(time.time() * 1000000)}"
        memory = Memory(
            memory_id=memory_id,
            memory_type=MemoryType.SOCIAL_INTERACTION,
            content={
                "agent_id": agent_id,
                "interaction_type": interaction_type,
                "outcome": outcome,
                "details": details
            },
            relevance=MemoryRelevance.HIGH if outcome in ["hostile", "very_positive"] else MemoryRelevance.MEDIUM
        )

        self.agent_memories[agent_id][memory_id] = memory
        self._update_relationship_score(agent_id, interaction_type, outcome)
        return memory

    def _update_relationship_score(self, agent_id: str, interaction_type: str, outcome: str):
        """Update relationship score based on interaction"""
        score_change = 0.0

        if interaction_type == "trade":
            if outcome == "successful":
                score_change = 0.1
            elif outcome == "failed":
                score_change = -0.05
            elif outcome == "cheated":
                score_change = -0.3
        elif interaction_type == "combat":
            if outcome == "attacked_by":
                score_change = -0.4
            elif outcome == "helped_by":
                score_change = 0.3
        elif interaction_type == "cooperation":
            if outcome == "successful":
                score_change = 0.2
            elif outcome == "abandoned":
                score_change = -0.2

        self.relationship_scores[agent_id] = max(-1.0, min(1.0,
            self.relationship_scores[agent_id] + score_change))

        # Update trust based on relationship
        if self.relationship_scores[agent_id] > 0.2:  # Lower threshold for trust increase
            self.trust_levels[agent_id] = min(1.0, self.trust_levels[agent_id] + 0.05)
        elif self.relationship_scores[agent_id] < -0.3:
            self.trust_levels[agent_id] = max(0.0, self.trust_levels[agent_id] - 0.1)

    def get_relationship_score(self, agent_id: str) -> float:
        """Get relationship score with another agent (-1.0 to 1.0)"""
        return self.relationship_scores[agent_id]

    def get_trust_level(self, agent_id: str) -> float:
        """Get trust level for another agent (0.0 to 1.0)"""
        return self.trust_levels[agent_id]

    def get_agent_memories(self, agent_id: str, memory_type: Optional[str] = None) -> List[Memory]:
        """Get memories related to a specific agent"""
        memories = list(self.agent_memories[agent_id].values())

        if memory_type:
            memories = [m for m in memories if m.content.get("interaction_type") == memory_type]

        # Sort by recency and strength
        memories.sort(key=lambda m: (m.last_accessed, m.get_strength()), reverse=True)
        return memories


class AgentMemory:
    """Complete memory system for an agent"""

    def __init__(self, agent_id: str, max_memories: int = 1000,
                 cleanup_interval: float = 300.0):  # 5 minutes
        self.agent_id = agent_id
        self.max_memories = max_memories
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()

        # Memory subsystems
        self.location_memory = LocationMemory()
        self.social_memory = SocialMemory()
        self.general_memories: Dict[str, Memory] = {}

        # Memory statistics
        self.memory_stats = {
            "total_memories": 0,
            "memories_by_type": defaultdict(int),
            "average_strength": 0.0,
            "oldest_memory": None,
            "most_accessed": None
        }

    def remember_resource_location(self, x: float, y: float, resource_type: str,
                                 quality: float, quantity: int) -> Memory:
        """Remember a resource location"""
        memory_id = f"resource_{resource_type}_{x}_{y}_{int(time.time())}"
        memory = Memory(
            memory_id=memory_id,
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={
                "resource_type": resource_type,
                "quality": quality,
                "quantity": quantity,
                "discovery_time": time.time()
            },
            location=(x, y),
            relevance=MemoryRelevance.HIGH if quality > 0.7 else MemoryRelevance.MEDIUM,
            decay_rate=0.05  # Resources decay slowly
        )

        self.location_memory.add_memory(memory)
        self._update_stats()
        return memory

    def remember_danger_zone(self, x: float, y: float, danger_type: str,
                           severity: float, details: Dict[str, Any]) -> Memory:
        """Remember a dangerous location"""
        memory_id = f"danger_{danger_type}_{x}_{y}_{int(time.time())}"
        memory = Memory(
            memory_id=memory_id,
            memory_type=MemoryType.DANGER_ZONE,
            content={
                "danger_type": danger_type,
                "severity": severity,
                "details": details,
                "incident_time": time.time()
            },
            location=(x, y),
            relevance=MemoryRelevance.CRITICAL if severity > 0.8 else MemoryRelevance.HIGH,
            decay_rate=0.02 if severity > 0.8 else 0.08  # Severe dangers remembered longer
        )

        self.location_memory.add_memory(memory)
        self._update_stats()
        return memory

    def remember_social_interaction(self, other_agent_id: str, interaction_type: str,
                                  outcome: str, location: Optional[Tuple[float, float]] = None,
                                  details: Optional[Dict[str, Any]] = None) -> Memory:
        """Remember interaction with another agent"""
        details = details or {}
        memory = self.social_memory.add_interaction_memory(
            other_agent_id, interaction_type, outcome, details
        )

        if location:
            memory.location = location

        self._update_stats()
        return memory

    def remember_trade_result(self, other_agent_id: str, items_given: List[Dict],
                            items_received: List[Dict], success: bool,
                            location: Optional[Tuple[float, float]] = None) -> Memory:
        """Remember a trade result"""
        outcome = "successful" if success else "failed"
        details = {
            "items_given": items_given,
            "items_received": items_received,
            "trade_value_given": sum(item.get("value", 1) for item in items_given),
            "trade_value_received": sum(item.get("value", 1) for item in items_received)
        }

        return self.remember_social_interaction(
            other_agent_id, "trade", outcome, location, details
        )

    def get_known_resources(self, x: float, y: float, radius: float = 20.0,
                          resource_type: Optional[str] = None) -> List[Memory]:
        """Get known resource locations near a position"""
        memories = self.location_memory.get_memories_near(
            x, y, radius, MemoryType.RESOURCE_LOCATION
        )

        if resource_type:
            memories = [m for m in memories if m.content.get("resource_type") == resource_type]

        return memories

    def get_danger_zones(self, x: float, y: float, radius: float = 15.0) -> List[Memory]:
        """Get known danger zones near a position"""
        return self.location_memory.get_memories_near(
            x, y, radius, MemoryType.DANGER_ZONE
        )

    def is_location_dangerous(self, x: float, y: float, radius: float = 5.0) -> Tuple[bool, float]:
        """Check if a location is considered dangerous"""
        danger_memories = self.get_danger_zones(x, y, radius)

        if not danger_memories:
            return False, 0.0

        # Calculate danger level based on severity and memory strength
        max_danger = 0.0
        for memory in danger_memories:
            severity = memory.content.get("severity", 0.0)
            strength = memory.get_strength()
            danger_level = severity * strength
            max_danger = max(max_danger, danger_level)

        return max_danger > 0.3, max_danger

    def get_agent_relationship(self, agent_id: str) -> Dict[str, float]:
        """Get relationship information for another agent"""
        return {
            "relationship_score": self.social_memory.get_relationship_score(agent_id),
            "trust_level": self.social_memory.get_trust_level(agent_id),
            "interaction_count": len(self.social_memory.get_agent_memories(agent_id))
        }

    def get_trusted_agents(self, min_trust: float = 0.7) -> List[str]:
        """Get list of trusted agent IDs"""
        trusted = []
        for agent_id, trust in self.social_memory.trust_levels.items():
            if trust >= min_trust:
                trusted.append(agent_id)
        return trusted

    def get_hostile_agents(self, max_relationship: float = -0.3) -> List[str]:
        """Get list of hostile agent IDs"""
        hostile = []
        for agent_id, score in self.social_memory.relationship_scores.items():
            if score <= max_relationship:
                hostile.append(agent_id)
        return hostile

    def calculate_location_utility_modifier(self, x: float, y: float, action_type: str) -> float:
        """Calculate utility modifier for a location based on memories"""
        modifier = 1.0

        # Check for danger
        is_dangerous, danger_level = self.is_location_dangerous(x, y)
        if is_dangerous:
            if action_type in ["explore", "gather_resources"]:
                modifier *= (1.0 - danger_level * 0.8)  # Reduce utility for dangerous actions
            elif action_type == "flee":
                modifier *= (1.0 + danger_level * 0.5)  # Increase flee utility in dangerous areas

        # Check for known resources
        if action_type == "gather_resources":
            nearby_resources = self.get_known_resources(x, y, 10.0)
            if nearby_resources:
                best_resource = max(nearby_resources, key=lambda m: m.get_strength())
                quality = best_resource.content.get("quality", 0.5)
                strength = best_resource.get_strength()
                modifier *= (1.0 + quality * strength * 0.5)

        return max(0.1, min(2.0, modifier))

    def calculate_social_utility_modifier(self, target_agent_id: str, action_type: str) -> float:
        """Calculate utility modifier for social actions based on memories"""
        relationship = self.get_agent_relationship(target_agent_id)
        relationship_score = relationship["relationship_score"]
        trust_level = relationship["trust_level"]

        modifier = 1.0

        if action_type == "trade":
            # Higher utility for trusted agents
            modifier *= (0.5 + trust_level)
            if relationship_score > 0:
                modifier *= (1.0 + relationship_score * 0.3)
        elif action_type == "attack":
            # Higher utility for hostile agents
            if relationship_score < 0:
                modifier *= (1.0 + abs(relationship_score) * 0.5)
            else:
                modifier *= 0.3  # Low utility for attacking friendly agents
        elif action_type == "cooperate":
            # Higher utility for trusted, friendly agents
            modifier *= trust_level * (1.0 + max(0, relationship_score))

        return max(0.1, min(2.0, modifier))

    def periodic_cleanup(self):
        """Perform periodic memory cleanup"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return

        # Clean up weak memories
        self.location_memory.cleanup_weak_memories()

        # Remove very old, weak general memories
        to_remove = []
        for memory_id, memory in self.general_memories.items():
            if memory.get_strength(current_time) < 0.05:
                to_remove.append(memory_id)

        for memory_id in to_remove:
            del self.general_memories[memory_id]

        # If still over capacity, remove oldest low-relevance memories
        total_memories = (len(self.location_memory.memories) +
                         sum(len(memories) for memories in self.social_memory.agent_memories.values()) +
                         len(self.general_memories))

        if total_memories > self.max_memories:
            self._aggressive_cleanup()

        self.last_cleanup = current_time
        self._update_stats()
        logger.debug(f"Agent {self.agent_id} memory cleanup: {total_memories} memories remaining")

    def _aggressive_cleanup(self):
        """Aggressively remove memories when over capacity"""
        # Collect all memories with their strength
        all_memories = []

        for memory in self.location_memory.memories.values():
            all_memories.append(("location", memory))

        for agent_memories in self.social_memory.agent_memories.values():
            for memory in agent_memories.values():
                all_memories.append(("social", memory))

        for memory in self.general_memories.values():
            all_memories.append(("general", memory))

        # Sort by strength and relevance (keep strongest, most relevant)
        all_memories.sort(key=lambda x: (x[1].relevance.value, x[1].get_strength()), reverse=True)

        # Keep only the best memories
        memories_to_keep = all_memories[:self.max_memories]
        memories_to_remove = all_memories[self.max_memories:]

        # Remove excess memories
        for memory_type, memory in memories_to_remove:
            if memory_type == "location":
                if memory.location:
                    grid_coords = self.location_memory._get_grid_coords(*memory.location)
                    if memory.memory_id in self.location_memory.location_grid[grid_coords]:
                        self.location_memory.location_grid[grid_coords].remove(memory.memory_id)
                if memory.memory_id in self.location_memory.memories:
                    del self.location_memory.memories[memory.memory_id]
            elif memory_type == "social":
                agent_id = memory.content.get("agent_id")
                if agent_id and memory.memory_id in self.social_memory.agent_memories[agent_id]:
                    del self.social_memory.agent_memories[agent_id][memory.memory_id]
            elif memory_type == "general":
                if memory.memory_id in self.general_memories:
                    del self.general_memories[memory.memory_id]

    def _update_stats(self):
        """Update memory statistics"""
        all_memories = []
        all_memories.extend(self.location_memory.memories.values())
        for agent_memories in self.social_memory.agent_memories.values():
            all_memories.extend(agent_memories.values())
        all_memories.extend(self.general_memories.values())

        self.memory_stats["total_memories"] = len(all_memories)

        # Count by type
        type_counts = defaultdict(int)
        strengths = []
        oldest_time = float('inf')
        oldest_memory = None
        max_access = 0
        most_accessed = None

        for memory in all_memories:
            type_counts[memory.memory_type.value] += 1
            strengths.append(memory.get_strength())

            if memory.creation_time < oldest_time:
                oldest_time = memory.creation_time
                oldest_memory = memory.memory_id

            if memory.access_count > max_access:
                max_access = memory.access_count
                most_accessed = memory.memory_id

        self.memory_stats["memories_by_type"] = dict(type_counts)
        self.memory_stats["average_strength"] = sum(strengths) / len(strengths) if strengths else 0.0
        self.memory_stats["oldest_memory"] = oldest_memory
        self.memory_stats["most_accessed"] = most_accessed

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of the agent's memory state"""
        self._update_stats()
        return {
            "agent_id": self.agent_id,
            "statistics": self.memory_stats.copy(),
            "relationship_summary": {
                "trusted_agents": len(self.get_trusted_agents()),
                "hostile_agents": len(self.get_hostile_agents()),
                "total_known_agents": len(self.social_memory.relationship_scores)
            },
            "location_memory_summary": {
                "total_locations": len(self.location_memory.memories),
                "danger_zones": len([m for m in self.location_memory.memories.values()
                                   if m.memory_type == MemoryType.DANGER_ZONE]),
                "resource_locations": len([m for m in self.location_memory.memories.values()
                                         if m.memory_type == MemoryType.RESOURCE_LOCATION])
            }
        }