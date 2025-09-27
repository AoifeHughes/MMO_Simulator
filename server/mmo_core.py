"""
MMO-Style Server Core Architecture

This module implements the high-frequency, authoritative server architecture
similar to commercial MMO games. It provides:

- 60Hz server tick system with delta updates
- Authoritative world state management
- High-frequency position updates with client prediction support
- Transactional action processing with rollback
- Event-driven state synchronization
"""

import asyncio
import logging
import time
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class UpdateChannel(Enum):
    """Different update frequencies for different data types"""

    HIGH_FREQ = "high_freq"  # Position, movement - 60Hz
    MEDIUM_FREQ = "medium_freq"  # Health, combat - 20Hz
    LOW_FREQ = "low_freq"  # Inventory, stats - 5Hz
    EVENT_DRIVEN = "event"  # Actions, chat - immediate


@dataclass
class ServerTick:
    """Represents a single server tick with timing info"""

    tick_number: int
    timestamp: float
    delta_time: float
    tick_rate: float


class GameStateComponent(ABC):
    """Base class for all game state components"""

    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.last_update_time = 0.0
        self.dirty = True  # Whether this component needs to be sent to clients

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize component for network transmission"""
        pass

    @abstractmethod
    def apply_delta(self, delta: Dict[str, Any]) -> bool:
        """Apply delta update and return True if state changed"""
        pass

    def mark_dirty(self):
        """Mark this component as needing update"""
        self.dirty = True
        self.last_update_time = time.time()


class PositionComponent(GameStateComponent):
    """Authoritative position component with prediction support"""

    def __init__(
        self, entity_id: str, x: float = 0.0, y: float = 0.0, rotation: float = 0.0
    ):
        super().__init__(entity_id)
        self.x = x
        self.y = y
        self.rotation = rotation
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.target_x = x
        self.target_y = y
        self.move_speed = 5.0
        self.last_position_update = time.time()
        self.update_channel = UpdateChannel.HIGH_FREQ

    def set_target_position(
        self, target_x: float, target_y: float, speed: float = None
    ) -> bool:
        """Set target position for smooth movement"""
        if speed:
            self.move_speed = speed

        self.target_x = target_x
        self.target_y = target_y

        # Calculate velocity for smooth movement
        dx = target_x - self.x
        dy = target_y - self.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance > 0.01:  # Not already at target
            self.velocity_x = (dx / distance) * self.move_speed
            self.velocity_y = (dy / distance) * self.move_speed
            self.mark_dirty()
            return True
        else:
            self.velocity_x = 0.0
            self.velocity_y = 0.0
            return False

    def update_position(self, dt: float) -> bool:
        """Update position based on velocity and return if changed"""
        if abs(self.velocity_x) < 0.01 and abs(self.velocity_y) < 0.01:
            return False

        old_x, old_y = self.x, self.y

        # Move towards target
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance_to_target = (dx * dx + dy * dy) ** 0.5

        if distance_to_target < self.move_speed * dt:
            # Reached target
            self.x = self.target_x
            self.y = self.target_y
            self.velocity_x = 0.0
            self.velocity_y = 0.0
        else:
            # Continue moving
            self.x += self.velocity_x * dt
            self.y += self.velocity_y * dt

        # Check if position actually changed
        if abs(self.x - old_x) > 0.01 or abs(self.y - old_y) > 0.01:
            self.mark_dirty()
            return True

        return False

    def teleport_to(self, x: float, y: float, rotation: float = None):
        """Instantly move to position (for respawning, teleportation)"""
        self.x = x
        self.y = y
        self.target_x = x
        self.target_y = y
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        if rotation is not None:
            self.rotation = rotation

        self.mark_dirty()

    def get_predicted_position(self, dt_future: float) -> Tuple[float, float]:
        """Get predicted position for client prediction validation"""
        pred_x = self.x + self.velocity_x * dt_future
        pred_y = self.y + self.velocity_y * dt_future
        return pred_x, pred_y

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "rotation": round(self.rotation, 3),
            "velocity_x": round(self.velocity_x, 3),
            "velocity_y": round(self.velocity_y, 3),
            "timestamp": self.last_update_time,
        }

    def apply_delta(self, delta: Dict[str, Any]) -> bool:
        """Apply position delta (usually movement requests from clients)"""
        changed = False

        if "target_x" in delta and "target_y" in delta:
            if self.set_target_position(delta["target_x"], delta["target_y"]):
                changed = True

        if "rotation" in delta and abs(delta["rotation"] - self.rotation) > 0.01:
            self.rotation = delta["rotation"]
            self.mark_dirty()
            changed = True

        return changed


class HealthComponent(GameStateComponent):
    """Health and combat state component"""

    def __init__(self, entity_id: str, max_health: float = 100.0):
        super().__init__(entity_id)
        self.health = max_health
        self.max_health = max_health
        self.is_alive = True
        self.last_damage_time = 0.0
        self.update_channel = UpdateChannel.MEDIUM_FREQ

    def take_damage(
        self, damage: float, attacker_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Apply damage and return event data"""
        if not self.is_alive or damage <= 0:
            return {"damage_applied": 0.0, "died": False}

        old_health = self.health
        self.health = max(0.0, self.health - damage)
        self.last_damage_time = time.time()

        died = False
        if self.health <= 0 and old_health > 0:
            self.is_alive = False
            died = True

        self.mark_dirty()

        return {
            "damage_applied": damage,
            "health_after": self.health,
            "died": died,
            "attacker_id": attacker_id,
        }

    def heal(self, amount: float) -> float:
        """Heal and return actual amount healed"""
        if not self.is_alive or amount <= 0:
            return 0.0

        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        healed = self.health - old_health

        if healed > 0:
            self.mark_dirty()

        return healed

    def respawn(self, full_heal: bool = True):
        """Respawn the entity"""
        self.is_alive = True
        if full_heal:
            self.health = self.max_health
        self.mark_dirty()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "health": round(self.health, 1),
            "max_health": self.max_health,
            "is_alive": self.is_alive,
            "timestamp": self.last_update_time,
        }

    def apply_delta(self, delta: Dict[str, Any]) -> bool:
        """Apply health delta - usually from healing items"""
        changed = False

        if "heal" in delta:
            if self.heal(delta["heal"]) > 0:
                changed = True

        return changed


