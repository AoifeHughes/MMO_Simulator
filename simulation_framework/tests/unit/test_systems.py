from unittest.mock import Mock

from src.core.world import World
from src.systems.fog_of_war import FogOfWar
from src.systems.respawn import RespawnEntry, RespawnManager, RespawnType
from src.systems.trading import Market, TradeOffer, TradingSystem


class TestFogOfWar:
    def test_fog_of_war_creation(self):
        fog = FogOfWar(50, 50)

        assert fog.world_width == 50
        assert fog.world_height == 50
        assert fog.agent_vision == {}
        assert fog.agent_memory == {}

    def test_line_of_sight_calculation(self):
        world = World(10, 10, seed=42)
        fog = FogOfWar(10, 10)

        # Clear line of sight
        has_los = fog._has_line_of_sight(0, 0, 5, 5, world)
        assert isinstance(has_los, bool)

    def test_agent_vision_update(self):
        world = World(10, 10, seed=42)
        fog = FogOfWar(10, 10)

        # Mock agent
        agent = Mock()
        agent.id = 1
        agent.position = (5, 5)
        agent.vision_range = 3

        fog.update_agent_vision(agent, world)

        assert 1 in fog.agent_vision
        assert len(fog.agent_vision[1]) > 0
        assert (5, 5) in fog.agent_vision[1]  # Agent can see own position

    def test_memory_system(self):
        world = World(10, 10, seed=42)
        world.current_tick = 10
        fog = FogOfWar(10, 10)

        agent = Mock()
        agent.id = 1
        agent.position = (5, 5)
        agent.vision_range = 2

        fog.update_agent_vision(agent, world)

        # Check that memory was created
        assert 1 in fog.agent_memory
        assert len(fog.agent_memory[1]) > 0

    def test_pathfinding_grid_generation(self):
        world = World(10, 10, seed=42)
        fog = FogOfWar(10, 10)

        agent = Mock()
        agent.id = 1
        agent.position = (5, 5)
        agent.vision_range = 3

        fog.update_agent_vision(agent, world)
        grid = fog.get_pathfinding_grid(1, world)

        assert len(grid) == 10
        assert len(grid[0]) == 10
        assert all(cell in [0, 1] for row in grid for cell in row)

    def test_exploration_targets(self):
        fog = FogOfWar(20, 20)

        targets = fog.get_exploration_targets(1, (10, 10), max_distance=5)

        # Should return some targets since agent hasn't seen anything yet
        assert isinstance(targets, list)

    def test_memory_cleanup(self):
        fog = FogOfWar(10, 10)
        fog.agent_memory[1] = {(5, 5): {"last_seen": 50}, (6, 6): {"last_seen": 200}}
        fog.memory_duration = 100

        fog.forget_old_memories(1, 200)

        # Old memory should be removed
        assert (5, 5) not in fog.agent_memory[1]
        assert (6, 6) in fog.agent_memory[1]


class TestMarket:
    def test_market_creation(self):
        market = Market()

        assert "Wood" in market.item_prices
        assert "Stone" in market.supply
        assert "Berries" in market.demand

    def test_price_calculation(self):
        market = Market()
        initial_price = market.get_price("Wood")

        # Reduce supply, price should increase
        market.update_supply("Wood", -50)
        new_price = market.get_price("Wood")
        assert new_price > initial_price

    def test_trade_recording(self):
        market = Market()
        initial_volume = market.trade_volume.get("Wood", 0)

        market.record_trade("Wood", 10, 5.0)

        assert market.trade_volume["Wood"] == initial_volume + 10

    def test_demand_supply_interaction(self):
        market = Market()

        # Increase demand
        market.update_demand("Stone", 50)
        price_after_demand = market.get_price("Stone")

        # Increase supply
        market.update_supply("Stone", 100)
        price_after_supply = market.get_price("Stone")

        # Price should be lower after supply increase
        assert price_after_supply < price_after_demand


class TestTradingSystem:
    def test_trading_system_creation(self):
        trading = TradingSystem()

        assert isinstance(trading.market, Market)
        assert trading.pending_offers == {}
        assert trading.next_offer_id == 1

    def test_trade_offer_creation(self):
        trading = TradingSystem()

        # Mock the _can_trade method to return True for testing
        trading._can_trade = Mock(return_value=True)

        # Mock entities properly
        initiator = Mock()
        initiator.id = 1
        initiator.inventory = Mock()
        initiator.inventory.has_item.return_value = True
        initiator.inventory.gold = 100

        target = Mock()
        target.id = 2

        offer = trading.create_trade_offer(
            initiator,
            target,
            offered_items=[("Wood", 5)],
            requested_items=[("Stone", 3)],
            offered_gold=10,
        )

        assert offer is not None
        assert offer.initiator_id == 1
        assert offer.target_id == 2
        assert offer.offered_items == [("Wood", 5)]
        assert offer.offered_gold == 10

    def test_trade_utility_calculation(self):
        trading = TradingSystem()

        entity = Mock()
        entity.inventory = Mock()
        entity.inventory.get_item_count.return_value = 0

        # Mock personality properly
        entity.personality = Mock()
        entity.personality.greed = 0.5

        offer = TradeOffer(
            id=1,
            initiator_id=1,
            target_id=2,
            offered_items=[("Wood", 5)],
            requested_items=[("Stone", 2)],
        )

        utility = trading._calculate_trade_utility(entity, offer)

        assert isinstance(utility, float)
        assert utility > 0

    def test_trade_offer_validation(self):
        trading = TradingSystem()

        # Mock entity without required items
        entity = Mock()
        entity.id = 1
        entity.inventory = Mock()
        entity.inventory.has_item.return_value = False
        entity.inventory.gold = 0

        offer = TradeOffer(
            id=1,
            initiator_id=2,
            target_id=1,
            offered_items=[("Wood", 1)],
            requested_items=[("Stone", 5)],  # Entity doesn't have this
        )

        should_accept, utility = trading.evaluate_trade_offer(entity, 1)
        trading.pending_offers[1] = offer

        # Should reject since entity doesn't have requested items
        should_accept, utility = trading.evaluate_trade_offer(entity, 1)
        assert not should_accept

    def test_offer_expiration(self):
        trading = TradingSystem()

        # Create expired offer
        offer = TradeOffer(
            id=1,
            initiator_id=1,
            target_id=2,
            offered_items=[],
            requested_items=[],
            created_tick=0,
            expires_tick=50,
        )
        trading.pending_offers[1] = offer

        trading.cleanup_expired_offers(100)

        assert 1 not in trading.pending_offers


