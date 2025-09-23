#!/usr/bin/env python3
"""
Improved exploration agent with more natural movement patterns
"""

import asyncio
import random
import logging
import math
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import deque

from client.core.agent_client import AgentClient, AgentConfig
from shared.math_utils import Vector2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImprovedExplorerAgent(AgentClient):
    """Agent with improved exploration using frontier-based approach and directional persistence"""

    def __init__(self, name: str):
        config = AgentConfig(
            name=name,
            agent_class="Mage",
            personality={'exploration': 0.9, 'combat_seeking': 0.2, 'caution': 0.5, 'aggression': 0.3}
        )
        super().__init__(config)

        self.last_move_time = 0
        self.last_attack_time = 0

        # Combat stats
        self.combat_stats = {
            'attack_cooldown': 2.0,
            'attack_range': 80.0,
            'attack_damage': 50,
            'flee_health_threshold': 0.4
        }

        # Improved exploration system
        self.exploration_state = {
            'current_direction': None,  # Current exploration direction (angle in radians)
            'direction_persistence': 0.8,  # How likely to continue in same direction
            'direction_variance': 0.3,  # How much to vary direction (in radians)
            'momentum_steps': 0,  # How many steps in current direction
            'max_momentum': 10,  # Maximum steps before considering direction change
        }

        # Trail memory - remember recent positions to avoid doubling back
        self.position_trail = deque(maxlen=20)  # Last 20 positions
        self.trail_avoidance_radius = 150  # Avoid getting too close to recent trail

        # Frontier-based exploration
        self.frontier_sectors = {}  # Dict of sector_id -> exploration_score
        self.sector_size = 300  # Size of each exploration sector
        self.current_sector = None
        self.home_position = None

        # Exploration parameters
        self.exploration_radius = 500  # Initial exploration distance
        self.max_exploration_radius = 4000  # Maximum distance from home
        self.step_distance = 200  # Distance to move in each step

        # Target management
        self.current_target = None
        self.stuck_counter = 0
        self.last_position = None

    def _get_sector_id(self, position: Vector2) -> Tuple[int, int]:
        """Get sector ID for a position"""
        sector_x = int(position.x // self.sector_size)
        sector_y = int(position.y // self.sector_size)
        return (sector_x, sector_y)

    def _update_sector_exploration(self, position: Vector2):
        """Update exploration score for current sector"""
        sector_id = self._get_sector_id(position)

        # Initialize home position
        if self.home_position is None:
            self.home_position = Vector2(position.x, position.y)
            logger.info(f"🏠 {self.config.name} HOME: ({self.home_position.x:.0f},{self.home_position.y:.0f})")

        # Update sector exploration score
        if sector_id not in self.frontier_sectors:
            self.frontier_sectors[sector_id] = 0
            logger.info(f"📍 {self.config.name} discovered new sector {sector_id}")

        self.frontier_sectors[sector_id] += 1
        self.current_sector = sector_id

    def _get_frontier_direction(self, current_pos: Vector2) -> Optional[float]:
        """Get direction towards least explored frontier"""
        current_sector = self._get_sector_id(current_pos)

        # Find neighboring sectors and their exploration scores
        frontier_candidates = []

        # Check 8 neighboring sectors plus some further ones
        search_patterns = [
            # Immediate neighbors
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),           (1, 0),
            (-1, 1),  (0, 1),  (1, 1),
            # Extended search
            (-2, 0), (2, 0), (0, -2), (0, 2),
            (-2, -2), (2, 2), (-2, 2), (2, -2)
        ]

        for dx, dy in search_patterns:
            sector_id = (current_sector[0] + dx, current_sector[1] + dy)
            sector_center = Vector2(
                sector_id[0] * self.sector_size + self.sector_size / 2,
                sector_id[1] * self.sector_size + self.sector_size / 2
            )

            # Check if within world bounds
            if 500 <= sector_center.x <= 9500 and 500 <= sector_center.y <= 9500:
                # Calculate exploration priority (lower score = higher priority)
                exploration_score = self.frontier_sectors.get(sector_id, 0)
                distance = current_pos.distance_to(sector_center)

                # Prioritize unexplored sectors that aren't too far
                if distance <= self.exploration_radius * 2:
                    priority = exploration_score * 1000 + distance
                    frontier_candidates.append((priority, sector_center, sector_id))

        if frontier_candidates:
            # Sort by priority (lower is better)
            frontier_candidates.sort(key=lambda x: x[0])

            # Pick from top candidates with some randomness
            n_candidates = min(3, len(frontier_candidates))
            chosen = random.choice(frontier_candidates[:n_candidates])

            target_pos = chosen[1]
            direction = math.atan2(
                target_pos.y - current_pos.y,
                target_pos.x - current_pos.x
            )

            logger.info(f"🧭 {self.config.name} heading to frontier sector {chosen[2]} (score: {chosen[0]:.0f})")
            return direction

        return None

    def _avoid_trail(self, proposed_target: Vector2) -> Vector2:
        """Adjust target to avoid recent trail"""
        if len(self.position_trail) < 5:
            return proposed_target

        # Check if proposed target is too close to recent trail
        min_distance = float('inf')
        closest_trail_pos = None

        for trail_pos in self.position_trail:
            dist = proposed_target.distance_to(trail_pos)
            if dist < min_distance:
                min_distance = dist
                closest_trail_pos = trail_pos

        # If too close to trail, adjust direction
        if min_distance < self.trail_avoidance_radius and closest_trail_pos:
            # Push away from trail
            avoid_vector = (proposed_target - closest_trail_pos).normalize()
            adjusted_target = closest_trail_pos + avoid_vector * (self.trail_avoidance_radius * 1.5)

            # Ensure within bounds
            adjusted_target.x = max(500, min(9500, adjusted_target.x))
            adjusted_target.y = max(500, min(9500, adjusted_target.y))

            logger.debug(f"📍 {self.config.name} avoiding trail, adjusted target")
            return adjusted_target

        return proposed_target

    def _get_exploration_target(self, current_pos: Vector2) -> Vector2:
        """Get next exploration target using improved algorithm"""

        # Update current position tracking
        self._update_sector_exploration(current_pos)
        self.position_trail.append(Vector2(current_pos.x, current_pos.y))

        # Check if stuck (not moving much)
        if self.last_position and current_pos.distance_to(self.last_position) < 50:
            self.stuck_counter += 1
        else:
            self.stuck_counter = 0
        self.last_position = Vector2(current_pos.x, current_pos.y)

        # If stuck, force a new random direction
        if self.stuck_counter > 3:
            logger.info(f"🔄 {self.config.name} stuck, choosing new random direction")
            self.exploration_state['current_direction'] = random.uniform(0, 2 * math.pi)
            self.exploration_state['momentum_steps'] = 0
            self.stuck_counter = 0
            self.exploration_radius = min(self.exploration_radius * 1.2, self.max_exploration_radius)

        # Determine exploration direction
        direction = None

        # First, try to get frontier direction
        if random.random() > 0.3:  # 70% chance to use frontier
            direction = self._get_frontier_direction(current_pos)

        # If no frontier or random chance, use directional persistence
        if direction is None:
            if self.exploration_state['current_direction'] is None:
                # Initialize with random direction
                direction = random.uniform(0, 2 * math.pi)
            elif (self.exploration_state['momentum_steps'] < self.exploration_state['max_momentum']
                  and random.random() < self.exploration_state['direction_persistence']):
                # Continue in current direction with small variance
                variance = random.uniform(-self.exploration_state['direction_variance'],
                                         self.exploration_state['direction_variance'])
                direction = self.exploration_state['current_direction'] + variance
                self.exploration_state['momentum_steps'] += 1
            else:
                # Time for a new direction - use smooth turn
                turn_angle = random.choice([math.pi/4, math.pi/3, math.pi/2, 2*math.pi/3])
                if random.random() < 0.5:
                    turn_angle = -turn_angle
                direction = self.exploration_state['current_direction'] + turn_angle
                self.exploration_state['momentum_steps'] = 0

        # Update current direction
        self.exploration_state['current_direction'] = direction

        # Calculate target position
        step_distance = self.step_distance * random.uniform(0.8, 1.2)  # Add some variance
        target_x = current_pos.x + step_distance * math.cos(direction)
        target_y = current_pos.y + step_distance * math.sin(direction)

        # Keep within bounds
        target_x = max(500, min(9500, target_x))
        target_y = max(500, min(9500, target_y))

        proposed_target = Vector2(target_x, target_y)

        # Avoid recent trail
        final_target = self._avoid_trail(proposed_target)

        # Check distance from home
        if self.home_position:
            home_distance = final_target.distance_to(self.home_position)
            if home_distance > self.max_exploration_radius:
                # Turn back towards home
                home_direction = math.atan2(
                    self.home_position.y - current_pos.y,
                    self.home_position.x - current_pos.x
                )
                # Add some randomness to avoid getting stuck
                home_direction += random.uniform(-math.pi/4, math.pi/4)

                target_x = current_pos.x + step_distance * math.cos(home_direction)
                target_y = current_pos.y + step_distance * math.sin(home_direction)
                final_target = Vector2(
                    max(500, min(9500, target_x)),
                    max(500, min(9500, target_y))
                )
                logger.info(f"🏃 {self.config.name} returning towards home (distance: {home_distance:.0f})")

        return final_target

    async def make_decision(self):
        """Make exploration and combat decisions"""
        current_time = asyncio.get_event_loop().time()

        # Get nearby entities
        nearby_entities = self.world_view.get_nearby_entities(self.position, 150)
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']

        # Simple combat handling
        if enemies:
            nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))
            distance_to_enemy = nearest_enemy.position.distance_to(self.position)

            should_flee = self.health < self.combat_stats['flee_health_threshold']
            can_attack = (
                distance_to_enemy <= self.combat_stats['attack_range'] and
                current_time - self.last_attack_time >= self.combat_stats['attack_cooldown']
            )

            if should_flee:
                escape_direction = (self.position - nearest_enemy.position).normalize()
                escape_target = self.position + escape_direction * 250
                self.action_queue.append({
                    'type': 'move',
                    'target': escape_target
                })
                logger.info(f"💨 {self.config.name} fleeing from {nearest_enemy.name}")
                return
            elif can_attack:
                self.action_queue.append({
                    'type': 'attack',
                    'target_id': nearest_enemy.id,
                    'range': self.combat_stats['attack_range']
                })
                self.last_attack_time = current_time
                logger.info(f"⚔️ {self.config.name} attacking {nearest_enemy.name}")
                return
            elif distance_to_enemy > self.combat_stats['attack_range']:
                self.action_queue.append({
                    'type': 'move',
                    'target': nearest_enemy.position
                })
                logger.info(f"🎯 {self.config.name} approaching {nearest_enemy.name}")
                return

        # Exploration behavior
        if current_time - self.last_move_time > 2.0:
            # Get new exploration target if needed
            if not self.current_target or self.position.distance_to(self.current_target) < 100:
                self.current_target = self._get_exploration_target(self.position)
                logger.info(f"🚶 {self.config.name} exploring to ({self.current_target.x:.0f},{self.current_target.y:.0f})")

            self.action_queue.append({
                'type': 'move',
                'target': self.current_target
            })
            self.last_move_time = current_time


async def run_agent(name: str):
    """Run a single agent"""
    agent = ImprovedExplorerAgent(name)

    try:
        success = await agent.connect()
        if success:
            await agent.run()
        else:
            logger.error(f"Failed to connect agent {name}")
    except Exception as e:
        logger.error(f"Agent {name} error: {e}")


async def main():
    """Run multiple improved explorer agents"""
    print("Starting improved explorer agents...")

    # Get number of agents from command line or use default
    import sys
    num_agents = 5
    if len(sys.argv) > 1:
        try:
            num_agents = int(sys.argv[1])
        except:
            pass

    agents = []
    for i in range(num_agents):
        agents.append(f"Explorer_{i+1}")

    print(f"Starting {len(agents)} improved explorer agents...")

    # Run all agents concurrently
    tasks = []
    for name in agents:
        task = asyncio.create_task(run_agent(name))
        tasks.append(task)

    # Wait for all agents
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("Shutting down agents...")
        for task in tasks:
            task.cancel()


if __name__ == "__main__":
    asyncio.run(main())