class AuthoritativeGameState:
    """
    Central authoritative game state manager.

    This is the single source of truth for all game state.
    All modifications go through this system.
    """

    def __init__(self):
        self.entities: Dict[str, Dict[str, GameStateComponent]] = {}
        self.event_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.tick_number = 0
        self.last_tick_time = time.time()
        self.state_lock = asyncio.Lock()

        # Update channel management
        self.update_queues: Dict[UpdateChannel, Dict[str, Set[str]]] = {
            channel: defaultdict(set) for channel in UpdateChannel
        }

    def create_entity(self, entity_id: str, entity_type: str = "agent") -> bool:
        """Create a new game entity"""
        if entity_id in self.entities:
            return False

        self.entities[entity_id] = {}

        # Add default components based on type
        if entity_type == "agent":
            self.add_component(entity_id, PositionComponent(entity_id))
            self.add_component(entity_id, HealthComponent(entity_id))

        self.emit_event("entity_created", {"entity_id": entity_id, "type": entity_type})
        return True

    def destroy_entity(self, entity_id: str) -> bool:
        """Remove an entity and all its components"""
        if entity_id not in self.entities:
            return False

        del self.entities[entity_id]

        # Clean up from update queues
        for channel_queues in self.update_queues.values():
            for component_queues in channel_queues.values():
                component_queues.discard(entity_id)

        self.emit_event("entity_destroyed", {"entity_id": entity_id})
        return True

    def add_component(self, entity_id: str, component: GameStateComponent) -> bool:
        """Add a component to an entity"""
        if entity_id not in self.entities:
            return False

        component_type = type(component).__name__
        self.entities[entity_id][component_type] = component

        # Add to appropriate update queue
        if hasattr(component, "update_channel"):
            self.update_queues[component.update_channel][component_type].add(entity_id)

        return True

    def get_component(
        self, entity_id: str, component_type: str
    ) -> Optional[GameStateComponent]:
        """Get a specific component from an entity"""
        if entity_id not in self.entities:
            return None
        return self.entities[entity_id].get(component_type)

    def get_position(self, entity_id: str) -> Optional[Tuple[float, float]]:
        """Get entity position"""
        pos_component = self.get_component(entity_id, "PositionComponent")
        if pos_component:
            return pos_component.x, pos_component.y
        return None

    def set_target_position(
        self, entity_id: str, x: float, y: float, speed: float = None
    ) -> bool:
        """Set target position for smooth movement"""
        pos_component = self.get_component(entity_id, "PositionComponent")
        if pos_component:
            return pos_component.set_target_position(x, y, speed)
        return False

    def teleport_entity(
        self, entity_id: str, x: float, y: float, rotation: float = None
    ) -> bool:
        """Instantly move entity to position"""
        pos_component = self.get_component(entity_id, "PositionComponent")
        if pos_component:
            pos_component.teleport_to(x, y, rotation)
            return True
        return False

    def damage_entity(
        self, entity_id: str, damage: float, attacker_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Apply damage to entity"""
        health_component = self.get_component(entity_id, "HealthComponent")
        if health_component:
            damage_result = health_component.take_damage(damage, attacker_id)

            if damage_result["died"]:
                self.emit_event(
                    "entity_died", {"entity_id": entity_id, "attacker_id": attacker_id}
                )

            return damage_result

        return {"damage_applied": 0.0, "died": False}

    def heal_entity(self, entity_id: str, amount: float) -> float:
        """Heal entity"""
        health_component = self.get_component(entity_id, "HealthComponent")
        if health_component:
            return health_component.heal(amount)
        return 0.0

    def get_entity_state(self, entity_id: str) -> Dict[str, Any]:
        """Get complete entity state for network transmission"""
        if entity_id not in self.entities:
            return {}

        state = {"entity_id": entity_id}
        for component_type, component in self.entities[entity_id].items():
            state[component_type.lower().replace("component", "")] = component.to_dict()

        return state

    def get_entities_by_channel(
        self, channel: UpdateChannel
    ) -> Dict[str, Dict[str, Any]]:
        """Get all entities that have dirty components for this update channel"""
        entities_to_update = {}

        for component_type, entity_set in self.update_queues[channel].items():
            for (
                entity_id
            ) in entity_set.copy():  # Copy to avoid modification during iteration
                component = self.get_component(entity_id, component_type)
                if component and component.dirty:
                    if entity_id not in entities_to_update:
                        entities_to_update[entity_id] = {"entity_id": entity_id}

                    # Add this component's data
                    component_key = component_type.lower().replace("component", "")
                    entities_to_update[entity_id][component_key] = component.to_dict()

                    # Mark as clean after adding to update
                    component.dirty = False

        return entities_to_update

    async def tick_update(self, dt: float) -> None:
        """Update all game state for one server tick"""
        async with self.state_lock:
            self.tick_number += 1
            current_time = time.time()

            # Update all position components
            for entity_id, components in self.entities.items():
                pos_component = components.get("PositionComponent")
                if pos_component:
                    pos_component.update_position(dt)

    def subscribe_to_event(self, event_name: str, callback: Callable):
        """Subscribe to game state events"""
        self.event_subscribers[event_name].append(callback)

    def emit_event(self, event_name: str, data: Dict[str, Any]):
        """Emit a game state event"""
        for callback in self.event_subscribers[event_name]:
            try:
                callback(event_name, data)
            except Exception as e:
                logger.error(f"Error in event callback for {event_name}: {e}")


class ServerTickScheduler:
    """High-frequency server tick scheduler with lag compensation"""

    def __init__(self, target_fps: float = 60.0):
        self.target_fps = target_fps
        self.target_dt = 1.0 / target_fps
        self.tick_number = 0
        self.last_tick_time = time.time()
        self.running = False
        self.tick_subscribers: List[Callable[[ServerTick], None]] = []
        self.performance_stats = deque(maxlen=1000)  # Last 1000 ticks

    def subscribe_to_ticks(self, callback: Callable[[ServerTick], None]):
        """Subscribe to server ticks"""
        self.tick_subscribers.append(callback)

    async def start(self):
        """Start the server tick loop"""
        self.running = True
        self.last_tick_time = time.time()

        logger.info(f"Starting server tick scheduler at {self.target_fps} FPS")

        while self.running:
            tick_start = time.time()

            # Calculate delta time
            dt = tick_start - self.last_tick_time
            self.last_tick_time = tick_start

            # Create tick info
            tick = ServerTick(
                tick_number=self.tick_number,
                timestamp=tick_start,
                delta_time=dt,
                tick_rate=self.target_fps,
            )

            # Process all tick subscribers
            for subscriber in self.tick_subscribers:
                try:
                    await subscriber(tick)
                except Exception as e:
                    logger.error(f"Error in tick subscriber: {e}")

            # Performance tracking
            tick_duration = time.time() - tick_start
            self.performance_stats.append(tick_duration)

            # Sleep to maintain target FPS
            sleep_time = max(0, self.target_dt - tick_duration)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

            self.tick_number += 1

            # Log performance warnings
            if tick_duration > self.target_dt * 1.5:
                logger.warning(
                    f"Slow server tick: {tick_duration*1000:.2f}ms (target: {self.target_dt*1000:.2f}ms)"
                )

    def stop(self):
        """Stop the server tick scheduler"""
        self.running = False

    def get_performance_stats(self) -> Dict[str, float]:
        """Get server performance statistics"""
        if not self.performance_stats:
            return {}

        durations = list(self.performance_stats)
        return {
            "avg_tick_duration_ms": (sum(durations) / len(durations)) * 1000,
            "max_tick_duration_ms": max(durations) * 1000,
            "min_tick_duration_ms": min(durations) * 1000,
            "target_tick_duration_ms": self.target_dt * 1000,
            "actual_fps": len(durations) / sum(durations) if sum(durations) > 0 else 0,
        }
