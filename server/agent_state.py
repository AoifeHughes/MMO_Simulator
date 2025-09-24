"""
Server-side agent state registry for authoritative game state management.

This module provides persistent agent data storage, validation, and statistics
tracking. It serves as the foundation for future features like inventory,
money, and anti-cheat systems.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from shared.inventory import Inventory
from shared.items import create_item


@dataclass
class ServerAgentState:
    """Authoritative server-side agent state"""

    agent_id: str
    agent_type: str

    # Core state
    health: float = 100.0
    max_health: float = 100.0
    position: Tuple[float, float] = (50.0, 50.0)
    rotation: float = 0.0
    is_alive: bool = True

    # Timing
    spawn_time: float = field(default_factory=time.time)
    last_damage_time: float = 0.0
    last_attack_time: float = 0.0
    respawn_time: float = 0.0
    last_update_time: float = field(default_factory=time.time)

    # Statistics (foundation for future features)
    stats: Dict[str, float] = field(
        default_factory=lambda: {
            "damage_dealt": 0.0,
            "damage_taken": 0.0,
            "kills": 0.0,
            "deaths": 0.0,
            "exploration_percent": 0.0,
            "distance_traveled": 0.0,
        }
    )

    # Inventory system
    inventory: Inventory = field(default_factory=lambda: Inventory(max_weight=100.0))
    experience: float = 0.0

    # Special modes for different behaviors
    exploration_mode: str = "frontier"

    def update_position(self, x: float, y: float, rotation: float = None):
        """Update agent position and track distance traveled"""
        old_x, old_y = self.position
        distance = ((x - old_x) ** 2 + (y - old_y) ** 2) ** 0.5
        self.stats["distance_traveled"] += distance

        self.position = (x, y)
        if rotation is not None:
            self.rotation = rotation
        self.last_update_time = time.time()

    def take_damage(self, damage: float, attacker_id: Optional[str] = None) -> bool:
        """Apply damage and return True if agent died"""
        if not self.is_alive:
            return False

        old_health = self.health
        self.health = max(0.0, self.health - damage)
        self.stats["damage_taken"] += damage
        self.last_damage_time = time.time()

        if self.health <= 0 and old_health > 0:
            self.is_alive = False
            self.stats["deaths"] += 1
            return True

        return False

    def heal(self, amount: float):
        """Restore health up to maximum"""
        self.health = min(self.max_health, self.health + amount)

    def respawn(self, x: float, y: float, respawn_delay: float = 5.0):
        """Respawn agent at given position"""
        self.health = self.max_health
        self.is_alive = True
        self.position = (x, y)
        self.respawn_time = time.time() + respawn_delay
        self.last_update_time = time.time()

    def add_kill(self):
        """Record a kill for statistics"""
        self.stats["kills"] += 1

    def add_damage_dealt(self, damage: float):
        """Record damage dealt for statistics"""
        self.stats["damage_dealt"] += damage

    def update_exploration(self, percent: float):
        """Update exploration percentage"""
        self.stats["exploration_percent"] = max(
            self.stats["exploration_percent"], percent
        )

    def add_starting_items(self):
        """Add default starting items based on agent type"""
        if self.agent_type == "player":
            # Players start with a sword
            sword = create_item("iron_sword")
            if sword:
                self.inventory.add_item(sword, 1)
                self.inventory.equip_item(sword.item_id)

        elif self.agent_type == "explorer":
            # Explorers start with fishing rod
            fishing_rod = create_item("fishing_rod")
            if fishing_rod:
                self.inventory.add_item(fishing_rod, 1)

        # All agents start with some gold
        self.inventory.add_gold(100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "health": self.health,
            "max_health": self.max_health,
            "x": self.position[0],
            "y": self.position[1],
            "rotation": self.rotation,
            "is_alive": self.is_alive,
            "stats": self.stats.copy(),
            "inventory": self.inventory.to_dict(),
            "last_update_time": self.last_update_time,
        }


class AgentRegistry:
    """Server-side registry for managing all agent states"""

    def __init__(self):
        self.agents: Dict[str, ServerAgentState] = {}
        self.controlled_agents: Dict[str, str] = {}  # agent_id -> client_id

    def register_agent(
        self, agent_id: str, agent_type: str, x: float = 50.0, y: float = 50.0
    ) -> ServerAgentState:
        """Register a new agent in the registry"""
        if agent_id in self.agents:
            return self.agents[agent_id]

        agent_state = ServerAgentState(
            agent_id=agent_id, agent_type=agent_type, position=(x, y)
        )

        # Add starting items
        agent_state.add_starting_items()

        self.agents[agent_id] = agent_state
        return agent_state

    def get_agent(self, agent_id: str) -> Optional[ServerAgentState]:
        """Get agent state by ID"""
        return self.agents.get(agent_id)

    def remove_agent(self, agent_id: str) -> bool:
        """Remove agent from registry"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            if agent_id in self.controlled_agents:
                del self.controlled_agents[agent_id]
            return True
        return False

    def assign_agent_to_client(self, agent_id: str, client_id: str):
        """Assign agent control to a client"""
        if agent_id in self.agents:
            self.controlled_agents[agent_id] = client_id

    def unassign_agent(self, agent_id: str):
        """Remove client control from agent"""
        if agent_id in self.controlled_agents:
            del self.controlled_agents[agent_id]

    def get_uncontrolled_agents(self, agent_type: Optional[str] = None) -> List[str]:
        """Get list of uncontrolled agent IDs, optionally filtered by type"""
        uncontrolled = []

        for agent_id, agent_state in self.agents.items():
            if agent_id not in self.controlled_agents:
                if agent_type is None or agent_state.agent_type == agent_type:
                    uncontrolled.append(agent_id)

        return uncontrolled

    def get_client_agents(self, client_id: str) -> List[str]:
        """Get all agent IDs controlled by a client"""
        return [
            agent_id
            for agent_id, cid in self.controlled_agents.items()
            if cid == client_id
        ]

    def validate_agent_action(
        self, agent_id: str, action_type: str, action_data: Dict
    ) -> bool:
        """Validate if an agent can perform an action (anti-cheat foundation)"""
        agent = self.get_agent(agent_id)
        if not agent or not agent.is_alive:
            return False

        if action_type == "damage":
            # Validate attack range, cooldowns, etc.
            target_id = action_data.get("target_id")
            if not target_id:
                return False

            target = self.get_agent(target_id)
            if not target or not target.is_alive:
                return False

            # Check distance (simple validation)
            dx = target.position[0] - agent.position[0]
            dy = target.position[1] - agent.position[1]
            distance = (dx**2 + dy**2) ** 0.5

            max_attack_range = 5.0  # Maximum allowed attack range
            if distance > max_attack_range:
                return False

        return True

    def update_from_world_agents(self, world_agents: List[Any]):
        """Sync registry with world agent data"""
        for world_agent in world_agents:
            agent = self.get_agent(world_agent.id)
            if agent:
                agent.update_position(
                    world_agent.x, world_agent.y, world_agent.rotation
                )
                agent.health = world_agent.health
                agent.is_alive = world_agent.is_alive

    def get_statistics_summary(self) -> Dict[str, Any]:
        """Get aggregated statistics for all agents"""
        total_agents = len(self.agents)
        alive_agents = sum(1 for agent in self.agents.values() if agent.is_alive)
        controlled_agents = len(self.controlled_agents)

        total_kills = sum(agent.stats["kills"] for agent in self.agents.values())
        total_damage = sum(
            agent.stats["damage_dealt"] for agent in self.agents.values()
        )

        return {
            "total_agents": total_agents,
            "alive_agents": alive_agents,
            "controlled_agents": controlled_agents,
            "uncontrolled_agents": total_agents - controlled_agents,
            "total_kills": total_kills,
            "total_damage_dealt": total_damage,
        }