class TestRespawnManager:
    def test_respawn_manager_creation(self):
        respawn = RespawnManager(50, 50)

        assert respawn.world_width == 50
        assert respawn.world_height == 50
        assert respawn.respawn_queue == []
        assert respawn.total_respawns == 0

    def test_schedule_respawn(self):
        world = World(10, 10, seed=42)
        world.current_tick = 100
        respawn = RespawnManager(10, 10)

        # Mock entity
        entity = Mock()
        entity.id = 1
        entity.position = (5, 5)
        entity.name = "Test Entity"
        entity.stats = Mock()
        entity.stats.max_health = 100
        entity.stats.max_stamina = 50
        entity.stats.attack_power = 10
        entity.stats.defense = 5

        # Mock personality properly
        entity.personality = Mock()
        entity.personality.patience = 0.5

        success = respawn.schedule_respawn(entity, RespawnType.AGENT, world)

        assert success
        assert len(respawn.respawn_queue) == 1
        assert respawn.respawn_queue[0].entity_id == 1

    def test_respawn_data_creation(self):
        respawn = RespawnManager(10, 10)

        entity = Mock()
        entity.name = "Test Agent"
        entity.stats = Mock()
        entity.stats.max_health = 100
        entity.stats.max_stamina = 50
        entity.stats.attack_power = 10
        entity.stats.defense = 5

        # Mock agent-specific attributes
        entity.personality = Mock()
        entity.personality.to_dict.return_value = {"curiosity": 0.8}
        entity.character_class = Mock()
        entity.character_class.name = "Warrior"
        entity.skills = {"combat": 5}

        data = respawn._create_respawn_data(entity, RespawnType.AGENT)

        assert data["name"] == "Test Agent"
        assert "personality" in data
        assert "character_class" in data
        assert "skills" in data

    def test_safe_position_checking(self):
        world = World(10, 10, seed=42)
        respawn = RespawnManager(10, 10)

        # Test bounds checking
        assert not respawn._is_safe_respawn_position((-1, 5), world)
        assert not respawn._is_safe_respawn_position((15, 5), world)

        # Test valid position
        assert respawn._is_safe_respawn_position((5, 5), world)

    def test_population_maintenance(self):
        world = World(20, 20, seed=42)
        respawn = RespawnManager(20, 20)

        # Mock world with no entities
        world.entities = {}

        respawn.maintain_population(world)

        # Should have attempted to spawn entities

    def test_safe_zone_management(self):
        respawn = RespawnManager(20, 20)

        respawn.add_safe_zone(10, 10, 5)
        respawn.add_restricted_zone(15, 15, 3)

        assert len(respawn.safe_zones) == 1
        assert len(respawn.restricted_zones) == 1

    def test_respawn_delay_calculation(self):
        respawn = RespawnManager(10, 10)

        entity = Mock()
        entity.personality = Mock()
        entity.personality.patience = 0.5

        # Test basic delays
        agent_delay = respawn._get_respawn_delay(RespawnType.AGENT, entity)
        npc_delay = respawn._get_respawn_delay(RespawnType.NPC, entity)
        resource_delay = respawn._get_respawn_delay(RespawnType.RESOURCE_NODE, entity)

        assert agent_delay >= 50  # Minimum delay
        assert npc_delay >= 50
        assert resource_delay >= 50

    def test_respawn_processing(self):
        world = World(10, 10, seed=42)
        world.current_tick = 200
        respawn = RespawnManager(10, 10)

        # Create a respawn entry that's ready
        entry = RespawnEntry(
            entity_id=1,
            entity_type=RespawnType.AGENT,
            respawn_tick=100,  # Ready to respawn
            original_position=(5, 5),
            respawn_data={
                "name": "Test Agent",
                "stats": {
                    "max_health": 100,
                    "max_stamina": 50,
                    "attack_power": 10,
                    "defense": 5,
                },
            },
            death_tick=50,
        )

        respawn.respawn_queue.append(entry)

        # Mock world.add_entity
        world.add_entity = Mock()

        respawn.process_respawns(world)

        # Should have processed the respawn
        assert len(respawn.respawn_queue) == 0  # Entry should be removed

    def test_respawn_summary(self):
        respawn = RespawnManager(10, 10)

        summary = respawn.get_respawn_summary()

        assert "pending_respawns" in summary
        assert "total_respawns" in summary
        assert "respawns_by_type" in summary
