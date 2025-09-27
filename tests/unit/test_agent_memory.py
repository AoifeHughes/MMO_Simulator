"""
Tests for Agent Memory System

Tests memory storage, retrieval, decay mechanisms, and integration
with utility calculations and decision making.
"""

import math
import time
from unittest.mock import Mock, patch

import pytest

from client.agent_memory import (
    AgentMemory,
    LocationMemory,
    Memory,
    MemoryRelevance,
    MemoryType,
    SocialMemory,
)


class TestMemory:
    """Test basic Memory functionality"""

    def test_memory_creation(self):
        """Test memory creation with default values"""
        memory = Memory(
            memory_id="test_memory",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={"resource_type": "wood", "quality": 0.8},
        )

        assert memory.memory_id == "test_memory"
        assert memory.memory_type == MemoryType.RESOURCE_LOCATION
        assert memory.content["resource_type"] == "wood"
        assert memory.relevance == MemoryRelevance.MEDIUM
        assert memory.confidence == 1.0
        assert memory.access_count == 0

    def test_memory_strength_calculation(self):
        """Test memory strength calculation"""
        memory = Memory(
            memory_id="test_memory",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={},
            relevance=MemoryRelevance.HIGH,
            decay_rate=0.1,
        )

        # Fresh memory should have high strength
        initial_strength = memory.get_strength()
        assert initial_strength > 0.6

        # Simulate time passing
        future_time = time.time() + 3600  # 1 hour later
        decayed_strength = memory.get_strength(future_time)
        assert decayed_strength < initial_strength

    def test_memory_access_tracking(self):
        """Test memory access tracking"""
        memory = Memory(
            memory_id="test_memory",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={},
        )

        initial_access_count = memory.access_count
        initial_access_time = memory.last_accessed

        time.sleep(0.01)  # Small delay
        memory.access()

        assert memory.access_count == initial_access_count + 1
        assert memory.last_accessed > initial_access_time

    def test_memory_reinforcement(self):
        """Test memory reinforcement"""
        memory = Memory(
            memory_id="test_memory",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={},
            confidence=0.5,
        )

        initial_confidence = memory.confidence
        initial_reinforcement = memory.reinforcement_count

        memory.reinforce(1.0)

        assert memory.confidence > initial_confidence
        assert memory.reinforcement_count == initial_reinforcement + 1

    def test_memory_weakening(self):
        """Test memory weakening"""
        memory = Memory(
            memory_id="test_memory",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={},
            confidence=0.8,
        )

        initial_confidence = memory.confidence
        memory.weaken(1.0)

        assert memory.confidence < initial_confidence
        assert memory.confidence >= 0.1  # Should not go below minimum


