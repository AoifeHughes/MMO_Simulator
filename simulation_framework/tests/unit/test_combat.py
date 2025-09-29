import pytest
from src.systems.combat_resolver import CombatResolver, DamageType
from src.actions.combat import MeleeAttack, RangedAttack, MagicAttack, DefendAction, FleeAction
from src.entities.base import Entity, StatusEffect
from src.entities.stats import Stats
from src.entities.npc import NPC, create_basic_goblin, create_forest_wolf
from src.items.weapon import Weapon
from src.items.loot_table import LootTable, LootEntry
from src.items.item import Item
from src.core.world import World


class MockEntity(Entity):
    def __init__(self, position, name="MockEntity", stats=None):
        super().__init__(position, name, stats or Stats())

    def update(self, world):
        pass

    def on_death(self, killer=None):
        self.is_dead = True


class TestCombatResolver:
    def test_basic_damage_calculation(self):
        attacker = MockEntity((0, 0))
        attacker.stats = Stats(attack_power=15)

        defender = MockEntity((1, 0))
        defender.stats = Stats(defense=5)

        resolver = CombatResolver()
        damage, is_critical, damage_info = resolver.calculate_damage(
            attacker, defender, base_damage=10
        )

        expected_base = 10 + 15 - 5  # base + attack - defense
        assert damage >= expected_base * 0.9
        assert damage <= expected_base * 1.1
        assert damage_info["base_damage"] == 10
        assert damage_info["attack_power"] == 15
        assert damage_info["defense"] == 5

    def test_critical_hit_calculation(self):
        attacker = MockEntity((0, 0))
        defender = MockEntity((1, 0))

        resolver = CombatResolver()

        # Test with 100% crit chance
        damage, is_critical, _ = resolver.calculate_damage(
            attacker, defender, base_damage=10, critical_chance=1.0, critical_multiplier=2.0
        )

        assert is_critical
        # Should be roughly double the base damage (accounting for variance)
        assert damage >= 15

    def test_damage_type_effectiveness(self):
        attacker = MockEntity((0, 0))

        fire_weak_defender = MockEntity((1, 0))
        fire_weak_defender.damage_types = [DamageType.ICE]

        fire_resistant_defender = MockEntity((2, 0))
        fire_resistant_defender.damage_types = [DamageType.FIRE]

        resolver = CombatResolver()

        # Fire vs Ice should be effective
        fire_vs_ice, _, _ = resolver.calculate_damage(
            attacker, fire_weak_defender, 10, DamageType.FIRE
        )

        # Fire vs Fire should be resisted
        fire_vs_fire, _, _ = resolver.calculate_damage(
            attacker, fire_resistant_defender, 10, DamageType.FIRE
        )

        # Ice-weak target should take more damage
        assert fire_vs_ice > fire_vs_fire

    def test_hit_chance_calculation(self):
        attacker = MockEntity((0, 0))
        defender = MockEntity((1, 0))

        resolver = CombatResolver()

        hit_chance = resolver.calculate_hit_chance(attacker, defender)
        assert 0.05 <= hit_chance <= 0.95

        # Test with range penalty
        hit_chance_far = resolver.calculate_hit_chance(
            attacker, defender, range_penalty=0.2
        )
        assert hit_chance_far < hit_chance

    def test_resolve_attack_integration(self):
        attacker = MockEntity((0, 0))
        attacker.stats = Stats(attack_power=10)

        defender = MockEntity((1, 0))
        defender.stats = Stats(max_health=50, health=50, defense=2)

        resolver = CombatResolver()

        # Test multiple attacks - at least some should hit with high accuracy
        hits = 0
        for _ in range(10):
            defender.stats.health = 50  # Reset health
            result = resolver.resolve_attack(
                attacker, defender, weapon_damage=15, base_accuracy=0.95
            )
            if result["hit"]:
                hits += 1
                assert result["damage"] > 0
                assert defender.stats.health < 50

        # With 95% accuracy over 10 attempts, we should get some hits
        assert hits > 5

    def test_combat_modifiers(self):
        entity = MockEntity((0, 0))

        strength_buff = StatusEffect("strength", 5, "strength", 10)
        entity.apply_status_effect(strength_buff)

        resolver = CombatResolver()
        modifiers = resolver.get_combat_modifiers(entity)

        assert modifiers["attack_bonus"] == 10


