"""
Tests for the Forest Fisher Cooperation scenario.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from scenarios.forest_fisher_cooperation import ForestFisherCooperationScenario
from world.terrain_generator import TerrainType


class TestForestFisherCooperationScenario:
    @pytest.fixture
    def scenario(self):
        return ForestFisherCooperationScenario()

    @pytest.fixture
    def mock_server(self):
        """Mock server with world and agent registry"""
        server = Mock()
        server.world = Mock()
        server.world.spawn_agent = Mock(return_value="test_agent_id")
        server.agent_registry = Mock()
        server.agent_registry.register_agent = Mock(return_value=Mock())
        return server

    def test_scenario_initialization(self, scenario):
        """Test scenario initialization with correct parameters"""
        assert scenario.name == "Forest Fisher Cooperation"
        assert "cooperate" in scenario.description.lower()
        assert scenario.terrain_type == TerrainType.MIXED
        assert scenario.seed == 300
        assert scenario.map_size == 20

    @pytest.mark.asyncio
    async def test_scenario_setup(self, scenario, mock_server):
        """Test scenario setup process"""
        await scenario.setup(mock_server)

        assert scenario.server == mock_server

    @pytest.mark.asyncio
    async def test_spawn_agents(self, scenario, mock_server):
        """Test agent spawning in cooperation scenario"""
        scenario.server = mock_server

        # Mock agent states for inventory modification
        mock_woodcutter_state = Mock()
        mock_woodcutter_state.inventory = Mock()
        mock_woodcutter_state.inventory.slots = []

        mock_fisher_state = Mock()

        mock_server.agent_registry.register_agent.side_effect = [
            mock_woodcutter_state,
            mock_fisher_state
        ]

        agent_configs = await scenario.spawn_agents()

        # Should spawn 2 agents
        assert len(agent_configs) == 2

        # Verify agent configurations
        woodcutter_config = agent_configs[0]
        fisher_config = agent_configs[1]

        assert woodcutter_config["name"] == "WoodCutter"
        assert woodcutter_config["behavior"] == "wood_harvester"
        assert woodcutter_config["specialization"] == "wood_harvesting"

        assert fisher_config["name"] == "Fisher"
        assert fisher_config["behavior"] == "fishing_specialist"
        assert fisher_config["specialization"] == "fishing"

        # Verify world spawn calls
        assert mock_server.world.spawn_agent.call_count == 2

        # Verify agent registry calls
        assert mock_server.agent_registry.register_agent.call_count == 2

    def test_agent_positioning(self, scenario):
        """Test agent positioning logic"""
        center_x, center_y = scenario.map_size // 2, scenario.map_size // 2

        # Calculate expected positions
        woodcutter_x, woodcutter_y = center_x - 2, center_y - 1
        fisher_x, fisher_y = center_x + 2, center_y + 1

        # Verify positions are reasonable
        assert 0 < woodcutter_x < scenario.map_size
        assert 0 < woodcutter_y < scenario.map_size
        assert 0 < fisher_x < scenario.map_size
        assert 0 < fisher_y < scenario.map_size

        # Verify agents are close but not overlapping
        distance = ((fisher_x - woodcutter_x)**2 + (fisher_y - woodcutter_y)**2)**0.5
        assert 2 < distance < 10  # Close cooperation but not overlapping

    def test_custom_behavior_tree(self, scenario):
        """Test custom behavior tree method"""
        # Should return None to use default behaviors
        behavior_tree = scenario.get_custom_behavior_tree("explorer", 10.0, 10.0)
        assert behavior_tree is None

    def test_scenario_info(self, scenario):
        """Test scenario information structure"""
        info = scenario.get_scenario_info()

        # Verify scenario metadata
        assert info["scenario_type"] == "cooperation"
        assert info["map_size"] == 20

        # Verify agent role definitions
        assert "agent_roles" in info
        roles = info["agent_roles"]

        # WoodCutter role
        assert "WoodCutter" in roles
        woodcutter_role = roles["WoodCutter"]
        assert woodcutter_role["primary_task"] == "harvest_wood"
        assert woodcutter_role["secondary_task"] == "craft_fire"
        assert "wood" in [item.lower() for item in woodcutter_role["required_items"]]
        assert "basic_fire" in woodcutter_role["crafting_recipes"]

        # Fisher role
        assert "Fisher" in roles
        fisher_role = roles["Fisher"]
        assert fisher_role["primary_task"] == "fishing"
        assert fisher_role["secondary_task"] == "find_fire"
        assert "fish" in [item.lower() for item in fisher_role["target_items"]]
        assert any("fire" in obj.lower() for obj in fisher_role["seeks_objects"])

        # Verify cooperation mechanics
        assert "cooperation_mechanics" in info
        mechanics = info["cooperation_mechanics"]
        assert "wood_to_fire" in mechanics
        assert "fire_benefits" in mechanics
        assert "proximity_required" in mechanics

    @pytest.mark.asyncio
    async def test_inventory_modification(self, scenario, mock_server):
        """Test that agents get appropriate starting inventories"""
        scenario.server = mock_server

        # Create mock inventory slots
        fishing_rod_slot = Mock()
        fishing_rod_slot.is_empty.return_value = False
        fishing_rod_slot.item = Mock()
        fishing_rod_slot.item.name = "Fishing Rod"

        empty_slot = Mock()
        empty_slot.is_empty.return_value = True

        mock_woodcutter_state = Mock()
        mock_woodcutter_state.inventory = Mock()
        mock_woodcutter_state.inventory.slots = [fishing_rod_slot, empty_slot, empty_slot]

        mock_fisher_state = Mock()

        mock_server.agent_registry.register_agent.side_effect = [
            mock_woodcutter_state,
            mock_fisher_state
        ]

        await scenario.spawn_agents()

        # Verify woodcutter inventory was modified (fishing rod removed)
        # The slots should be filtered to remove fishing rod
        assert mock_woodcutter_state.inventory.slots != [fishing_rod_slot, empty_slot, empty_slot]

    def test_scenario_seed_and_terrain(self, scenario):
        """Test scenario uses appropriate seed and terrain for cooperation"""
        assert scenario.seed == 300  # Specific seed for good forest/water distribution
        assert scenario.terrain_type == TerrainType.MIXED  # Mixed terrain for both agents

    def test_map_size_for_cooperation(self, scenario):
        """Test map size is appropriate for close cooperation"""
        assert scenario.map_size == 20  # Small map for agent interaction

        # Verify map is small enough for agents to find each other easily
        max_distance = (scenario.map_size * 1.414)  # Diagonal distance
        assert max_distance < 30  # Reasonable for cooperation

    @pytest.mark.asyncio
    async def test_spawn_agent_rotations(self, scenario, mock_server):
        """Test that agents spawn with different rotations"""
        scenario.server = mock_server

        mock_state = Mock()
        mock_state.inventory = Mock()
        mock_state.inventory.slots = []

        mock_server.agent_registry.register_agent.return_value = mock_state

        await scenario.spawn_agents()

        # Verify spawn_agent was called with different rotations
        spawn_calls = mock_server.world.spawn_agent.call_args_list

        assert len(spawn_calls) == 2
        woodcutter_call = spawn_calls[0]
        fisher_call = spawn_calls[1]

        # Agents should have different rotations (45.0 vs 225.0 degrees)
        woodcutter_rotation = woodcutter_call[0][3]  # 4th argument is rotation
        fisher_rotation = fisher_call[0][3]

        assert woodcutter_rotation == 45.0
        assert fisher_rotation == 225.0
        assert woodcutter_rotation != fisher_rotation

    def test_scenario_description_accuracy(self, scenario):
        """Test that scenario description matches expected behaviors"""
        description = scenario.description.lower()

        # Should mention key cooperation elements
        assert "wood cutter" in description
        assert "fisher" in description
        assert "cooperate" in description or "cooperation" in description
        assert "harvest" in description or "wood" in description
        assert "fish" in description or "fishing" in description
        assert "fire" in description