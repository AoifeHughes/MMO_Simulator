from __future__ import annotations
from typing import Optional, List, Tuple, TYPE_CHECKING
import random

from .base import Entity
from .stats import Stats
from ..items.loot_table import LootTable

if TYPE_CHECKING:
    from ..core.world import World


class NPC(Entity):
    def __init__(
        self,
        position: Tuple[int, int],
        name: str = "NPC",
        npc_type: str = "neutral",
        stats: Optional[Stats] = None,
        loot_table: Optional[LootTable] = None,
        spawn_point: Optional[Tuple[int, int]] = None,
        tether_radius: int = 10
    ):
        super().__init__(position, name, stats or Stats())
        self.npc_type = npc_type
        self.loot_table = loot_table or LootTable()
        self.spawn_point = spawn_point or position
        self.tether_radius = tether_radius
        self.aggro_range = 5
        self.target_id: Optional[int] = None
        self.last_seen_target_pos: Optional[Tuple[int, int]] = None
        self.patrol_points: List[Tuple[int, int]] = []
        self.current_patrol_index = 0
        self.idle_timer = 0
        self.aggro_cooldown = 0
        self.current_action = None  # Track current action like agents do

    def update(self, world: World) -> None:
        self.update_status_effects()
        self._update_aggro_cooldown()

        if not self.stats.is_alive():
            return

        if self._is_too_far_from_spawn():
            self._return_to_spawn(world)
            return

        if self.target_id and self._should_continue_combat(world):
            self._combat_behavior(world)
        elif self.npc_type == "aggressive":
            self._scan_for_targets(world)

        if not self.target_id:
            self._idle_behavior(world)

    def _update_aggro_cooldown(self) -> None:
        if self.aggro_cooldown > 0:
            self.aggro_cooldown -= 1

    def _is_too_far_from_spawn(self) -> bool:
        spawn_x, spawn_y = self.spawn_point
        current_x, current_y = self.position
        distance = ((current_x - spawn_x)**2 + (current_y - spawn_y)**2)**0.5
        return distance > self.tether_radius

    def _return_to_spawn(self, world: World) -> None:
        self.target_id = None
        self.last_seen_target_pos = None

    def _should_continue_combat(self, world: World) -> bool:
        if not self.target_id:
            return False

        target = world.entities.get(self.target_id)
        if not target or not target.stats.is_alive():
            self.target_id = None
            return False

        distance = self.distance_to(target)
        if distance > self.aggro_range * 2:
            self.target_id = None
            return False

        return True

    def _combat_behavior(self, world: World) -> None:
        target = world.entities.get(self.target_id)
        if not target:
            self.target_id = None
            return

        self.last_seen_target_pos = target.position
        distance = self.distance_to(target)

        # Only set new action if we don't have one already
        if not self.current_action or not self.current_action.is_active:
            # Initiate combat if in range
            if distance <= 1.5:
                from ..actions.combat import MeleeAttack
                attack = MeleeAttack(self.id, self.target_id)
                if attack.can_execute(self, world):
                    self.current_action = attack
                    self.current_action.start(world.current_tick)  # Start the action
            else:
                # Move closer to target
                from ..actions.movement import PathfindAction
                pathfind = PathfindAction(self.id, target.position)
                if pathfind.can_execute(self, world):
                    self.current_action = pathfind
                    self.current_action.start(world.current_tick)  # Start the action

    def _scan_for_targets(self, world: World) -> None:
        if self.aggro_cooldown > 0:
            return

        current_x, current_y = self.position

        for entity in world.entities.values():
            if entity.id == self.id:
                continue

            if not entity.stats.is_alive():
                continue

            distance = self.distance_to(entity)
            if distance <= self.aggro_range:
                if hasattr(entity, 'inventory'):
                    self.target_id = entity.id
                    self.aggro_cooldown = 5
                    break

    def _idle_behavior(self, world: World) -> None:
        self.idle_timer += 1

        if self.idle_timer >= random.randint(10, 30):
            self.idle_timer = 0
            self._perform_idle_action(world)

    def _perform_idle_action(self, world: World) -> None:
        if self.patrol_points:
            self._patrol(world)
        else:
            self._wander(world)

    def _patrol(self, world: World) -> None:
        if not self.patrol_points:
            return

        target_point = self.patrol_points[self.current_patrol_index]

        if self.distance_to_position(*target_point) < 1.5:
            self.current_patrol_index = (self.current_patrol_index + 1) % len(self.patrol_points)
        else:
            from ..actions.movement import PathfindAction
            pathfind = PathfindAction(self.id, target_point)
            if pathfind.can_execute(self, world):
                pathfind.execute(self, world)

    def _wander(self, world: World) -> None:
        # Only set new action if we don't have one already
        if not self.current_action or not self.current_action.is_active:
            from ..actions.movement import WanderAction
            wander = WanderAction(self.id, self.spawn_point, max_distance=3)
            if wander.can_execute(self, world):
                self.current_action = wander
                self.current_action.start(world.current_tick)  # Start the action

    def set_patrol_route(self, points: List[Tuple[int, int]]) -> None:
        self.patrol_points = points
        self.current_patrol_index = 0

    def add_patrol_point(self, point: Tuple[int, int]) -> None:
        self.patrol_points.append(point)

    def set_aggressive(self, aggressive: bool = True) -> None:
        self.npc_type = "aggressive" if aggressive else "neutral"

    def set_target(self, target: Entity) -> None:
        """Set a target for combat - called by simulation when agent comes within aggro range"""
        if target and target.stats.is_alive():
            self.target_id = target.id
            self.last_seen_target_pos = target.position
            self.aggro_cooldown = 5

    def on_death(self, killer: Optional[Entity] = None) -> None:
        if killer and self.loot_table:
            self._drop_loot(killer)

        self._register_for_respawn()

    def _drop_loot(self, killer: Entity) -> None:
        luck_modifier = getattr(killer, 'luck', 0) * 0.01
        loot_items = self.loot_table.generate_loot(luck_modifier)

        for item, quantity in loot_items:
            remaining = killer.inventory.add_item(item, quantity)
            if remaining > 0:
                pass

    def _register_for_respawn(self) -> None:
        pass

    def get_threat_level(self) -> str:
        total_stats = self.stats.max_health + self.stats.attack_power + self.stats.defense

        if total_stats < 50:
            return "weak"
        elif total_stats < 100:
            return "normal"
        elif total_stats < 200:
            return "strong"
        else:
            return "elite"

    def is_hostile_to(self, entity: Entity) -> bool:
        if self.npc_type == "aggressive":
            return hasattr(entity, 'inventory')
        return False

    def __repr__(self) -> str:
        status = "alive" if self.stats.is_alive() else "dead"
        target_info = f", target={self.target_id}" if self.target_id else ""
        return f"NPC(id={self.id}, name='{self.name}', type={self.npc_type}, {status}{target_info})"


