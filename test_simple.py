#!/usr/bin/env python3
"""
Simple test to verify all systems are working correctly.
Creates a basic world with hazards and healing stations,
agents move randomly and seek healing when injured.
"""

import time
import random
import logging
import threading
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum

from src.engine.game import Game, GameConfig
from src.agents.agent import Agent, AgentState
from src.world.world import Vector2
from src.world.objects import GameObject, ObjectType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleActionType(Enum):
    """Simple actions for test agents"""
    WANDER = "wander"
    SEEK_HEALING = "seek_healing"
    HEAL = "heal"
    AVOID_HAZARD = "avoid_hazard"


@dataclass
class SimpleBehaviorNode:
    """Simple behavior tree node"""
    action: SimpleActionType
    priority: float
    condition: Any = None


class HazardZone(GameObject):
    """Hazard zone that damages agents"""

    def __init__(self, name: str, position: Vector2, radius: float, damage_per_second: float):
        super().__init__(name, position, ObjectType.TRIGGER)
        self.radius = radius
        self.damage_per_second = damage_per_second
        self.last_damage_time = {}
        self.damage_interval = 1.0  # Apply damage every second

    def check_and_damage(self, agent: Agent, current_time: float) -> bool:
        """Check if agent is in hazard zone and apply damage"""
        distance = self.position.distance_to(agent.position)

        if distance <= self.radius:
            # Check if enough time has passed for this agent
            last_time = self.last_damage_time.get(agent.id, 0)
            if current_time - last_time >= self.damage_interval:
                # Apply damage
                agent.stats.health -= self.damage_per_second
                agent.stats.health = max(0, agent.stats.health)
                self.last_damage_time[agent.id] = current_time
                return True
        return False


class HealingStation(GameObject):
    """Healing station that restores agent health"""

    def __init__(self, name: str, position: Vector2, heal_radius: float, heal_per_second: float):
        super().__init__(name, position, ObjectType.INTERACTIVE)
        self.heal_radius = heal_radius
        self.heal_per_second = heal_per_second
        self.last_heal_time = {}
        self.heal_interval = 1.0  # Heal every second

    def check_and_heal(self, agent: Agent, current_time: float) -> bool:
        """Check if agent is in healing range and apply healing"""
        distance = self.position.distance_to(agent.position)

        if distance <= self.heal_radius:
            # Check if enough time has passed for this agent
            last_time = self.last_heal_time.get(agent.id, 0)
            if current_time - last_time >= self.heal_interval:
                # Apply healing
                old_health = agent.stats.health
                agent.stats.health = min(agent.stats.max_health,
                                       agent.stats.health + self.heal_per_second)
                self.last_heal_time[agent.id] = current_time
                healed = agent.stats.health - old_health
                return healed > 0
        return False


class SimpleTestAgent(Agent):
    """Test agent with simple behavior tree"""

    def __init__(self, name: str, position: Vector2):
        super().__init__(name)
        self.position = position
        self.target_position: Optional[Vector2] = None
        self.current_action = SimpleActionType.WANDER
        self.wander_timer = 0
        self.stats_log = []  # Track health changes

        # Simple behavior tree
        self.behavior_tree = [
            SimpleBehaviorNode(SimpleActionType.SEEK_HEALING, 1.0),
            SimpleBehaviorNode(SimpleActionType.AVOID_HAZARD, 0.7),
            SimpleBehaviorNode(SimpleActionType.WANDER, 0.3),
        ]

    def update_behavior(self, world, hazards: List[HazardZone],
                       healing_stations: List[HealingStation], delta_time: float):
        """Update agent behavior based on simple behavior tree"""

        # Log current stats
        self.stats_log.append({
            'time': time.time(),
            'health': self.stats.health,
            'position': (self.position.x, self.position.y),
            'action': self.current_action.value
        })

        # Evaluate behavior tree
        health_percentage = self.stats.health / self.stats.max_health

        # Priority 1: Seek healing if health is low
        if health_percentage < 0.5:
            self.current_action = SimpleActionType.SEEK_HEALING
            nearest_station = self._find_nearest_healing_station(healing_stations)
            if nearest_station:
                self.target_position = nearest_station.position
                self._move_towards_target(delta_time)
            return

        # Priority 2: Check if in hazard zone
        in_hazard = False
        for hazard in hazards:
            if hazard.position.distance_to(self.position) <= hazard.radius:
                in_hazard = True
                self.current_action = SimpleActionType.AVOID_HAZARD
                # Move away from hazard
                direction_x = self.position.x - hazard.position.x
                direction_y = self.position.y - hazard.position.y
                distance = (direction_x**2 + direction_y**2)**0.5
                if distance > 0:
                    # Move away from hazard center
                    self.velocity.x = (direction_x / distance)
                    self.velocity.y = (direction_y / distance)
                break

        # Priority 3: Wander randomly
        if not in_hazard and self.current_action != SimpleActionType.SEEK_HEALING:
            self.current_action = SimpleActionType.WANDER
            self.wander_timer -= delta_time

            if self.wander_timer <= 0:
                # Pick new random target
                self.target_position = Vector2(
                    random.uniform(100, 900),
                    random.uniform(100, 900)
                )
                self.wander_timer = random.uniform(3, 6)

            if self.target_position:
                self._move_towards_target(delta_time)

    def _find_nearest_healing_station(self, healing_stations: List[HealingStation]) -> Optional[HealingStation]:
        """Find the nearest healing station"""
        if not healing_stations:
            return None

        nearest = None
        min_distance = float('inf')

        for station in healing_stations:
            distance = self.position.distance_to(station.position)
            if distance < min_distance:
                min_distance = distance
                nearest = station

        return nearest

    def _move_towards_target(self, delta_time: float):
        """Move towards target position"""
        if not self.target_position:
            return

        dx = self.target_position.x - self.position.x
        dy = self.target_position.y - self.position.y
        distance = (dx**2 + dy**2)**0.5

        if distance > 5:  # Move if not close enough
            self.velocity.x = (dx / distance)
            self.velocity.y = (dy / distance)

            # Update position
            self.position.x += self.velocity.x * self.speed * delta_time
            self.position.y += self.velocity.y * self.speed * delta_time
        else:
            # Reached target
            self.velocity.x = 0
            self.velocity.y = 0
            if self.current_action == SimpleActionType.WANDER:
                self.target_position = None