class TestLocationMemory:
    """Test location-based memory functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.location_memory = LocationMemory(spatial_resolution=5.0)

    def test_grid_coordinate_calculation(self):
        """Test spatial grid coordinate calculation"""
        coords = self.location_memory._get_grid_coords(12.3, 7.8)
        assert coords == (2, 1)  # 12.3 // 5 = 2, 7.8 // 5 = 1

        coords = self.location_memory._get_grid_coords(-3.2, 15.7)
        assert coords == (-1, 3)

    def test_add_location_memory(self):
        """Test adding location-based memories"""
        memory = Memory(
            memory_id="resource_1",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={"resource_type": "wood"},
            location=(10.0, 15.0),
        )

        self.location_memory.add_memory(memory)

        assert "resource_1" in self.location_memory.memories
        grid_coords = self.location_memory._get_grid_coords(10.0, 15.0)
        assert "resource_1" in self.location_memory.location_grid[grid_coords]

    def test_get_memories_near_location(self):
        """Test retrieving memories near a location"""
        # Add memories at different locations
        memory1 = Memory(
            memory_id="resource_1",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={"resource_type": "wood"},
            location=(10.0, 10.0),
        )

        memory2 = Memory(
            memory_id="resource_2",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={"resource_type": "stone"},
            location=(15.0, 15.0),
        )

        memory3 = Memory(
            memory_id="danger_1",
            memory_type=MemoryType.DANGER_ZONE,
            content={"danger_type": "enemy"},
            location=(100.0, 100.0),  # Far away
        )

        self.location_memory.add_memory(memory1)
        self.location_memory.add_memory(memory2)
        self.location_memory.add_memory(memory3)

        # Search near (12, 12) with radius 5
        nearby = self.location_memory.get_memories_near(12.0, 12.0, radius=5.0)
        nearby_ids = [m.memory_id for m in nearby]

        assert "resource_1" in nearby_ids
        assert "resource_2" in nearby_ids
        assert "danger_1" not in nearby_ids  # Too far away

    def test_get_memories_with_type_filter(self):
        """Test retrieving memories with type filtering"""
        memory1 = Memory(
            memory_id="resource_1",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={"resource_type": "wood"},
            location=(10.0, 10.0),
        )

        memory2 = Memory(
            memory_id="danger_1",
            memory_type=MemoryType.DANGER_ZONE,
            content={"danger_type": "enemy"},
            location=(12.0, 12.0),
        )

        self.location_memory.add_memory(memory1)
        self.location_memory.add_memory(memory2)

        # Search for only resource locations
        resources = self.location_memory.get_memories_near(
            11.0, 11.0, radius=5.0, memory_type=MemoryType.RESOURCE_LOCATION
        )
        resource_ids = [m.memory_id for m in resources]

        assert "resource_1" in resource_ids
        assert "danger_1" not in resource_ids

    def test_cleanup_weak_memories(self):
        """Test cleanup of weak memories"""
        # Create a memory with very high decay rate
        weak_memory = Memory(
            memory_id="weak_memory",
            memory_type=MemoryType.RESOURCE_LOCATION,
            content={},
            location=(10.0, 10.0),
            decay_rate=100.0,  # Very high decay
        )

        # Set last accessed to long ago
        weak_memory.last_accessed = time.time() - 3600  # 1 hour ago

        self.location_memory.add_memory(weak_memory)
        assert "weak_memory" in self.location_memory.memories

        # Cleanup should remove weak memory
        self.location_memory.cleanup_weak_memories(min_strength=0.1)
        assert "weak_memory" not in self.location_memory.memories


class TestSocialMemory:
    """Test social memory functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.social_memory = SocialMemory()

    def test_add_interaction_memory(self):
        """Test adding interaction memories"""
        memory = self.social_memory.add_interaction_memory(
            agent_id="agent_1",
            interaction_type="trade",
            outcome="successful",
            details={"items_traded": ["wood", "stone"]},
        )

        assert memory.memory_type == MemoryType.SOCIAL_INTERACTION
        assert memory.content["agent_id"] == "agent_1"
        assert memory.content["interaction_type"] == "trade"
        assert "agent_1" in self.social_memory.agent_memories

    def test_relationship_score_updates(self):
        """Test relationship score updates based on interactions"""
        agent_id = "agent_1"

        # Successful trade should improve relationship
        self.social_memory.add_interaction_memory(agent_id, "trade", "successful", {})
        score_after_trade = self.social_memory.get_relationship_score(agent_id)
        assert score_after_trade > 0

        # Being attacked should worsen relationship
        self.social_memory.add_interaction_memory(agent_id, "combat", "attacked_by", {})
        score_after_attack = self.social_memory.get_relationship_score(agent_id)
        assert score_after_attack < score_after_trade

    def test_trust_level_updates(self):
        """Test trust level updates"""
        agent_id = "agent_1"
        initial_trust = self.social_memory.get_trust_level(agent_id)

        # Multiple successful interactions should increase trust
        for _ in range(5):
            self.social_memory.add_interaction_memory(
                agent_id, "cooperation", "successful", {}
            )

        final_trust = self.social_memory.get_trust_level(agent_id)
        assert final_trust > initial_trust

    def test_get_agent_memories_filtering(self):
        """Test filtering agent memories by type"""
        agent_id = "agent_1"

        # Add different types of interactions
        self.social_memory.add_interaction_memory(agent_id, "trade", "successful", {})
        self.social_memory.add_interaction_memory(agent_id, "combat", "attacked_by", {})
        self.social_memory.add_interaction_memory(agent_id, "trade", "failed", {})

        # Get only trade memories
        trade_memories = self.social_memory.get_agent_memories(agent_id, "trade")
        assert len(trade_memories) == 2
        assert all(m.content["interaction_type"] == "trade" for m in trade_memories)

        # Get all memories
        all_memories = self.social_memory.get_agent_memories(agent_id)
        assert len(all_memories) == 3