def create_basic_goblin(position: Tuple[int, int]) -> NPC:
    stats = Stats(
        max_health=30,
        health=30,
        max_stamina=40,
        stamina=40,
        attack_power=8,
        defense=2,
        speed=6
    )

    loot_table = LootTable.create_basic_monster_loot()

    return NPC(
        position=position,
        name="Goblin",
        npc_type="aggressive",
        stats=stats,
        loot_table=loot_table
    )


def create_forest_wolf(position: Tuple[int, int]) -> NPC:
    stats = Stats(
        max_health=45,
        health=45,
        max_stamina=60,
        stamina=60,
        attack_power=12,
        defense=3,
        speed=8
    )

    loot_table = LootTable()
    from ..items.consumable import Consumable
    from ..items.item import Item

    meat = Item(
        id=200,
        name="Wolf Meat",
        item_type="material",
        properties={"resource_type": "meat"},
        value=8,
        description="Fresh wolf meat",
        max_stack_size=20
    )

    loot_table.add_entry(meat, 0.8, 1, 3)
    loot_table.add_entry(Consumable.create_food("Wolf Meat"), 0.4, 1, 2)

    wolf = NPC(
        position=position,
        name="Forest Wolf",
        npc_type="aggressive",
        stats=stats,
        loot_table=loot_table
    )
    wolf.aggro_range = 7
    return wolf


def create_peaceful_villager(position: Tuple[int, int]) -> NPC:
    stats = Stats(
        max_health=25,
        health=25,
        max_stamina=30,
        stamina=30,
        attack_power=3,
        defense=1,
        speed=4
    )

    return NPC(
        position=position,
        name="Villager",
        npc_type="neutral",
        stats=stats
    )