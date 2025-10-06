from __future__ import annotations

import math
from typing import TYPE_CHECKING, List, Optional, Tuple

from ..systems.pathfinding import Pathfinder
from .base import Action, ActionResult, Event, ResourceCost

if TYPE_CHECKING:
    from ..core.world import World
    from ..entities.base import Entity


class MoveAction(Action):
    def __init__(self, actor_id: int, destination: Tuple[int, int]):
        super().__init__(actor_id)
        self.destination = destination

    def can_execute(self, actor: Entity, world: World) -> bool:
        if not world.is_valid_position(self.destination[0], self.destination[1]):
            return False

        if not world.is_passable(self.destination[0], self.destination[1]):
            return False

        current_x, current_y = actor.position
        dest_x, dest_y = self.destination

        distance = math.sqrt((dest_x - current_x) ** 2 + (dest_y - current_y) ** 2)
        if distance > 1.5:
            return False

        return self.get_cost().can_afford(actor)

    def execute(self, actor: Entity, world: World) -> ActionResult:
        if not self.can_execute(actor, world):
            return ActionResult.failure("Cannot move to destination")

        cost = self.get_cost()
        if not cost.consume(actor):
            return ActionResult.failure("Not enough resources to move")

        success = world.move_entity(actor, self.destination[0], self.destination[1])
        if success:
            event = Event(
                event_type="move",
                actor_id=actor.id,
                data={"from": actor.position, "to": self.destination},
            )
            return ActionResult.success(f"Moved to {self.destination}", [event])
        else:
            return ActionResult.failure("Failed to move")

    def get_duration(self) -> int:
        return 1

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=1)

    def __repr__(self) -> str:
        return f"MoveAction(to={self.destination})"


class PathfindAction(Action):
    def __init__(
        self,
        actor_id: int,
        destination: Tuple[int, int],
        pathfinder: Optional[Pathfinder] = None,
        use_fog_of_war: bool = False,
    ):
        super().__init__(actor_id)
        self.destination = destination
        self.pathfinder = pathfinder or Pathfinder()
        self.use_fog_of_war = use_fog_of_war
        self.path: List[Tuple[int, int]] = []
        self.current_step = 0

    def can_execute(self, actor: Entity, world: World) -> bool:
        if not world.is_valid_position(self.destination[0], self.destination[1]):
            return False

        if not world.is_passable(self.destination[0], self.destination[1]):
            return False

        known_tiles = None
        if self.use_fog_of_war and hasattr(actor, "known_map"):
            known_tiles = actor.known_map.get_explored_tiles()

        self.path = self.pathfinder.find_path(
            actor.position, self.destination, world, known_tiles
        )

        if not self.path or len(self.path) < 2:
            return False

        return True

    def execute(self, actor: Entity, world: World) -> ActionResult:
        if not self.path and not self.can_execute(actor, world):
            return ActionResult.failure("No path to destination")

        if self.current_step >= len(self.path) - 1:
            return ActionResult.success("Destination reached")

        next_position = self.path[self.current_step + 1]

        move_action = MoveAction(self.actor_id, next_position)
        result = move_action.execute(actor, world)

        if result.success:
            self.current_step += 1

            if self.current_step >= len(self.path) - 1:
                return ActionResult.success("Pathfinding complete", result.events)
            else:
                return ActionResult(
                    success=True,
                    message=f"Step {self.current_step}/{len(self.path)-1}",
                    events=result.events,
                )
        else:
            known_tiles = None
            if self.use_fog_of_war and hasattr(actor, "known_map"):
                known_tiles = actor.known_map.get_explored_tiles()

            new_path = self.pathfinder.find_path(
                actor.position, self.destination, world, known_tiles
            )

            if new_path and len(new_path) > 1:
                self.path = new_path
                self.current_step = 0
                return ActionResult(
                    success=True, message="Recalculating path", events=[]
                )
            else:
                return ActionResult.failure("Path blocked and no alternative found")

    def get_duration(self) -> int:
        return len(self.path) if self.path else 1

    def get_cost(self) -> ResourceCost:
        path_length = len(self.path) if self.path else 1
        return ResourceCost(stamina=path_length)

    def get_remaining_steps(self) -> int:
        if not self.path:
            return 0
        return len(self.path) - 1 - self.current_step

    def get_current_target(self) -> Optional[Tuple[int, int]]:
        if not self.path or self.current_step >= len(self.path) - 1:
            return None
        return self.path[self.current_step + 1]

    def __repr__(self) -> str:
        return f"PathfindAction(to={self.destination}, step={self.current_step}/{len(self.path) if self.path else 0})"


class WanderAction(Action):
    def __init__(
        self,
        actor_id: int,
        center: Optional[Tuple[int, int]] = None,
        max_distance: int = 5,
    ):
        super().__init__(actor_id)
        self.center = center
        self.max_distance = max_distance
        self.target_position: Optional[Tuple[int, int]] = None
        self.pathfind_action: Optional[PathfindAction] = None

    def can_execute(self, actor: Entity, world: World) -> bool:
        center = self.center if self.center else actor.position

        candidates = []
        cx, cy = center
        for dx in range(-self.max_distance, self.max_distance + 1):
            for dy in range(-self.max_distance, self.max_distance + 1):
                if dx == 0 and dy == 0:
                    continue

                x, y = cx + dx, cy + dy
                if world.is_valid_position(x, y) and world.is_passable(x, y):
                    distance = math.sqrt(dx**2 + dy**2)
                    if distance <= self.max_distance:
                        candidates.append((x, y))

        if not candidates:
            return False

        import random

        self.target_position = random.choice(candidates)
        return True

    def execute(self, actor: Entity, world: World) -> ActionResult:
        if not self.target_position:
            if not self.can_execute(actor, world):
                return ActionResult.failure("No valid wandering destination")

        # Create pathfind action once and reuse it
        if not self.pathfind_action:
            self.pathfind_action = PathfindAction(self.actor_id, self.target_position)
            self.pathfind_action.start(self.start_tick)
            self.pathfind_action.is_active = True

        return self.pathfind_action.execute(actor, world)

    def get_duration(self) -> int:
        # Duration is dynamic based on pathfinding, but we need a reasonable estimate
        if self.pathfind_action:
            return self.pathfind_action.get_duration()
        elif self.target_position:
            # Rough estimate based on max distance
            return self.max_distance + 2
        return 5  # Default estimate

    def get_cost(self) -> ResourceCost:
        return ResourceCost(stamina=2)

    def __repr__(self) -> str:
        return f"WanderAction(center={self.center}, max_dist={self.max_distance})"