class TestAgentMemory:
    """Test complete agent memory system"""

    def setup_method(self):
        """Set up test fixtures"""
        self.agent_memory = AgentMemory("test_agent", max_memories=50)

    def test_remember_resource_location(self):
        """Test remembering resource locations"""
        memory = self.agent_memory.remember_resource_location(
            x=10.0, y=20.0, resource_type="wood", quality=0.8, quantity=5
        )

        assert memory.memory_type == MemoryType.RESOURCE_LOCATION
        assert memory.location == (10.0, 20.0)
        assert memory.content["resource_type"] == "wood"
        assert memory.content["quality"] == 0.8

    def test_remember_danger_zone(self):
        """Test remembering danger zones"""
        memory = self.agent_memory.remember_danger_zone(
            x=15.0,
            y=25.0,
            danger_type="enemy",
            severity=0.9,
            details={"enemy_type": "aggressive", "weapon": "sword"},
        )

        assert memory.memory_type == MemoryType.DANGER_ZONE
        assert memory.location == (15.0, 25.0)
        assert memory.content["danger_type"] == "enemy"
        assert memory.content["severity"] == 0.9
        assert memory.relevance == MemoryRelevance.CRITICAL  # High severity

    def test_remember_social_interaction(self):
        """Test remembering social interactions"""
        memory = self.agent_memory.remember_social_interaction(
            other_agent_id="agent_2",
            interaction_type="trade",
            outcome="successful",
            location=(5.0, 5.0),
            details={"items": ["wood", "stone"]},
        )

        assert memory.memory_type == MemoryType.SOCIAL_INTERACTION
        assert memory.location == (5.0, 5.0)
        assert memory.content["agent_id"] == "agent_2"

    def test_remember_trade_result(self):
        """Test remembering trade results"""
        items_given = [{"type": "wood", "quantity": 3, "value": 6}]
        items_received = [{"type": "stone", "quantity": 2, "value": 8}]

        memory = self.agent_memory.remember_trade_result(
            other_agent_id="agent_2",
            items_given=items_given,
            items_received=items_received,
            success=True,
            location=(10.0, 10.0),
        )

        assert memory.content["details"]["items_given"] == items_given
        assert memory.content["details"]["items_received"] == items_received
        assert memory.content["details"]["trade_value_given"] == 6
        assert memory.content["details"]["trade_value_received"] == 8

    def test_get_known_resources(self):
        """Test retrieving known resource locations"""
        # Add several resource memories
        self.agent_memory.remember_resource_location(10.0, 10.0, "wood", 0.8, 5)
        self.agent_memory.remember_resource_location(15.0, 15.0, "stone", 0.6, 3)
        self.agent_memory.remember_resource_location(
            50.0, 50.0, "wood", 0.9, 10  # Far away
        )

        # Search near (12, 12)
        nearby_resources = self.agent_memory.get_known_resources(
            12.0, 12.0, radius=10.0
        )
        assert len(nearby_resources) == 2

        # Search for specific resource type
        wood_resources = self.agent_memory.get_known_resources(
            12.0, 12.0, radius=20.0, resource_type="wood"
        )
        assert len(wood_resources) == 1
        assert wood_resources[0].content["resource_type"] == "wood"

    def test_get_danger_zones(self):
        """Test retrieving danger zones"""
        # Add danger memories
        self.agent_memory.remember_danger_zone(
            10.0, 10.0, "enemy", 0.8, {"type": "bandit"}
        )
        self.agent_memory.remember_danger_zone(
            50.0, 50.0, "trap", 0.5, {"type": "pit"}  # Far away
        )

        danger_zones = self.agent_memory.get_danger_zones(12.0, 12.0, radius=10.0)
        assert len(danger_zones) == 1
        assert danger_zones[0].content["danger_type"] == "enemy"

    def test_is_location_dangerous(self):
        """Test danger assessment for locations"""
        # Initially not dangerous
        is_dangerous, danger_level = self.agent_memory.is_location_dangerous(10.0, 10.0)
        assert not is_dangerous
        assert danger_level == 0.0

        # Add danger zone
        self.agent_memory.remember_danger_zone(
            10.0, 10.0, "enemy", 0.8, {"type": "bandit"}
        )

        is_dangerous, danger_level = self.agent_memory.is_location_dangerous(10.0, 10.0)
        assert is_dangerous
        assert danger_level > 0.3

    def test_get_agent_relationship(self):
        """Test getting relationship information"""
        agent_id = "agent_2"

        # Add some interactions
        self.agent_memory.remember_social_interaction(
            agent_id, "trade", "successful", details={}
        )
        self.agent_memory.remember_social_interaction(
            agent_id, "cooperation", "successful", details={}
        )

        relationship = self.agent_memory.get_agent_relationship(agent_id)

        assert "relationship_score" in relationship
        assert "trust_level" in relationship
        assert "interaction_count" in relationship
        assert relationship["relationship_score"] > 0  # Should be positive
        assert relationship["interaction_count"] == 2

    def test_get_trusted_and_hostile_agents(self):
        """Test getting lists of trusted and hostile agents"""
        # Create relationships with different agents
        self.agent_memory.remember_social_interaction(
            "friend_1", "cooperation", "successful", details={}
        )
        for _ in range(5):  # Multiple positive interactions
            self.agent_memory.remember_social_interaction(
                "friend_1", "trade", "successful", details={}
            )

        self.agent_memory.remember_social_interaction(
            "enemy_1", "combat", "attacked_by", details={}
        )

        trusted = self.agent_memory.get_trusted_agents(min_trust=0.6)
        hostile = self.agent_memory.get_hostile_agents(max_relationship=-0.2)

        assert "friend_1" in trusted
        assert "enemy_1" in hostile
        assert "enemy_1" not in trusted
        assert "friend_1" not in hostile

    def test_location_utility_modifier(self):
        """Test location-based utility modification"""
        location = (10.0, 10.0)

        # Base utility should be 1.0
        base_modifier = self.agent_memory.calculate_location_utility_modifier(
            location[0], location[1], "explore"
        )
        assert base_modifier == 1.0

        # Add danger - should reduce utility for exploration
        self.agent_memory.remember_danger_zone(
            location[0], location[1], "enemy", 0.8, {}
        )

        danger_modifier = self.agent_memory.calculate_location_utility_modifier(
            location[0], location[1], "explore"
        )
        assert danger_modifier < base_modifier

        # But should increase utility for fleeing
        flee_modifier = self.agent_memory.calculate_location_utility_modifier(
            location[0], location[1], "flee"
        )
        assert flee_modifier > base_modifier

    def test_social_utility_modifier(self):
        """Test social action utility modification"""
        agent_id = "agent_2"

        # Base utility should be 1.0
        base_modifier = self.agent_memory.calculate_social_utility_modifier(
            agent_id, "trade"
        )
        assert base_modifier > 0.0

        # Add positive interactions - should increase trade utility
        for _ in range(3):
            self.agent_memory.remember_social_interaction(
                agent_id, "trade", "successful", details={}
            )

        positive_modifier = self.agent_memory.calculate_social_utility_modifier(
            agent_id, "trade"
        )
        assert positive_modifier > base_modifier

        # Add hostile interaction - should increase attack utility
        self.agent_memory.remember_social_interaction(
            "enemy_1", "combat", "attacked_by", details={}
        )

        attack_modifier = self.agent_memory.calculate_social_utility_modifier(
            "enemy_1", "attack"
        )
        assert attack_modifier > 1.0

    def test_periodic_cleanup(self):
        """Test periodic memory cleanup"""
        # Add many memories to trigger cleanup
        for i in range(60):  # More than max_memories (50)
            self.agent_memory.remember_resource_location(
                float(i), float(i), "wood", 0.5, 1
            )

        # Force cleanup by setting last_cleanup to past
        self.agent_memory.last_cleanup = time.time() - 400  # Force cleanup
        self.agent_memory.periodic_cleanup()

        total_memories = (
            len(self.agent_memory.location_memory.memories)
            + sum(
                len(memories)
                for memories in self.agent_memory.social_memory.agent_memories.values()
            )
            + len(self.agent_memory.general_memories)
        )

        assert total_memories <= self.agent_memory.max_memories

    def test_memory_summary(self):
        """Test memory summary generation"""
        # Add various types of memories
        self.agent_memory.remember_resource_location(10.0, 10.0, "wood", 0.8, 5)
        self.agent_memory.remember_danger_zone(20.0, 20.0, "enemy", 0.6, {})
        self.agent_memory.remember_social_interaction("agent_2", "trade", "successful")

        summary = self.agent_memory.get_memory_summary()

        assert summary["agent_id"] == "test_agent"
        assert "statistics" in summary
        assert "relationship_summary" in summary
        assert "location_memory_summary" in summary
        assert summary["statistics"]["total_memories"] > 0
        assert summary["location_memory_summary"]["resource_locations"] == 1
        assert summary["location_memory_summary"]["danger_zones"] == 1

    def test_memory_decay_over_time(self):
        """Test that memories decay properly over time"""
        memory = self.agent_memory.remember_resource_location(
            10.0, 10.0, "wood", 0.8, 5
        )

        initial_strength = memory.get_strength()

        # Simulate time passing
        future_time = time.time() + 7200  # 2 hours
        decayed_strength = memory.get_strength(future_time)

        assert decayed_strength < initial_strength

    def test_memory_reinforcement_prevents_decay(self):
        """Test that reinforcement helps maintain memory strength"""
        memory = self.agent_memory.remember_resource_location(
            10.0, 10.0, "wood", 0.8, 5
        )

        # Reinforce the memory multiple times
        for _ in range(3):
            memory.reinforce(1.0)

        # Check strength after time passes
        future_time = time.time() + 3600  # 1 hour
        reinforced_strength = memory.get_strength(future_time)

        # Create a similar memory without reinforcement for comparison
        weak_memory = self.agent_memory.remember_resource_location(
            20.0, 20.0, "wood", 0.8, 5
        )
        weak_strength = weak_memory.get_strength(future_time)

        assert reinforced_strength > weak_strength


