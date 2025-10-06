from src.core.world import World
from src.entities.base import Entity, StatusEffect
from src.entities.inventory import Inventory
from src.entities.stats import Stats
from src.items.item import Item
from src.items.weapon import Weapon


class MockEntity(Entity):
    def update(self, world):
        pass

    def on_death(self, killer=None):
        self.is_dead = True


class TestStats:
    def test_damage_and_healing(self):
        stats = Stats(max_health=100, health=100, defense=5)

        actual_damage = stats.take_damage(20)
        assert actual_damage == 15
        assert stats.health == 85

        healed = stats.heal(10)
        assert healed == 10
        assert stats.health == 95

        healed = stats.heal(20)
        assert healed == 5
        assert stats.health == 100

    def test_death_detection(self):
        stats = Stats(max_health=100, health=50)
        assert stats.is_alive()

        stats.take_damage(100)
        assert not stats.is_alive()
        assert stats.health == 0

    def test_stamina_management(self):
        stats = Stats(max_stamina=100, stamina=100)

        assert stats.use_stamina(30)
        assert stats.stamina == 70

        assert not stats.use_stamina(80)
        assert stats.stamina == 70

        restored = stats.restore_stamina(50)
        assert restored == 30
        assert stats.stamina == 100

    def test_magic_management(self):
        stats = Stats(max_magic=50, magic=50)

        assert stats.use_magic(20)
        assert stats.magic == 30

        assert not stats.use_magic(40)
        assert stats.magic == 30

        restored = stats.restore_magic(30)
        assert restored == 20
        assert stats.magic == 50

    def test_percentages(self):
        stats = Stats(
            max_health=100,
            health=75,
            max_stamina=100,
            stamina=50,
            max_magic=50,
            magic=25,
        )

        assert stats.get_health_percentage() == 0.75
        assert stats.get_stamina_percentage() == 0.50
        assert stats.get_magic_percentage() == 0.50


class TestInventory:
    def test_add_and_remove_items(self):
        inventory = Inventory(capacity=10)
        item = Item(1, "Sword", "weapon", max_stack_size=1)

        remaining = inventory.add_item(item, 1)
        assert remaining == 0
        assert inventory.has_item("Sword", 1)

        assert inventory.remove_item("Sword", 1)
        assert not inventory.has_item("Sword", 1)

    def test_stackable_items(self):
        inventory = Inventory()
        item = Item(2, "Arrow", "ammo", max_stack_size=50)

        inventory.add_item(item, 30)
        assert inventory.get_item_count("Arrow") == 30

        inventory.add_item(item, 25)
        assert inventory.get_item_count("Arrow") == 50

        remaining = inventory.add_item(item, 10)
        assert remaining == 10 or inventory.get_item_count("Arrow") == 60

    def test_inventory_overflow(self):
        inventory = Inventory(capacity=3)

        for i in range(5):
            item = Item(i, f"Item{i}", "misc", max_stack_size=1)
            inventory.add_item(item, 1)

        assert inventory.get_total_items() <= 3

    def test_equipment_management(self):
        inventory = Inventory()
        sword = Weapon.create_sword()
        bow = Weapon.create_bow()

        inventory.add_item(sword, 1)
        old_weapon = inventory.equip_weapon(sword)
        assert old_weapon is None
        assert inventory.get_equipped_weapon() == sword
        assert not inventory.has_item("Iron Sword", 1)

        inventory.add_item(bow, 1)
        old_weapon = inventory.equip_weapon(bow)
        assert old_weapon == sword
        assert inventory.get_equipped_weapon() == bow
        assert inventory.has_item("Iron Sword", 1)


class TestEntity:
    def test_entity_creation(self):
        entity = MockEntity((5, 5), name="TestEntity")
        assert entity.position == (5, 5)
        assert entity.name == "TestEntity"
        assert entity.stats.is_alive()

    def test_movement(self):
        world = World(10, 10)
        entity = MockEntity((5, 5))
        world.add_entity(entity)

        assert entity.move_to(6, 5, world)
        assert entity.position == (6, 5)

        water_pos = None
        for y in range(10):
            for x in range(10):
                if not world.is_passable(x, y):
                    water_pos = (x, y)
                    break
            if water_pos:
                break

        if water_pos:
            assert not entity.move_to(water_pos[0], water_pos[1], world)
            assert entity.position == (6, 5)

    def test_distance_calculations(self):
        entity1 = MockEntity((0, 0))
        entity2 = MockEntity((3, 4))

        distance = entity1.distance_to(entity2)
        assert distance == 5.0

        distance = entity1.distance_to_position(6, 8)
        assert distance == 10.0

    def test_vision_range(self):
        entity1 = MockEntity((0, 0))
        entity2 = MockEntity((5, 0))
        entity3 = MockEntity((15, 0))

        entity1.vision_range = 10

        assert entity1.can_see(entity2)
        assert not entity1.can_see(entity3)
        assert entity1.can_see(entity3, range_override=20)

    def test_damage_and_death(self):
        entity = MockEntity((0, 0))
        entity.stats = Stats(max_health=50, health=50, defense=5)

        damage = entity.take_damage(20)
        assert damage == 15
        assert entity.stats.health == 35

        entity.take_damage(100)
        assert not entity.stats.is_alive()
        assert hasattr(entity, "is_dead") and entity.is_dead

    def test_status_effects(self):
        entity = MockEntity((0, 0))
        entity.stats = Stats(max_health=100, health=100)

        poison = StatusEffect("poison", duration=3, effect_type="poison", power=5)
        entity.apply_status_effect(poison)

        assert entity.has_status_effect("poison")

        for _ in range(3):
            entity.update_status_effects()

        assert entity.stats.health == 85

        entity.update_status_effects()
        assert not entity.has_status_effect("poison")
