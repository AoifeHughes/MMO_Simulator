"""
Simplified Server-Side AI System

This replaces the complex client-side behavior trees with simple, server-authoritative AI.
All agent decisions are made on the server, eliminating client-server sync issues.

Core principles:
- Server is the single source of truth for all agent behavior
- Simple state machines replace complex behavior trees
- Direct action execution without prediction/rollback complexity
- Clear, debuggable logic flow
"""

import logging
import random
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Simple agent states for server-side AI"""
    IDLE = "idle"
    EXPLORING = "exploring"
    MOVING_TO_TARGET = "moving_to_target"
    FISHING = "fishing"
    HARVESTING_WOOD = "harvesting_wood"
    SEEKING_RESOURCE = "seeking_resource"
    ATTACKING = "attacking"
    FLEEING = "fleeing"


class SimplifiedAI:
    """Server-side AI that replaces client-side behavior trees"""

    def __init__(self, world):
        self.world = world
        self.agent_states: Dict[str, AgentState] = {}
        self.agent_targets: Dict[str, Tuple[float, float]] = {}
        self.agent_timers: Dict[str, float] = {}
        self.last_update = time.time()

        # Simple AI parameters
        self.exploration_chance = 0.3
        self.resource_seeking_range = 15.0
        self.flee_health_threshold = 20.0
        self.attack_range = 3.0

    def register_agent(self, agent_id: str, agent_type: str):
        """Register an agent for AI control"""
        self.agent_states[agent_id] = AgentState.IDLE
        self.agent_timers[agent_id] = time.time()
        logger.info(f"SimplifiedAI: Registered {agent_type} agent {agent_id[:8]}")

    def unregister_agent(self, agent_id: str):
        """Remove agent from AI control"""
        self.agent_states.pop(agent_id, None)
        self.agent_targets.pop(agent_id, None)
        self.agent_timers.pop(agent_id, None)

    def update_all_agents(self, delta_time: float):
        """Update AI for all registered agents"""
        current_time = time.time()

        for agent_id in list(self.agent_states.keys()):
            agent = self.world.get_agent(agent_id)
            if not agent or not agent.is_alive:
                continue

            # Update this agent's AI
            self._update_agent_ai(agent, current_time, delta_time)

        self.last_update = current_time

    def _update_agent_ai(self, agent, current_time: float, delta_time: float):
        """Update AI for a single agent using simple state machine"""
        agent_id = agent.id
        current_state = self.agent_states.get(agent_id, AgentState.IDLE)

        # Check for emergency states first
        if agent.health < self.flee_health_threshold:
            self._enter_flee_state(agent)
            return

        # Look for enemies to attack
        if agent.agent_type in ["enemy", "player"]:
            enemy = self._find_nearest_enemy(agent)
            if enemy and self._get_distance(agent, enemy) < self.attack_range:
                self._enter_attack_state(agent, enemy)
                return

        # State machine logic
        if current_state == AgentState.IDLE:
            self._handle_idle_state(agent, current_time)
        elif current_state == AgentState.EXPLORING:
            self._handle_exploring_state(agent, current_time)
        elif current_state == AgentState.MOVING_TO_TARGET:
            self._handle_moving_state(agent, current_time)
        elif current_state == AgentState.SEEKING_RESOURCE:
            self._handle_resource_seeking_state(agent, current_time)
        elif current_state == AgentState.FISHING:
            self._handle_fishing_state(agent, current_time)
        elif current_state == AgentState.HARVESTING_WOOD:
            self._handle_wood_harvesting_state(agent, current_time)
        elif current_state == AgentState.ATTACKING:
            self._handle_attack_state(agent, current_time)
        elif current_state == AgentState.FLEEING:
            self._handle_flee_state(agent, current_time)

    def _handle_idle_state(self, agent, current_time: float):
        """Handle agent in idle state - decide what to do next"""
        agent_id = agent.id

        # Check timer to avoid constant state changes
        if current_time - self.agent_timers.get(agent_id, 0) < 2.0:
            return

        # Decide next action based on agent type
        if agent.agent_type == "explorer":
            # Explorers seek resources or explore
            if random.random() < 0.7:
                self._enter_resource_seeking_state(agent)
            else:
                self._enter_exploration_state(agent)
        elif agent.agent_type == "fishing_explorer":
            # Fishing explorers primarily fish
            if random.random() < 0.8:
                self._seek_water_for_fishing(agent)
            else:
                self._enter_exploration_state(agent)
        elif agent.agent_type in ["npc", "enemy"]:
            # NPCs and enemies explore or seek resources
            if random.random() < self.exploration_chance:
                self._enter_exploration_state(agent)
            else:
                self._enter_resource_seeking_state(agent)
        else:
            # Default to exploration
            self._enter_exploration_state(agent)

        self.agent_timers[agent_id] = current_time

    def _handle_exploring_state(self, agent, current_time: float):
        """Handle agent exploring - move towards unexplored areas"""
        agent_id = agent.id

        # Check if we have a target
        if agent_id not in self.agent_targets:
            target = self._find_exploration_target(agent)
            if target:
                self.agent_targets[agent_id] = target
                self._move_agent_to_target(agent, target)
            else:
                # No exploration target found, go idle
                self._enter_idle_state(agent)
            return

        # Check if we've reached our target
        target = self.agent_targets[agent_id]
        if self._get_distance_to_point(agent, target) < 2.0:
            # Reached target, explore a bit then find new target
            self.agent_targets.pop(agent_id, None)
            if random.random() < 0.3:
                self._enter_idle_state(agent)
            else:
                # Continue exploring
                pass
        else:
            # Continue moving to target
            self._move_agent_to_target(agent, target)

    def _handle_moving_state(self, agent, current_time: float):
        """Handle agent moving to a target"""
        agent_id = agent.id

        if agent_id not in self.agent_targets:
            self._enter_idle_state(agent)
            return

        target = self.agent_targets[agent_id]
        distance = self._get_distance_to_point(agent, target)

        if distance < 1.0:
            # Reached target
            self.agent_targets.pop(agent_id, None)
            self._enter_idle_state(agent)
        else:
            # Continue moving
            self._move_agent_to_target(agent, target)

    def _handle_resource_seeking_state(self, agent, current_time: float):
        """Handle agent seeking resources"""
        agent_id = agent.id

        # Look for nearby resources
        resource_location = self._find_nearest_resource(agent)
        if resource_location:
            resource_type, location = resource_location
            if resource_type == "water":
                self._start_fishing(agent, location)
            elif resource_type == "wood":
                self._start_wood_harvesting(agent, location)
            else:
                # Move towards resource
                self.agent_targets[agent_id] = location
                self._move_agent_to_target(agent, location)
                self.agent_states[agent_id] = AgentState.MOVING_TO_TARGET
        else:
            # No resources found, start exploring
            self._enter_exploration_state(agent)

    def _handle_fishing_state(self, agent, current_time: float):
        """Handle agent fishing"""
        agent_id = agent.id

        # Check if fishing action is complete (simplified - just use timer)
        fishing_duration = current_time - self.agent_timers.get(agent_id, current_time)
        if fishing_duration > 3.0:  # 3 second fishing
            # Fishing complete, attempt to catch fish
            if random.random() < 0.6:  # 60% success rate
                self._give_agent_fish(agent)
                logger.info(f"🎣 Agent {agent_id[:8]} caught a fish!")
            else:
                logger.info(f"🎣 Agent {agent_id[:8]} fishing unsuccessful")

            # Return to idle
            self._enter_idle_state(agent)
        # Continue fishing (agent stays in place)

    def _handle_wood_harvesting_state(self, agent, current_time: float):
        """Handle agent harvesting wood"""
        agent_id = agent.id

        # Check if harvesting is complete
        harvest_duration = current_time - self.agent_timers.get(agent_id, current_time)
        if harvest_duration > 2.5:  # 2.5 second harvesting
            # Harvesting complete
            self._give_agent_wood(agent)
            logger.info(f"🌲 Agent {agent_id[:8]} harvested wood!")

            # Return to idle
            self._enter_idle_state(agent)
        # Continue harvesting (agent stays in place)

    def _handle_attack_state(self, agent, current_time: float):
        """Handle agent attacking"""
        # Simplified attack - just damage the target
        target_id = self.agent_targets.get(agent.id)
        if target_id:
            target = self.world.get_agent(target_id)
            if target and target.is_alive:
                # Deal damage
                target.health = max(0, target.health - 25)
                if target.health <= 0:
                    target.is_alive = False
                    logger.info(f"Agent {agent.id[:8]} killed {target_id[:8]}")

                # Short attack cooldown
                self.agent_timers[agent.id] = current_time + 1.0

        # Return to idle after attack
        self._enter_idle_state(agent)

    def _handle_flee_state(self, agent, current_time: float):
        """Handle agent fleeing from danger"""
        # Find safe location and move there
        safe_location = self._find_safe_location(agent)
        if safe_location:
            self._move_agent_to_target(agent, safe_location)

        # Check if health recovered enough to stop fleeing
        if agent.health > self.flee_health_threshold * 1.5:
            self._enter_idle_state(agent)

    # State transition methods
    def _enter_idle_state(self, agent):
        """Transition agent to idle state"""
        agent.velocity_x = 0
        agent.velocity_y = 0
        self.agent_states[agent.id] = AgentState.IDLE
        self.agent_targets.pop(agent.id, None)

    def _enter_exploration_state(self, agent):
        """Transition agent to exploration state"""
        self.agent_states[agent.id] = AgentState.EXPLORING
        self.agent_timers[agent.id] = time.time()

    def _enter_resource_seeking_state(self, agent):
        """Transition agent to resource seeking state"""
        self.agent_states[agent.id] = AgentState.SEEKING_RESOURCE
        self.agent_timers[agent.id] = time.time()

    def _enter_attack_state(self, agent, target):
        """Transition agent to attack state"""
        self.agent_states[agent.id] = AgentState.ATTACKING
        self.agent_targets[agent.id] = target.id
        self.agent_timers[agent.id] = time.time()

    def _enter_flee_state(self, agent):
        """Transition agent to flee state"""
        self.agent_states[agent.id] = AgentState.FLEEING
        self.agent_timers[agent.id] = time.time()

    # Action methods
    def _start_fishing(self, agent, water_location: Tuple[float, float]):
        """Start fishing at water location"""
        # Move to water location
        distance = self._get_distance_to_point(agent, water_location)
        if distance < 2.0:
            # Close enough to start fishing
            self.agent_states[agent.id] = AgentState.FISHING
            self.agent_timers[agent.id] = time.time()
            agent.velocity_x = 0
            agent.velocity_y = 0
        else:
            # Move closer to water
            self.agent_targets[agent.id] = water_location
            self._move_agent_to_target(agent, water_location)
            self.agent_states[agent.id] = AgentState.MOVING_TO_TARGET

    def _start_wood_harvesting(self, agent, wood_location: Tuple[float, float]):
        """Start harvesting wood at location"""
        distance = self._get_distance_to_point(agent, wood_location)
        if distance < 2.0:
            # Close enough to start harvesting
            self.agent_states[agent.id] = AgentState.HARVESTING_WOOD
            self.agent_timers[agent.id] = time.time()
            agent.velocity_x = 0
            agent.velocity_y = 0
        else:
            # Move closer to wood
            self.agent_targets[agent.id] = wood_location
            self._move_agent_to_target(agent, wood_location)
            self.agent_states[agent.id] = AgentState.MOVING_TO_TARGET

    def _seek_water_for_fishing(self, agent):
        """Look for water tiles for fishing"""
        water_location = self._find_nearest_water(agent)
        if water_location:
            self._start_fishing(agent, water_location)
        else:
            self._enter_exploration_state(agent)

    # Utility methods
    def _find_exploration_target(self, agent) -> Optional[Tuple[float, float]]:
        """Find a good location for exploration"""
        # Simple: pick a random location within bounds
        world_bounds = self.world.world_map.get_bounds()
        max_attempts = 10

        for _ in range(max_attempts):
            target_x = random.uniform(5, world_bounds[0] - 5)
            target_y = random.uniform(5, world_bounds[1] - 5)

            # Check if location is walkable
            if self.world.world_map.is_walkable(int(target_x), int(target_y)):
                return (target_x, target_y)

        return None

    def _find_nearest_resource(self, agent) -> Optional[Tuple[str, Tuple[float, float]]]:
        """Find nearest resource (water or wood) within range"""
        agent_x, agent_y = agent.x, agent.y
        search_radius = int(self.resource_seeking_range)

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(agent_x) + dx
                check_y = int(agent_y) + dy

                # Check bounds
                if (0 <= check_x < self.world.world_map.width and
                    0 <= check_y < self.world.world_map.height):

                    tile_type = self.world.world_map.get_tile(check_x, check_y)

                    # Check distance
                    distance = ((check_x - agent_x) ** 2 + (check_y - agent_y) ** 2) ** 0.5
                    if distance <= self.resource_seeking_range:
                        if tile_type.name == "WATER":
                            return ("water", (check_x + 0.5, check_y + 0.5))
                        elif tile_type.name == "WOOD":
                            return ("wood", (check_x + 0.5, check_y + 0.5))

        return None

    def _find_nearest_water(self, agent) -> Optional[Tuple[float, float]]:
        """Find nearest water tile for fishing"""
        resource = self._find_nearest_resource(agent)
        if resource and resource[0] == "water":
            return resource[1]
        return None

    def _find_nearest_enemy(self, agent) -> Optional[Any]:
        """Find nearest enemy agent"""
        enemies = []
        for other_agent in self.world.get_all_agents():
            if (other_agent.id != agent.id and
                other_agent.is_alive and
                other_agent.agent_type != agent.agent_type):
                enemies.append(other_agent)

        if not enemies:
            return None

        # Find closest enemy
        closest_enemy = None
        closest_distance = float('inf')

        for enemy in enemies:
            distance = self._get_distance(agent, enemy)
            if distance < closest_distance:
                closest_distance = distance
                closest_enemy = enemy

        return closest_enemy

    def _find_safe_location(self, agent) -> Optional[Tuple[float, float]]:
        """Find a safe location to flee to"""
        # Simple: move away from center of map
        world_bounds = self.world.world_map.get_bounds()
        center_x, center_y = world_bounds[0] / 2, world_bounds[1] / 2

        # Move towards edges
        if agent.x < center_x:
            safe_x = max(5, agent.x - 10)
        else:
            safe_x = min(world_bounds[0] - 5, agent.x + 10)

        if agent.y < center_y:
            safe_y = max(5, agent.y - 10)
        else:
            safe_y = min(world_bounds[1] - 5, agent.y + 10)

        return (safe_x, safe_y)

    def _move_agent_to_target(self, agent, target: Tuple[float, float]):
        """Move agent towards target using simple direct movement"""
        dx = target[0] - agent.x
        dy = target[1] - agent.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance > 0:
            speed = getattr(agent, 'speed', 3.0)
            agent.velocity_x = (dx / distance) * speed
            agent.velocity_y = (dy / distance) * speed

    def _get_distance(self, agent1, agent2) -> float:
        """Get distance between two agents"""
        dx = agent1.x - agent2.x
        dy = agent1.y - agent2.y
        return (dx * dx + dy * dy) ** 0.5

    def _get_distance_to_point(self, agent, point: Tuple[float, float]) -> float:
        """Get distance from agent to point"""
        dx = agent.x - point[0]
        dy = agent.y - point[1]
        return (dx * dx + dy * dy) ** 0.5

    def _give_agent_fish(self, agent):
        """Give agent a fish item (simplified)"""
        # In a real implementation, this would add to agent's inventory
        # For now, just log it
        logger.debug(f"Agent {agent.id[:8]} received fish")

    def _give_agent_wood(self, agent):
        """Give agent wood item (simplified)"""
        # In a real implementation, this would add to agent's inventory
        # For now, just log it
        logger.debug(f"Agent {agent.id[:8]} received wood")

    def get_agent_state_info(self, agent_id: str) -> Dict[str, Any]:
        """Get debug information about agent's AI state"""
        return {
            "state": self.agent_states.get(agent_id, "unknown").value,
            "has_target": agent_id in self.agent_targets,
            "target": self.agent_targets.get(agent_id),
            "last_timer": self.agent_timers.get(agent_id, 0)
        }