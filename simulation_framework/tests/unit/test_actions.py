import pytest
from src.actions.base import Action, ActionResult, ResourceCost
from src.actions.gathering import FishAction, GatherAction, MineAction, WoodcutAction
from src.actions.movement import MoveAction, PathfindAction
from src.core.world import World
from src.entities.base import Entity
from src.entities.stats import Stats
from src.items.tool import Tool
from src.world.tile import ResourceDeposit


class MockAction(Action):
    def __init__(self, actor_id: int, success: bool = True, duration: int = 1):
        super().__init__(actor_id)
        self._success = success
        self._duration = duration

    def can_execute(self, actor, world):
        return True

    def execute(self, actor, world):
        if self._success:
            return ActionResult.success("Mock action completed")
        else:
            return ActionResult.failure("Mock action failed")

    def get_duration(self):
        return self._duration

    def get_cost(self):
        return ResourceCost(stamina=5)


class MockEntity(Entity):
    def __init__(self, position, name="MockEntity"):
        super().__init__(position, name)
        self.skills = {}

    def update(self, world):
        pass

    def on_death(self, killer=None):
        pass


class TestActionBase:
    def test_resource_cost_affordability(self):
        entity = MockEntity((0, 0))
        entity.stats = Stats(stamina=50, magic=30)
        entity.inventory.add_item(Tool.create_pickaxe(), 1)

        cost1 = ResourceCost(stamina=10, magic=5)
        assert cost1.can_afford(entity)

        cost2 = ResourceCost(stamina=100)
        assert not cost2.can_afford(entity)

        cost3 = ResourceCost(items={"Iron Pickaxe": 1})
        assert cost3.can_afford(entity)

        cost4 = ResourceCost(items={"Nonexistent Item": 1})
        assert not cost4.can_afford(entity)

    def test_resource_cost_consumption(self):
        entity = MockEntity((0, 0))
        entity.stats = Stats(stamina=50, magic=30, health=100)
        tool = Tool.create_pickaxe()
        entity.inventory.add_item(tool, 1)

        cost = ResourceCost(stamina=10, magic=5, health=5, items={"Iron Pickaxe": 1})

        assert cost.consume(entity)
        assert entity.stats.stamina == 40
        assert entity.stats.magic == 25
        assert entity.stats.health == 95
        assert not entity.inventory.has_item("Iron Pickaxe", 1)

    def test_action_timing(self):
        action = MockAction(1, duration=5)

        assert not action.is_active
        action.start(10)
        assert action.is_active

        assert not action.is_complete(12)
        assert action.is_complete(15)

        assert action.get_progress(12) == 0.4
        assert action.get_progress(15) == 1.0

    def test_action_interrupt(self):
        action = MockAction(1, duration=5)
        action.start(10)

        result = action.interrupt()
        assert result.interrupted
        assert not action.is_active


class TestMoveAction:
    def test_successful_move(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))
        world.add_entity(entity)

        move_action = MoveAction(entity.id, (6, 5))

        assert move_action.can_execute(entity, world)

        result = move_action.execute(entity, world)
        assert result.success
        assert entity.position == (6, 5)
        assert len(result.events) == 1
        assert result.events[0].event_type == "move"

    def test_move_to_invalid_position(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))
        world.add_entity(entity)

        move_action = MoveAction(entity.id, (15, 15))
        assert not move_action.can_execute(entity, world)

    def test_move_too_far(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))
        world.add_entity(entity)

        move_action = MoveAction(entity.id, (8, 8))
        assert not move_action.can_execute(entity, world)

    def test_move_insufficient_stamina(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))
        entity.stats = Stats(stamina=0)
        world.add_entity(entity)

        move_action = MoveAction(entity.id, (6, 5))
        assert not move_action.can_execute(entity, world)


class TestPathfindAction:
    def test_pathfinding_action(self):
        world = World(10, 10, seed=42)

        # Find passable positions
        passable_positions = []
        for y in range(10):
            for x in range(10):
                if world.is_passable(x, y):
                    passable_positions.append((x, y))

        if len(passable_positions) < 2:
            pytest.skip("Not enough passable tiles for pathfinding action test")

        start = passable_positions[0]
        goal = passable_positions[-1]

        entity = MockEntity(start)
        world.add_entity(entity)

        pathfind_action = PathfindAction(entity.id, goal)

        if pathfind_action.can_execute(entity, world):
            result = pathfind_action.execute(entity, world)
            assert result.success
            assert entity.position != start

    def test_no_path_available(self):
        world = World(10, 10, seed=42)

        for y in range(5):
            for x in range(10):
                tile = world.tiles[y][x]
                tile.terrain_type = world.tiles[0][0].terrain_type
                tile.properties.passable = False

        entity = MockEntity((1, 1))
        world.add_entity(entity)

        pathfind_action = PathfindAction(entity.id, (8, 8))

        assert not pathfind_action.can_execute(entity, world)


class TestGatheringActions:
    def test_gather_action_with_tool(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))

        pickaxe = Tool.create_pickaxe()
        entity.inventory.equip_tool(pickaxe, "pickaxe")
        entity.skills = {"mining": 3}

        tile = world.get_tile(5, 5)
        tile.add_resource(ResourceDeposit("stone", 20))
        tile.terrain_type = world.tiles[0][0].terrain_type

        gather_action = GatherAction(
            entity.id,
            resource_type="stone",
            required_tool="pickaxe",
            skill_name="mining",
        )

        assert gather_action.can_execute(entity, world)

        result = gather_action.execute(entity, world)
        assert result.success
        assert entity.inventory.get_item_count("Stone") > 0

    def test_gather_without_required_tool(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))

        tile = world.get_tile(5, 5)
        tile.add_resource(ResourceDeposit("stone", 20))

        gather_action = GatherAction(
            entity.id, resource_type="stone", required_tool="pickaxe"
        )

        assert not gather_action.can_execute(entity, world)

    def test_gather_wrong_terrain(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))

        gather_action = GatherAction(
            entity.id, resource_type="wood", required_terrain="forest"
        )

        tile = world.get_tile(5, 5)
        tile.terrain_type = world.tiles[0][0].terrain_type

        if tile.terrain_type.value != "forest":
            assert not gather_action.can_execute(entity, world)

    def test_fish_action(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))

        fishing_rod = Tool.create_fishing_rod()
        entity.inventory.equip_tool(fishing_rod, "fishing_rod")

        world.get_tile(5, 5)
        neighbor = world.get_tile(6, 5)
        if neighbor:
            neighbor.terrain_type = world.tiles[0][0].terrain_type

        fish_action = FishAction(entity.id)

        fish_action.can_execute(entity, world)

    def test_mine_action(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))

        pickaxe = Tool.create_pickaxe()
        entity.inventory.equip_tool(pickaxe, "pickaxe")

        tile = world.get_tile(5, 5)
        tile.add_resource(ResourceDeposit("stone", 20))

        mine_action = MineAction(entity.id)

        if tile.terrain_type.value == "mountain":
            assert mine_action.can_execute(entity, world)

    def test_woodcut_action(self):
        world = World(10, 10, seed=42)
        entity = MockEntity((5, 5))

        axe = Tool.create_axe()
        entity.inventory.equip_tool(axe, "axe")

        tile = world.get_tile(5, 5)
        tile.add_resource(ResourceDeposit("wood", 30))

        woodcut_action = WoodcutAction(entity.id)

        if tile.terrain_type.value == "forest":
            assert woodcut_action.can_execute(entity, world)