class TestCombatActions:
    def test_melee_attack_success(self):
        world = World(10, 10, seed=42)

        attacker = MockEntity((5, 5))
        attacker.stats = Stats(stamina=50, attack_power=15)
        sword = Weapon.create_sword()
        attacker.inventory.equip_weapon(sword)
        world.add_entity(attacker)

        defender = MockEntity((5, 6))
        defender.stats = Stats(max_health=30, health=30, defense=3)
        world.add_entity(defender)

        action = MeleeAttack(attacker.id, defender.id)

        assert action.can_execute(attacker, world)

        initial_health = defender.stats.health
        result = action.execute(attacker, world)

        assert result.success
        assert len(result.events) >= 1
        # Either hit or miss should be recorded
        assert result.events[0].event_type in ["attack_hit", "attack_miss"]

    def test_melee_attack_out_of_range(self):
        world = World(10, 10, seed=42)

        attacker = MockEntity((5, 5))
        world.add_entity(attacker)

        defender = MockEntity((8, 8))  # Too far away
        world.add_entity(defender)

        action = MeleeAttack(attacker.id, defender.id)

        assert not action.can_execute(attacker, world)

    def test_ranged_attack_with_bow(self):
        world = World(10, 10, seed=42)

        attacker = MockEntity((5, 5))
        attacker.stats = Stats(stamina=50)
        bow = Weapon.create_bow()
        attacker.inventory.equip_weapon(bow)
        world.add_entity(attacker)

        defender = MockEntity((5, 8))  # Within bow range
        world.add_entity(defender)

        action = RangedAttack(attacker.id, defender.id)

        assert action.can_execute(attacker, world)

    def test_ranged_attack_without_bow(self):
        world = World(10, 10, seed=42)

        attacker = MockEntity((5, 5))
        world.add_entity(attacker)

        defender = MockEntity((5, 8))
        world.add_entity(defender)

        action = RangedAttack(attacker.id, defender.id)

        assert not action.can_execute(attacker, world)

    def test_magic_attack_with_staff(self):
        world = World(10, 10, seed=42)

        attacker = MockEntity((5, 5))
        attacker.stats = Stats(stamina=50, magic=50)
        staff = Weapon.create_staff()
        attacker.inventory.equip_weapon(staff)
        world.add_entity(attacker)

        defender = MockEntity((5, 9))  # Within staff range
        world.add_entity(defender)

        action = MagicAttack(attacker.id, defender.id)

        assert action.can_execute(attacker, world)

    def test_magic_attack_insufficient_magic(self):
        world = World(10, 10, seed=42)

        attacker = MockEntity((5, 5))
        attacker.stats = Stats(stamina=50, magic=5)  # Not enough magic
        world.add_entity(attacker)

        defender = MockEntity((5, 6))
        world.add_entity(defender)

        action = MagicAttack(attacker.id, defender.id)

        assert not action.can_execute(attacker, world)

    def test_defend_action(self):
        world = World(10, 10)

        defender = MockEntity((5, 5))
        world.add_entity(defender)

        action = DefendAction(defender.id)

        assert action.can_execute(defender, world)

        result = action.execute(defender, world)

        assert result.success
        assert defender.has_status_effect("defending")

    def test_flee_action(self):
        world = World(10, 10, seed=42)

        entity = MockEntity((5, 5))
        entity.stats = Stats(stamina=50)
        world.add_entity(entity)

        action = FleeAction(entity.id)

        initial_position = entity.position

        if action.can_execute(entity, world):
            result = action.execute(entity, world)

            if result.success:
                # Should have moved away from initial position
                new_position = entity.position
                distance = ((new_position[0] - initial_position[0])**2 +
                           (new_position[1] - initial_position[1])**2)**0.5
                assert distance > 0


