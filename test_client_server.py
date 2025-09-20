#!/usr/bin/env python3
"""
Test the client-server architecture with hazards and healing
Similar to the original test but using the new architecture
"""

import asyncio
import time
import random
import math
import logging
import sys
from typing import List, Dict, Any
import subprocess
import signal
import os

# Fix import paths
sys.path.append('.')

from client.core.agent_client import AgentClient, AgentConfig
from shared.math_utils import Vector2
from shared.messages import ActionMessage, ActionType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestAgent(AgentClient):
    """Test agent with simple hazard avoidance and healing behavior"""

    def __init__(self, name: str, personality_type: str = "balanced"):
        # Configure personality based on type
        personalities = {
            "explorer": {"exploration": 0.9, "risk_taking": 0.8, "social": 0.3},
            "cautious": {"exploration": 0.2, "risk_taking": 0.1, "social": 0.6},
            "balanced": {"exploration": 0.5, "risk_taking": 0.5, "social": 0.5},
            "aggressive": {"exploration": 0.4, "risk_taking": 0.9, "social": 0.3}
        }

        config = AgentConfig(
            name=name,
            agent_class="TestAgent",
            personality=personalities.get(personality_type, personalities["balanced"])
        )
        super().__init__(config)

        self.personality_type = personality_type
        self.last_move_time = 0
        self.target_position = None
        self.last_health_check = 0

        # Stats tracking
        self.stats_log = []
        self.actions_taken = {"wander": 0, "avoid_hazard": 0, "seek_healing": 0}

    async def make_decision(self):
        """Enhanced decision making for testing"""
        current_time = time.time()

        # Log current state
        self.stats_log.append({
            'time': current_time,
            'health': self.health,
            'position': (self.position.x, self.position.y),
            'state': self.state
        })

        # Get nearby entities
        nearby_entities = self.world_view.get_nearby_entities(self.position, 80)

        # Debug logging
        if len(nearby_entities) > 0:
            logger.info(f"{self.config.name} sees {len(nearby_entities)} entities")

        # Priority 1: Avoid enemies if health is low
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']
        if enemies and self.health < 50:
            self._flee_from_danger(enemies)
            return

        # Priority 2: Look for NPCs to heal (simulate healing stations)
        npcs = [e for e in nearby_entities if e.entity_type == 'npc']
        if self.health < 70 and npcs:
            self._seek_healing(npcs)
            return

        # Priority 3: Social behavior
        agents = [e for e in nearby_entities if e.entity_type == 'agent']
        if (len(agents) > 1 and
            random.random() < self.config.personality.get('social', 0.5) * 0.1):
            self._interact_socially(agents)
            return

        # Priority 4: Exploration/wandering (more aggressive)
        if (current_time - self.last_move_time > 1.0 and
            self.state == "idle"):
            await self._explore()

    def _flee_from_danger(self, enemies):
        """Run away from nearest enemy"""
        nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))

        # Calculate escape direction
        escape_direction = (self.position - nearest_enemy.position).normalize()
        escape_target = self.position + escape_direction * 100

        # Clamp to world bounds
        escape_target.x = max(50, min(9950, escape_target.x))
        escape_target.y = max(50, min(9950, escape_target.y))

        self.action_queue.append({
            'type': 'move',
            'target': escape_target
        })
        self.actions_taken["avoid_hazard"] += 1
        logger.info(f"{self.config.name} fleeing from {nearest_enemy.name}")

    def _seek_healing(self, npcs):
        """Move towards nearest NPC for healing"""
        nearest_npc = min(npcs, key=lambda e: e.position.distance_to(self.position))

        if nearest_npc.position.distance_to(self.position) < 15:
            # Close enough to interact
            self.action_queue.append({
                'type': 'interact',
                'target_id': nearest_npc.id
            })
            logger.info(f"{self.config.name} seeking healing from {nearest_npc.name}")
        else:
            # Move closer
            self.action_queue.append({
                'type': 'move',
                'target': nearest_npc.position
            })

        self.actions_taken["seek_healing"] += 1

    def _interact_socially(self, agents):
        """Interact with nearby agents"""
        other_agents = [a for a in agents if a.id != self.agent_id]
        if other_agents:
            target = random.choice(other_agents)
            if target.position.distance_to(self.position) < 20:
                self.action_queue.append({
                    'type': 'interact',
                    'target_id': target.id
                })
                logger.info(f"{self.config.name} interacting socially with {target.name}")

    async def _explore(self):
        """Random exploration behavior"""
        exploration_factor = self.config.personality.get('exploration', 0.5)
        risk_factor = self.config.personality.get('risk_taking', 0.5)

        # Determine exploration range based on personality
        base_range = 100
        range_modifier = 0.5 + exploration_factor
        max_distance = base_range * range_modifier

        # Pick random target with some intelligence
        angle = random.uniform(0, 6.28)  # 2π
        distance = random.uniform(50, max_distance)

        target = Vector2(
            self.position.x + distance * math.cos(angle),
            self.position.y + distance * math.sin(angle)
        )

        # Clamp to world bounds
        target.x = max(50, min(9950, target.x))
        target.y = max(50, min(9950, target.y))

        self.action_queue.append({
            'type': 'move',
            'target': target
        })
        self.actions_taken["wander"] += 1
        self.last_move_time = time.time()

    async def _handle_world_update(self, message):
        """Handle world updates and extract agent info"""
        await super()._handle_world_update(message)

        # Find ourselves in the update to get current stats
        for entity_data in message.visible_entities:
            if entity_data['id'] == self.agent_id:
                self.position = Vector2.from_tuple(entity_data['position'])
                self.health = entity_data['health_percentage']
                self.state = entity_data['state']
                break

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get stats summary for analysis"""
        if not self.stats_log:
            return {}

        health_values = [log['health'] for log in self.stats_log]
        return {
            'name': self.config.name,
            'personality_type': self.personality_type,
            'final_health': self.health,
            'min_health': min(health_values) if health_values else 0,
            'max_health': max(health_values) if health_values else 0,
            'avg_health': sum(health_values) / len(health_values) if health_values else 0,
            'actions_taken': self.actions_taken.copy(),
            'total_decisions': len(self.stats_log)
        }


class ClientServerTest:
    """Test runner for client-server architecture"""

    def __init__(self):
        self.server_process = None
        self.test_duration = 30.0  # 30 seconds
        self.agents: List[TestAgent] = []

    async def setup(self):
        """Setup test environment"""
        logger.info("Starting client-server test...")

        # Start server
        logger.info("Starting server process...")
        self.server_process = subprocess.Popen(
            [sys.executable, "run_server.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to start
        await asyncio.sleep(3)

        # Check if server started successfully
        if self.server_process.poll() is not None:
            logger.error("Server failed to start")
            return False

        logger.info("Server started successfully")

        # Create test agents with different personalities
        agent_configs = [
            ("Explorer_Alpha", "explorer"),
            ("Cautious_Beta", "cautious"),
            ("Balanced_Gamma", "balanced"),
            ("Aggressive_Delta", "aggressive"),
            ("Explorer_Epsilon", "explorer"),
            ("Cautious_Zeta", "cautious"),
        ]

        for name, personality in agent_configs:
            agent = TestAgent(name, personality)
            self.agents.append(agent)

        logger.info(f"Created {len(self.agents)} test agents")
        return True

    async def run_test(self):
        """Run the main test"""
        if not await self.setup():
            return

        # Connect all agents
        logger.info("Connecting agents to server...")
        connect_tasks = []
        for agent in self.agents:
            task = asyncio.create_task(agent.connect())
            connect_tasks.append(task)

        # Wait for all connections
        results = await asyncio.gather(*connect_tasks, return_exceptions=True)
        connected_agents = []

        for i, result in enumerate(results):
            if result is True:
                connected_agents.append(self.agents[i])
                logger.info(f"Agent {self.agents[i].config.name} connected")
            else:
                logger.error(f"Agent {self.agents[i].config.name} failed to connect: {result}")

        if not connected_agents:
            logger.error("No agents connected successfully")
            await self.cleanup()
            return

        # Run agent behaviors
        logger.info(f"Running test with {len(connected_agents)} agents for {self.test_duration} seconds...")

        # Start all agent loops
        agent_tasks = []
        for agent in connected_agents:
            task = asyncio.create_task(agent.run())
            agent_tasks.append(task)

        # Wait for test duration
        try:
            await asyncio.wait_for(
                asyncio.gather(*agent_tasks, return_exceptions=True),
                timeout=self.test_duration
            )
        except asyncio.TimeoutError:
            logger.info("Test duration completed")
            # Cancel agent tasks
            for task in agent_tasks:
                task.cancel()

        # Analyze results
        await self.analyze_results(connected_agents)
        await self.cleanup()

    async def analyze_results(self, agents: List[TestAgent]):
        """Analyze test results"""
        logger.info("Analyzing test results...")

        print("\n" + "="*60)
        print("CLIENT-SERVER TEST RESULTS")
        print("="*60)

        # Overall statistics
        total_actions = sum(sum(agent.actions_taken.values()) for agent in agents)
        print(f"Test Duration: {self.test_duration} seconds")
        print(f"Connected Agents: {len(agents)}")
        print(f"Total Actions: {total_actions}")

        # Per-agent analysis
        print("\nPer-Agent Analysis:")
        print("-" * 40)

        for agent in agents:
            stats = agent.get_stats_summary()
            if stats:
                print(f"\n{stats['name']} ({stats['personality_type']}):")
                print(f"  Final Health: {stats['final_health']:.1f}%")
                print(f"  Health Range: {stats['min_health']:.1f} - {stats['max_health']:.1f}%")
                print(f"  Average Health: {stats['avg_health']:.1f}%")
                print(f"  Actions: {stats['actions_taken']}")
                print(f"  Total Decisions: {stats['total_decisions']}")

        # Personality analysis
        print("\nPersonality Type Analysis:")
        print("-" * 40)

        personality_stats = {}
        for agent in agents:
            ptype = agent.personality_type
            if ptype not in personality_stats:
                personality_stats[ptype] = {'agents': [], 'avg_health': 0, 'total_actions': 0}

            stats = agent.get_stats_summary()
            if stats:
                personality_stats[ptype]['agents'].append(agent)
                personality_stats[ptype]['avg_health'] += stats['avg_health']
                personality_stats[ptype]['total_actions'] += sum(stats['actions_taken'].values())

        for ptype, data in personality_stats.items():
            count = len(data['agents'])
            if count > 0:
                avg_health = data['avg_health'] / count
                print(f"{ptype.title()}: {count} agents, avg health: {avg_health:.1f}%, actions: {data['total_actions']}")

        # System verification
        print("\n" + "="*60)
        print("SYSTEM VERIFICATION")
        print("="*60)

        checks = {
            "Server Running": self.server_process.poll() is None,
            "Agents Connected": len(agents) > 0,
            "Agents Making Decisions": any(agent.stats_log for agent in agents),
            "Actions Executed": total_actions > 0,
            "Behavior Variety": len(set(agent.personality_type for agent in agents)) > 1,
            "Health Tracking": any(agent.health != 100 for agent in agents),
        }

        all_passed = True
        for check, passed in checks.items():
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{check}: {status}")
            if not passed:
                all_passed = False

        print("\n" + "="*60)
        if all_passed:
            print("✓ CLIENT-SERVER ARCHITECTURE TEST PASSED")
        else:
            print("✗ SOME TESTS FAILED - REVIEW NEEDED")
        print("="*60)

    async def cleanup(self):
        """Clean up test environment"""
        logger.info("Cleaning up test...")

        # Disconnect all agents
        for agent in self.agents:
            if agent.connected:
                await agent.disconnect()

        # Stop server
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                self.server_process.wait()

        logger.info("Cleanup complete")


async def main():
    """Main test entry point"""
    print("""
    ╔══════════════════════════════════════════╗
    ║     CLIENT-SERVER ARCHITECTURE TEST     ║
    ║                                          ║
    ║  Testing new separated architecture      ║
    ╚══════════════════════════════════════════╝
    """)

    test = ClientServerTest()
    try:
        await test.run_test()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        await test.cleanup()
    except Exception as e:
        logger.error(f"Test error: {e}")
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(main())