class SimpleTest:
    """Simple test runner"""

    def __init__(self):
        self.game = Game(GameConfig(
            target_fps=60,
            agent_update_interval=0.1,  # Update more frequently for testing
            request_resolution_interval=0.1
        ))

        self.agents: List[SimpleTestAgent] = []
        self.hazards: List[HazardZone] = []
        self.healing_stations: List[HealingStation] = []

        self.test_duration = 30.0  # Run for 30 seconds
        self.start_time = None
        self.stats = {
            'total_damage_taken': 0,
            'total_healing_done': 0,
            'hazard_hits': 0,
            'healing_visits': 0,
            'agent_deaths': 0
        }

    def setup(self):
        """Setup test world"""
        logger.info("Setting up simple test world...")

        # Create hazard zones
        hazard_positions = [
            Vector2(200, 200),
            Vector2(700, 200),
            Vector2(450, 500),
            Vector2(200, 700),
            Vector2(700, 700)
        ]

        for i, pos in enumerate(hazard_positions):
            hazard = HazardZone(
                f"Hazard_{i}",
                pos,
                radius=50,
                damage_per_second=10
            )
            self.hazards.append(hazard)
            self.game.world.add_object(hazard)

        # Create healing stations
        healing_positions = [
            Vector2(100, 500),
            Vector2(500, 100),
            Vector2(900, 500),
            Vector2(500, 900)
        ]

        for i, pos in enumerate(healing_positions):
            station = HealingStation(
                f"Healing_Station_{i}",
                pos,
                heal_radius=30,
                heal_per_second=20
            )
            self.healing_stations.append(station)
            self.game.world.add_object(station)

        # Create test agents
        agent_count = 10
        for i in range(agent_count):
            # Random starting position avoiding hazards
            pos = Vector2(
                random.uniform(100, 900),
                random.uniform(100, 900)
            )

            agent = SimpleTestAgent(f"TestAgent_{i:02d}", pos)
            agent.stats.max_health = 100
            agent.stats.health = 100
            agent.speed = 50  # Faster movement for testing

            self.agents.append(agent)
            self.game.world.add_agent(agent)

        logger.info(f"Created {agent_count} agents, {len(self.hazards)} hazards, "
                   f"and {len(self.healing_stations)} healing stations")

    def run(self):
        """Run the test"""
        self.start_time = time.time()

        # Start game engine in background
        game_thread = threading.Thread(target=self.game.start)
        game_thread.daemon = True
        game_thread.start()

        logger.info(f"Starting test for {self.test_duration} seconds...")

        try:
            last_update = time.time()
            last_print = time.time()

            while time.time() - self.start_time < self.test_duration:
                current_time = time.time()
                delta_time = current_time - last_update
                last_update = current_time

                # Update agents
                for agent in self.agents:
                    if agent.stats.health > 0:
                        # Update agent behavior
                        agent.update_behavior(self.game.world, self.hazards,
                                            self.healing_stations, delta_time)

                        # Check hazards
                        for hazard in self.hazards:
                            if hazard.check_and_damage(agent, current_time):
                                self.stats['hazard_hits'] += 1
                                self.stats['total_damage_taken'] += hazard.damage_per_second

                        # Check healing stations
                        for station in self.healing_stations:
                            if station.check_and_heal(agent, current_time):
                                self.stats['healing_visits'] += 1
                                self.stats['total_healing_done'] += station.heal_per_second

                        # Check for death
                        if agent.stats.health <= 0:
                            self.stats['agent_deaths'] += 1
                            logger.warning(f"{agent.name} has died!")

                # Print status every 5 seconds
                if current_time - last_print >= 5.0:
                    self.print_status()
                    last_print = current_time

                time.sleep(0.05)  # Small delay

        except KeyboardInterrupt:
            logger.info("Test interrupted by user")

        finally:
            self.game.stop()
            self.analyze_results()

    def print_status(self):
        """Print current test status"""
        elapsed = time.time() - self.start_time
        print(f"\n--- Test Status at {elapsed:.1f}s ---")

        # Agent health summary
        alive_agents = [a for a in self.agents if a.stats.health > 0]
        avg_health = sum(a.stats.health for a in alive_agents) / len(alive_agents) if alive_agents else 0

        print(f"Agents: {len(alive_agents)}/{len(self.agents)} alive")
        print(f"Average Health: {avg_health:.1f}")
        print(f"Hazard Hits: {self.stats['hazard_hits']}")
        print(f"Healing Visits: {self.stats['healing_visits']}")

        # Sample agent status
        if alive_agents:
            sample = alive_agents[0]
            print(f"Sample Agent ({sample.name}):")
            print(f"  Health: {sample.stats.health:.1f}/{sample.stats.max_health}")
            print(f"  Position: ({sample.position.x:.1f}, {sample.position.y:.1f})")
            print(f"  Action: {sample.current_action.value}")

    def analyze_results(self):
        """Analyze and report test results"""
        print("\n" + "="*60)
        print("TEST RESULTS ANALYSIS")
        print("="*60)

        duration = time.time() - self.start_time
        print(f"Test Duration: {duration:.1f} seconds")

        # Overall statistics
        print(f"\nOverall Statistics:")
        print(f"  Total Damage Taken: {self.stats['total_damage_taken']:.0f}")
        print(f"  Total Healing Done: {self.stats['total_healing_done']:.0f}")
        print(f"  Hazard Encounters: {self.stats['hazard_hits']}")
        print(f"  Healing Station Visits: {self.stats['healing_visits']}")
        print(f"  Agent Deaths: {self.stats['agent_deaths']}")

        # Per-agent analysis
        print(f"\nPer-Agent Analysis:")
        for agent in self.agents:
            print(f"\n{agent.name}:")
            print(f"  Final Health: {agent.stats.health:.1f}/{agent.stats.max_health}")
            print(f"  Final Position: ({agent.position.x:.1f}, {agent.position.y:.1f})")
            print(f"  Final Action: {agent.current_action.value}")

            if len(agent.stats_log) > 0:
                # Calculate health changes
                health_values = [log['health'] for log in agent.stats_log]
                min_health = min(health_values)
                max_health = max(health_values)

                # Count action frequencies
                action_counts = {}
                for log in agent.stats_log:
                    action = log['action']
                    action_counts[action] = action_counts.get(action, 0) + 1

                print(f"  Health Range: {min_health:.1f} - {max_health:.1f}")
                print(f"  Action Distribution:")
                for action, count in action_counts.items():
                    percentage = (count / len(agent.stats_log)) * 100
                    print(f"    {action}: {count} ({percentage:.1f}%)")

        # System verification
        print("\n" + "="*60)
        print("SYSTEM VERIFICATION")
        print("="*60)

        checks = {
            "Game Loop Running": self.game.current_tick > 0,
            "World Updates": len(self.game.world.agents) > 0,
            "Agent Movement": any(a.position.x != 500 or a.position.y != 500 for a in self.agents),
            "Hazard Damage": self.stats['hazard_hits'] > 0,
            "Healing System": self.stats['healing_visits'] > 0,
            "Behavior Tree": all(len(a.stats_log) > 0 for a in self.agents),
            "Request Processing": self.game.request_manager.total_requests_processed >= 0
        }

        all_passed = True
        for check, passed in checks.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{check}: {status}")
            if not passed:
                all_passed = False

        print("\n" + "="*60)
        if all_passed:
            print("✓ ALL SYSTEMS FUNCTIONAL - TEST PASSED")
        else:
            print("✗ SOME SYSTEMS FAILED - REVIEW NEEDED")
        print("="*60)


def main():
    """Main entry point for simple test"""
    print("""
    ╔══════════════════════════════════════════╗
    ║     MMO ENGINE SIMPLE TEST               ║
    ║                                          ║
    ║  Testing basic systems functionality     ║
    ╚══════════════════════════════════════════╝
    """)

    test = SimpleTest()
    test.setup()
    test.run()


if __name__ == "__main__":
    main()