class TestMemoryIntegration:
    """Test memory system integration scenarios"""

    def setup_method(self):
        """Set up test fixtures"""
        self.agent_memory = AgentMemory("integration_agent")

    def test_resource_discovery_and_retrieval_scenario(self):
        """Test complete resource discovery and retrieval scenario"""
        # Agent discovers a high-quality resource
        location = (25.0, 30.0)
        memory = self.agent_memory.remember_resource_location(
            location[0], location[1], "gold", 0.9, 10
        )

        # Later, agent searches for resources nearby
        nearby_resources = self.agent_memory.get_known_resources(
            location[0] + 2, location[1] + 2, radius=5.0
        )

        assert len(nearby_resources) == 1
        assert nearby_resources[0].content["resource_type"] == "gold"

        # Check utility modifier for gathering at this location
        utility_modifier = self.agent_memory.calculate_location_utility_modifier(
            location[0], location[1], "gather_resources"
        )
        assert (
            utility_modifier > 1.0
        )  # Should be boosted by known high-quality resource

    def test_danger_avoidance_scenario(self):
        """Test danger zone creation and avoidance"""
        danger_location = (40.0, 45.0)

        # Agent gets attacked and remembers it as dangerous
        self.agent_memory.remember_danger_zone(
            danger_location[0],
            danger_location[1],
            "ambush",
            0.9,
            {"attacker": "bandit_leader", "weapon": "sword"},
        )

        # Later, agent checks if location is dangerous
        is_dangerous, danger_level = self.agent_memory.is_location_dangerous(
            danger_location[0], danger_location[1]
        )

        assert is_dangerous
        assert danger_level > 0.5

        # Utility for exploration should be reduced
        utility_modifier = self.agent_memory.calculate_location_utility_modifier(
            danger_location[0], danger_location[1], "explore"
        )
        assert utility_modifier < 1.0

    def test_social_relationship_development(self):
        """Test social relationship development over time"""
        partner_id = "trade_partner"

        # Start with neutral relationship
        initial_relationship = self.agent_memory.get_agent_relationship(partner_id)
        assert initial_relationship["relationship_score"] == 0.0

        # Successful trades improve relationship
        for i in range(5):
            self.agent_memory.remember_trade_result(
                partner_id,
                items_given=[{"type": "wood", "quantity": 2, "value": 4}],
                items_received=[{"type": "stone", "quantity": 1, "value": 5}],
                success=True,
            )

        final_relationship = self.agent_memory.get_agent_relationship(partner_id)
        assert final_relationship["relationship_score"] > 0.0
        assert final_relationship["trust_level"] > initial_relationship["trust_level"]

        # Trade utility should be increased
        trade_utility = self.agent_memory.calculate_social_utility_modifier(
            partner_id, "trade"
        )
        assert trade_utility > 1.0

    def test_memory_influenced_decision_making(self):
        """Test how memories influence decision making"""
        # Create scenario with multiple options
        safe_resource_location = (10.0, 10.0)
        dangerous_resource_location = (20.0, 20.0)

        # Both locations have resources
        self.agent_memory.remember_resource_location(
            safe_resource_location[0], safe_resource_location[1], "wood", 0.7, 5
        )
        self.agent_memory.remember_resource_location(
            dangerous_resource_location[0],
            dangerous_resource_location[1],
            "wood",
            0.8,
            8,  # Better resource
        )

        # But one location is dangerous
        self.agent_memory.remember_danger_zone(
            dangerous_resource_location[0],
            dangerous_resource_location[1],
            "enemy",
            0.7,
            {},
        )

        # Calculate utility modifiers
        safe_utility = self.agent_memory.calculate_location_utility_modifier(
            safe_resource_location[0], safe_resource_location[1], "gather_resources"
        )
        dangerous_utility = self.agent_memory.calculate_location_utility_modifier(
            dangerous_resource_location[0],
            dangerous_resource_location[1],
            "gather_resources",
        )

        # Safe location should have higher net utility despite lower resource quality
        assert safe_utility > dangerous_utility


if __name__ == "__main__":
    pytest.main([__file__])
