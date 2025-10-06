from src.entities.base import Entity
from src.entities.stats import Stats
from src.items.consumable import Consumable
from src.items.item import Item
from src.items.tool import Tool
from src.items.weapon import Weapon


class MockEntity(Entity):
    def update(self, world):
        pass

    def on_death(self, killer=None):
        pass


class TestItem:
    def test_item_creation(self):
        item = Item(
            id=1,
            name="Test Item",
            item_type="misc",
            properties={"color": "blue", "weight": 5},
            value=10,
        )

        assert item.name == "Test Item"
        assert item.item_type == "misc"
        assert item.get_property("color") == "blue"
        assert item.get_property("size", "medium") == "medium"

    def test_item_stacking(self):
        stackable = Item(1, "Arrow", "ammo", max_stack_size=50)
        unique = Item(2, "Sword", "weapon", max_stack_size=1)

        assert stackable.can_stack()
        assert not unique.can_stack()

    def test_item_serialization(self):
        original = Item(
            id=1,
            name="Magic Potion",
            item_type="consumable",
            properties={"heal": 50, "cooldown": 5},
            value=25,
        )

        data = original.to_dict()
        restored = Item.from_dict(data)

        assert restored.name == original.name
        assert restored.item_type == original.item_type
        assert restored.get_property("heal") == 50
        assert restored.value == 25


class TestWeapon:
    def test_sword_creation(self):
        sword = Weapon.create_sword()
        assert sword.item_type == "weapon"
        assert sword.get_damage() == 15
        assert sword.get_attack_type() == "melee"
        assert sword.get_range() == 1

    def test_bow_creation(self):
        bow = Weapon.create_bow()
        assert bow.get_attack_type() == "ranged"
        assert bow.get_range() == 15
        assert bow.get_damage() == 12

    def test_staff_creation(self):
        staff = Weapon.create_staff()
        assert staff.get_attack_type() == "magic"
        assert staff.get_magic_cost() == 10
        assert staff.get_range() == 20

    def test_weapon_stats(self):
        sword = Weapon.create_sword()
        assert sword.get_stamina_cost() == 5
        assert sword.get_critical_chance() == 0.15
        assert sword.get_critical_multiplier() == 2.0
        assert sword.get_damage_type() == "slashing"


class TestTool:
    def test_pickaxe_creation(self):
        pickaxe = Tool.create_pickaxe()
        assert pickaxe.item_type == "tool"
        assert pickaxe.get_tool_type() == "pickaxe"
        assert pickaxe.get_durability() == 100
        assert pickaxe.get_efficiency() == 1.5

    def test_tool_durability(self):
        axe = Tool.create_axe()
        initial_durability = axe.get_durability()

        assert axe.use(10)
        assert axe.get_durability() == initial_durability - 10

        repaired = axe.repair(5)
        assert repaired == 5
        assert axe.get_durability() == initial_durability - 5

    def test_tool_breaking(self):
        tool = Tool.create_fishing_rod()
        tool.set_property("durability", 5)

        assert not tool.is_broken()
        tool.use(10)
        assert tool.is_broken()
        assert not tool.use(1)

    def test_tool_types(self):
        pickaxe = Tool.create_pickaxe()
        axe = Tool.create_axe()
        fishing_rod = Tool.create_fishing_rod()
        hoe = Tool.create_hoe()

        assert pickaxe.get_tool_type() == "pickaxe"
        assert axe.get_tool_type() == "axe"
        assert fishing_rod.get_tool_type() == "fishing_rod"
        assert hoe.get_tool_type() == "hoe"


class TestConsumable:
    def test_health_potion(self):
        potion = Consumable.create_health_potion()
        entity = MockEntity((0, 0))
        entity.stats = Stats(max_health=100, health=50)
        entity.inventory.add_item(potion, 1)

        initial_health = entity.stats.health
        potion.consume(entity)

        assert entity.stats.health == initial_health + 50

    def test_stamina_potion(self):
        potion = Consumable.create_stamina_potion()
        entity = MockEntity((0, 0))
        entity.stats = Stats(max_stamina=100, stamina=25)
        entity.inventory.add_item(potion, 1)

        initial_stamina = entity.stats.stamina
        potion.consume(entity)

        assert entity.stats.stamina == initial_stamina + 50

    def test_poison_effect(self):
        poison = Consumable.create_poison()
        entity = MockEntity((0, 0))
        entity.stats = Stats(max_health=100, health=100)
        entity.inventory.add_item(poison, 1)

        poison.consume(entity)

        assert entity.has_status_effect("poisoned")

        for _ in range(10):
            entity.update_status_effects()

        assert entity.stats.health == 50

    def test_strength_elixir(self):
        elixir = Consumable.create_strength_elixir()
        entity = MockEntity((0, 0))
        entity.stats = Stats(attack_power=10)
        entity.inventory.add_item(elixir, 1)

        initial_attack = entity.stats.attack_power
        elixir.consume(entity)

        assert entity.stats.attack_power == initial_attack + 10
        assert entity.has_status_effect("strengthened")

    def test_food_consumption(self):
        bread = Consumable.create_food("Bread")
        entity = MockEntity((0, 0))
        entity.stats = Stats(max_health=100, health=80, max_stamina=100, stamina=60)
        entity.inventory.add_item(bread, 1)

        bread.consume(entity)

        assert entity.stats.health == 90
        assert entity.stats.stamina == 80

    def test_consumable_properties(self):
        potion = Consumable.create_health_potion()
        assert potion.get_cooldown() == 5
        assert potion.can_stack()
        assert potion.max_stack_size == 20