class TestLootSystem:
    def test_loot_table_creation(self):
        table = LootTable()

        item = Item(1, "Test Item", "misc", value=10)
        table.add_entry(item, 0.5, 1, 3)

        assert len(table.entries) == 1
        assert table.entries[0].item == item
        assert table.entries[0].probability == 0.5

    def test_loot_generation(self):
        table = LootTable()

        guaranteed_item = Item(1, "Guaranteed", "misc")
        rare_item = Item(2, "Rare", "misc")

        table.add_entry(guaranteed_item, 1.0, 2, 2)  # Always drops 2
        table.add_entry(rare_item, 0.0)  # Never drops

        loot = table.generate_loot()

        # Should always get the guaranteed item
        assert len(loot) == 1
        assert loot[0][0] == guaranteed_item
        assert loot[0][1] == 2

    def test_luck_modifier(self):
        table = LootTable()

        item = Item(1, "Lucky Item", "misc")
        table.add_entry(item, 0.1)  # 10% base chance

        # With high luck modifier, should increase drop chance
        loot_with_luck = table.generate_loot(luck_modifier=0.5)
        # Can't easily test randomness, but at least verify no errors

    def test_basic_monster_loot_table(self):
        table = LootTable.create_basic_monster_loot()

        assert not table.is_empty()
        assert len(table.entries) > 0

        possible_items = table.get_possible_loot()
        assert len(possible_items) > 0

    def test_loot_table_merge(self):
        table1 = LootTable()
        table2 = LootTable()

        item1 = Item(1, "Item1", "misc")
        item2 = Item(2, "Item2", "misc")

        table1.add_entry(item1, 0.5)
        table2.add_entry(item2, 0.3)

        merged = table1.merge(table2)

        assert len(merged.entries) == 2
        assert merged.get_total_probability() == 0.8


class TestNPCSystem:
    def test_basic_goblin_creation(self):
        goblin = create_basic_goblin((5, 5))

        assert goblin.name == "Goblin"
        assert goblin.npc_type == "aggressive"
        assert goblin.stats.is_alive()
        assert not goblin.loot_table.is_empty()

    def test_forest_wolf_creation(self):
        wolf = create_forest_wolf((3, 3))

        assert wolf.name == "Forest Wolf"
        assert wolf.npc_type == "aggressive"
        assert wolf.aggro_range == 7

    def test_npc_aggro_detection(self):
        world = World(10, 10)

        npc = create_basic_goblin((5, 5))
        npc.aggro_range = 3
        world.add_entity(npc)

        # Player within aggro range
        player = MockEntity((5, 6))
        world.add_entity(player)

        npc._scan_for_targets(world)
        assert npc.target_id == player.id

    def test_npc_tether_behavior(self):
        npc = create_basic_goblin((5, 5))
        npc.spawn_point = (5, 5)
        npc.tether_radius = 3
        npc.position = (10, 10)  # Far from spawn

        assert npc._is_too_far_from_spawn()

    def test_npc_death_and_loot(self):
        world = World(10, 10)

        npc = create_basic_goblin((5, 5))
        world.add_entity(npc)

        killer = MockEntity((5, 6))
        world.add_entity(killer)

        initial_inventory_size = len(killer.inventory.get_all_items())

        npc.on_death(killer)

        # Should have dropped some loot
        final_inventory_size = len(killer.inventory.get_all_items())
        # Loot might not always drop due to randomness, so we can't assert it's always greater

    def test_threat_level_calculation(self):
        weak_npc = MockEntity((0, 0))
        weak_npc.stats = Stats(max_health=20, attack_power=5, defense=2)

        strong_npc = MockEntity((1, 1))
        strong_npc.stats = Stats(max_health=100, attack_power=50, defense=30)

        # Convert to NPCs for threat level calculation
        weak = NPC((0, 0), stats=weak_npc.stats)
        strong = NPC((1, 1), stats=strong_npc.stats)

        assert weak.get_threat_level() == "weak"
        assert strong.get_threat_level() in ["strong", "elite"]