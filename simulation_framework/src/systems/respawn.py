from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ..core.world import World
    from ..entities.base import Entity


class RespawnType(Enum):
    AGENT = "agent"
    NPC = "npc"
    RESOURCE_NODE = "resource_node"
    STRUCTURE = "structure"


@dataclass
class RespawnEntry:
    """Represents an entity scheduled for respawn"""

    entity_id: int
    entity_type: RespawnType
    respawn_tick: int
    original_position: Tuple[int, int]
    respawn_data: Dict  # Store entity creation data
    death_tick: int
    respawn_attempts: int = 0
    max_respawn_attempts: int = 3


class RespawnManager:
    """Manages entity respawning and resource regeneration"""

    def __init__(self, world_width: int, world_height: int):
        self.world_width = world_width
        self.world_height = world_height

        # Respawn queues
        self.respawn_queue: List[RespawnEntry] = []
        self.respawn_history: Dict[int, RespawnEntry] = {}

        # Respawn settings
        self.agent_respawn_delay = 200  # Ticks to respawn agents
        self.npc_respawn_delay = 150  # Ticks to respawn NPCs
        self.resource_respawn_delay = 100  # Ticks to respawn resources

        # Population control
        self.max_agents = 50
        self.max_npcs = 100
        self.target_resource_density = 0.3  # 30% of tiles should have resources

        # Respawn zones
        self.safe_zones: List[Tuple[int, int, int]] = (
            []
        )  # (x, y, radius) for safe respawn areas
        self.restricted_zones: List[Tuple[int, int, int]] = (
            []
        )  # Areas where entities shouldn't respawn

        # Statistics
        self.total_respawns = 0
        self.respawn_by_type: Dict[RespawnType, int] = {
            RespawnType.AGENT: 0,
            RespawnType.NPC: 0,
            RespawnType.RESOURCE_NODE: 0,
            RespawnType.STRUCTURE: 0,
        }

    def add_safe_zone(self, center_x: int, center_y: int, radius: int) -> None:
        """Add a safe zone for respawning"""
        self.safe_zones.append((center_x, center_y, radius))

    def add_restricted_zone(self, center_x: int, center_y: int, radius: int) -> None:
        """Add a restricted zone where entities shouldn't respawn"""
        self.restricted_zones.append((center_x, center_y, radius))

    def schedule_respawn(
        self,
        entity: Entity,
        entity_type: RespawnType,
        world: World,
        custom_delay: Optional[int] = None,
    ) -> bool:
        """Schedule an entity for respawn"""

        if not self._should_respawn(entity, entity_type, world):
            return False

        # Calculate respawn delay
        delay = custom_delay or self._get_respawn_delay(entity_type, entity)

        # Create respawn data
        respawn_data = self._create_respawn_data(entity, entity_type)

        entry = RespawnEntry(
            entity_id=entity.id,
            entity_type=entity_type,
            respawn_tick=world.current_tick + delay,
            original_position=entity.position,
            respawn_data=respawn_data,
            death_tick=world.current_tick,
        )

        self.respawn_queue.append(entry)
        return True

    def process_respawns(self, world: World) -> List[Entity]:
        """Process all pending respawns and return newly spawned entities"""

        current_tick = world.current_tick
        respawned_entities = []

        # Process entries ready for respawn
        ready_entries = [
            entry for entry in self.respawn_queue if entry.respawn_tick <= current_tick
        ]

        for entry in ready_entries:
            respawned_entity = self._attempt_respawn(entry, world)

            if respawned_entity:
                respawned_entities.append(respawned_entity)
                self.respawn_queue.remove(entry)
                self.respawn_history[entry.entity_id] = entry
                self.total_respawns += 1
                self.respawn_by_type[entry.entity_type] += 1
            else:
                # Failed to respawn, try again later
                entry.respawn_attempts += 1
                if entry.respawn_attempts >= entry.max_respawn_attempts:
                    self.respawn_queue.remove(entry)
                else:
                    # Delay and try again
                    entry.respawn_tick = current_tick + 50

        return respawned_entities

    def _should_respawn(
        self, entity: Entity, entity_type: RespawnType, world: World
    ) -> bool:
        """Determine if an entity should be scheduled for respawn"""

        # Check population limits
        if entity_type == RespawnType.AGENT:
            current_agents = len(
                [
                    e
                    for e in world.entities.values()
                    if e.__class__.__name__ == "Agent" and e.stats.is_alive()
                ]
            )
            if current_agents >= self.max_agents:
                return False

        elif entity_type == RespawnType.NPC:
            current_npcs = len(
                [
                    e
                    for e in world.entities.values()
                    if hasattr(e, "npc_type") and e.stats.is_alive()
                ]
            )
            if current_npcs >= self.max_npcs:
                return False

        # Check if entity is already scheduled for respawn
        for entry in self.respawn_queue:
            if entry.entity_id == entity.id:
                return False

        # Always respawn important entities
        if entity_type in [RespawnType.AGENT, RespawnType.RESOURCE_NODE]:
            return True

        # Personality-based respawn decisions for agents
        if entity_type == RespawnType.AGENT and hasattr(entity, "personality"):
            # More determined personalities are more likely to respawn
            determination = (
                entity.personality.bravery + entity.personality.industriousness
            )
            respawn_chance = 0.5 + (determination * 0.3)
            return random.random() < respawn_chance

        return True

    def _get_respawn_delay(self, entity_type: RespawnType, entity: Entity) -> int:
        """Calculate respawn delay for an entity"""

        base_delay = {
            RespawnType.AGENT: self.agent_respawn_delay,
            RespawnType.NPC: self.npc_respawn_delay,
            RespawnType.RESOURCE_NODE: self.resource_respawn_delay,
            RespawnType.STRUCTURE: 500,  # Structures take longer to rebuild
        }.get(entity_type, 100)

        # Add some randomness
        variation = int(base_delay * 0.3)
        delay = base_delay + random.randint(-variation, variation)

        # Personality modifiers for agents
        if entity_type == RespawnType.AGENT and hasattr(entity, "personality"):
            # Impatient agents respawn faster
            if entity.personality.patience < 0.3:
                delay = int(delay * 0.8)
            # Patient agents take longer
            elif entity.personality.patience > 0.7:
                delay = int(delay * 1.2)

        return max(50, delay)  # Minimum respawn time

    def _create_respawn_data(self, entity: Entity, entity_type: RespawnType) -> Dict:
        """Create data needed to respawn the entity"""

        base_data = {
            "name": entity.name,
            "stats": {
                "max_health": entity.stats.max_health,
                "max_stamina": entity.stats.max_stamina,
                "attack_power": entity.stats.attack_power,
                "defense": entity.stats.defense,
            },
        }

        if entity_type == RespawnType.AGENT:
            if hasattr(entity, "personality"):
                base_data["personality"] = entity.personality.to_dict()
            if hasattr(entity, "character_class"):
                base_data["character_class"] = entity.character_class.name
            if hasattr(entity, "skills"):
                base_data["skills"] = entity.skills.copy()

        elif entity_type == RespawnType.NPC:
            if hasattr(entity, "npc_type"):
                base_data["npc_type"] = entity.npc_type
            if hasattr(entity, "faction"):
                base_data["faction"] = entity.faction
            if hasattr(entity, "ai_state"):
                base_data["ai_state"] = entity.ai_state

        elif entity_type == RespawnType.RESOURCE_NODE:
            if hasattr(entity, "resource_type"):
                base_data["resource_type"] = entity.resource_type
            if hasattr(entity, "resource_amount"):
                base_data["resource_amount"] = entity.resource_amount

        return base_data

    def _attempt_respawn(self, entry: RespawnEntry, world: World) -> Optional[Entity]:
        """Attempt to respawn an entity"""

        # Find a suitable respawn position
        respawn_position = self._find_respawn_position(entry, world)
        if not respawn_position:
            return None

        # Create the respawned entity
        respawned_entity = self._create_respawned_entity(entry, respawn_position, world)
        if not respawned_entity:
            return None

        # Add to world
        world.add_entity(respawned_entity)

        return respawned_entity

    def _find_respawn_position(
        self, entry: RespawnEntry, world: World
    ) -> Optional[Tuple[int, int]]:
        """Find a suitable position to respawn an entity"""

        candidates = []

        # Try original position first if it's safe
        if self._is_safe_respawn_position(entry.original_position, world):
            candidates.append(entry.original_position)

        # Try safe zones
        for safe_x, safe_y, radius in self.safe_zones:
            for _ in range(10):  # Try 10 random positions in each safe zone
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(0, radius)
                x = int(safe_x + distance * math.cos(angle))
                y = int(safe_y + distance * math.sin(angle))

                if (
                    0 <= x < self.world_width
                    and 0 <= y < self.world_height
                    and self._is_safe_respawn_position((x, y), world)
                ):
                    candidates.append((x, y))

        # If no safe zones work, try near original position
        if not candidates:
            orig_x, orig_y = entry.original_position
            for radius in [3, 5, 10, 15]:
                for _ in range(20):  # Try random positions in expanding radius
                    angle = random.uniform(0, 2 * math.pi)
                    distance = random.uniform(0, radius)
                    x = int(orig_x + distance * math.cos(angle))
                    y = int(orig_y + distance * math.sin(angle))

                    if (
                        0 <= x < self.world_width
                        and 0 <= y < self.world_height
                        and self._is_safe_respawn_position((x, y), world)
                    ):
                        candidates.append((x, y))
                        break
                if candidates:
                    break

        # Return best candidate (closest to original position)
        if candidates:
            orig_x, orig_y = entry.original_position
            candidates.sort(
                key=lambda pos: math.sqrt(
                    (pos[0] - orig_x) ** 2 + (pos[1] - orig_y) ** 2
                )
            )
            return candidates[0]

        return None

    def _is_safe_respawn_position(
        self, position: Tuple[int, int], world: World
    ) -> bool:
        """Check if a position is safe for respawning"""

        x, y = position

        # Check bounds
        if not (0 <= x < self.world_width and 0 <= y < self.world_height):
            return False

        # Check if position is in restricted zone
        for restrict_x, restrict_y, radius in self.restricted_zones:
            distance = math.sqrt((x - restrict_x) ** 2 + (y - restrict_y) ** 2)
            if distance <= radius:
                return False

        # Check terrain
        tile = world.get_tile(x, y)
        if not tile or not tile.can_pass():
            return False

        # Check for existing entities at position
        entities_at_pos = world.get_entities_at(x, y)
        if entities_at_pos:
            return False

        # Check for nearby hostile entities
        for entity in world.entities.values():
            if not entity.stats.is_alive():
                continue

            if hasattr(entity, "npc_type") and entity.npc_type == "aggressive":
                distance = math.sqrt(
                    (x - entity.position[0]) ** 2 + (y - entity.position[1]) ** 2
                )
                if distance < 5:  # Too close to hostile entity
                    return False

        return True

    def _create_respawned_entity(
        self, entry: RespawnEntry, position: Tuple[int, int], world: World
    ) -> Optional[Entity]:
        """Create a respawned entity from respawn data"""

        try:
            if entry.entity_type == RespawnType.AGENT:
                return self._create_respawned_agent(entry, position)
            elif entry.entity_type == RespawnType.NPC:
                return self._create_respawned_npc(entry, position)
            elif entry.entity_type == RespawnType.RESOURCE_NODE:
                return self._create_respawned_resource(entry, position)
            elif entry.entity_type == RespawnType.STRUCTURE:
                return self._create_respawned_structure(entry, position)

        except Exception:
            # Log error in real implementation
            return None

        return None

    def _create_respawned_agent(
        self, entry: RespawnEntry, position: Tuple[int, int]
    ) -> Optional[Entity]:
        """Create a respawned agent"""
        from ..ai.character_class import get_character_class
        from ..ai.personality import Personality
        from ..entities.agent import Agent

        data = entry.respawn_data

        # Restore personality
        personality = None
        if "personality" in data:
            personality = Personality.from_dict(data["personality"])

        # Restore character class
        character_class = None
        if "character_class" in data:
            character_class = get_character_class(data["character_class"])

        agent = Agent(
            position=position,
            name=data["name"],
            personality=personality,
            character_class=character_class,
        )

        # Restore skills (with some penalty)
        if "skills" in data:
            for skill, level in data["skills"].items():
                # Lose some skill levels on death
                new_level = max(0, level - random.randint(0, 2))
                if new_level > 0:
                    agent.skills[skill] = new_level

        return agent

    def _create_respawned_npc(
        self, entry: RespawnEntry, position: Tuple[int, int]
    ) -> Optional[Entity]:
        """Create a respawned NPC"""
        from ..entities.npc import NPC

        data = entry.respawn_data

        npc = NPC(
            position=position,
            name=data["name"],
            npc_type=data.get("npc_type", "neutral"),
        )

        if "faction" in data:
            npc.faction = data["faction"]

        return npc

    def _create_respawned_resource(
        self, entry: RespawnEntry, position: Tuple[int, int]
    ) -> Optional[Entity]:
        """Create a respawned resource node"""
        # This would create resource nodes - simplified for now
        # In full implementation, would create resource entities or update tile resources
        return None

    def _create_respawned_structure(
        self, entry: RespawnEntry, position: Tuple[int, int]
    ) -> Optional[Entity]:
        """Create a respawned structure"""
        # This would create structures - simplified for now
        return None

    def maintain_population(self, world: World) -> None:
        """Maintain target population levels"""

        current_agents = len(
            [
                e
                for e in world.entities.values()
                if e.__class__.__name__ == "Agent" and e.stats.is_alive()
            ]
        )

        current_npcs = len(
            [
                e
                for e in world.entities.values()
                if hasattr(e, "npc_type") and e.stats.is_alive()
            ]
        )

        # Spawn new agents if below target
        target_agents = max(20, self.max_agents // 2)
        if current_agents < target_agents:
            self._spawn_new_agents(world, target_agents - current_agents)

        # Spawn new NPCs if below target
        target_npcs = max(30, self.max_npcs // 2)
        if current_npcs < target_npcs:
            self._spawn_new_npcs(world, target_npcs - current_npcs)

    def _spawn_new_agents(self, world: World, count: int) -> None:
        """Spawn new agents to maintain population"""
        from ..entities.agent import create_random_agent

        for _ in range(count):
            # Find spawn position
            position = self._find_spawn_position(world)
            if position:
                agent = create_random_agent(position)
                world.add_entity(agent)

    def _spawn_new_npcs(self, world: World, count: int) -> None:
        """Spawn new NPCs to maintain population"""
        # This would create new NPCs - simplified for now

    def _find_spawn_position(self, world: World) -> Optional[Tuple[int, int]]:
        """Find a position to spawn a new entity"""

        # Try safe zones first
        for safe_x, safe_y, radius in self.safe_zones:
            for _ in range(10):
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(0, radius)
                x = int(safe_x + distance * math.cos(angle))
                y = int(safe_y + distance * math.sin(angle))

                if (
                    0 <= x < self.world_width
                    and 0 <= y < self.world_height
                    and self._is_safe_respawn_position((x, y), world)
                ):
                    return (x, y)

        # Random position as fallback
        for _ in range(100):
            x = random.randint(0, self.world_width - 1)
            y = random.randint(0, self.world_height - 1)

            if self._is_safe_respawn_position((x, y), world):
                return (x, y)

        return None

    def get_respawn_summary(self) -> Dict:
        """Get respawn system summary for debugging"""

        return {
            "pending_respawns": len(self.respawn_queue),
            "total_respawns": self.total_respawns,
            "respawns_by_type": self.respawn_by_type.copy(),
            "safe_zones": len(self.safe_zones),
            "restricted_zones": len(self.restricted_zones),
            "next_respawn_tick": min(
                (entry.respawn_tick for entry in self.respawn_queue), default=None
            ),
        }

    def cancel_respawn(self, entity_id: int) -> bool:
        """Cancel a pending respawn"""

        for entry in self.respawn_queue:
            if entry.entity_id == entity_id:
                self.respawn_queue.remove(entry)
                return True

        return False

    def get_entity_respawn_info(self, entity_id: int) -> Optional[Dict]:
        """Get respawn information for a specific entity"""

        # Check pending respawns
        for entry in self.respawn_queue:
            if entry.entity_id == entity_id:
                return {
                    "status": "pending",
                    "respawn_tick": entry.respawn_tick,
                    "attempts": entry.respawn_attempts,
                    "original_position": entry.original_position,
                }

        # Check history
        if entity_id in self.respawn_history:
            entry = self.respawn_history[entity_id]
            return {
                "status": "completed",
                "death_tick": entry.death_tick,
                "respawn_tick": entry.respawn_tick,
                "attempts": entry.respawn_attempts,
            }

        return None
