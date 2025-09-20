#!/usr/bin/env python3
"""
Example agent using the client-server architecture
"""

import asyncio
import random
import logging
from typing import Dict, Any

from client.core.agent_client import AgentClient, AgentConfig
from shared.math_utils import Vector2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleExplorerAgent(AgentClient):
    """Simple agent that explores and avoids danger"""

    def __init__(self, name: str):
        config = AgentConfig(
            name=name,
            agent_class="Explorer",
            personality={'exploration': 0.8, 'risk_taking': 0.3}
        )
        super().__init__(config)

        self.last_move_time = 0
        self.target_position = None

    async def make_decision(self):
        """Enhanced decision making"""
        current_time = asyncio.get_event_loop().time()

        # Get nearby entities
        nearby_entities = self.world_view.get_nearby_entities(self.position, 50)

        # Check for threats
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']
        if enemies and self.health < 50:
            # Run away from nearest enemy
            nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))
            escape_direction = (self.position - nearest_enemy.position).normalize()
            escape_target = self.position + escape_direction * 100

            self.action_queue.append({
                'type': 'move',
                'target': escape_target
            })
            logger.info(f"{self.config.name} fleeing from {nearest_enemy.name}")
            return

        # Check for NPCs to interact with
        npcs = [e for e in nearby_entities if e.entity_type == 'npc']
        if npcs and random.random() < 0.1:  # 10% chance
            nearest_npc = min(npcs, key=lambda e: e.position.distance_to(self.position))
            if nearest_npc.position.distance_to(self.position) < 20:
                self.action_queue.append({
                    'type': 'interact',
                    'target_id': nearest_npc.id
                })
                logger.info(f"{self.config.name} interacting with {nearest_npc.name}")
                return

        # Exploration behavior
        if (self.state == "idle" and
            current_time - self.last_move_time > 3.0):  # Move every 3 seconds

            # Random exploration with some intelligence
            if not self.target_position or self.position.distance_to(self.target_position) < 10:
                # Pick new target
                angle = random.uniform(0, 6.28)  # 2π
                distance = random.uniform(50, 150)
                self.target_position = Vector2(
                    self.position.x + distance * random.uniform(-1, 1),
                    self.position.y + distance * random.uniform(-1, 1)
                )

                # Clamp to world bounds (simplified)
                self.target_position.x = max(50, min(9950, self.target_position.x))
                self.target_position.y = max(50, min(9950, self.target_position.y))

            self.action_queue.append({
                'type': 'move',
                'target': self.target_position
            })
            self.last_move_time = current_time

    async def _handle_world_update(self, message):
        """Handle world updates and extract info"""
        await super()._handle_world_update(message)

        # Update our position from visible entities (find ourselves)
        for entity_data in message.visible_entities:
            if entity_data['id'] == self.agent_id:
                self.position = Vector2.from_tuple(entity_data['position'])
                self.health = entity_data['health_percentage']
                break


class CombatAgent(AgentClient):
    """Aggressive agent that seeks combat"""

    def __init__(self, name: str):
        config = AgentConfig(
            name=name,
            agent_class="Warrior",
            personality={'risk_taking': 0.9, 'exploration': 0.4}
        )
        super().__init__(config)

    async def make_decision(self):
        """Aggressive combat behavior"""
        # Look for enemies to fight
        nearby_entities = self.world_view.get_nearby_entities(self.position, 100)
        enemies = [e for e in nearby_entities if e.entity_type == 'enemy']

        if enemies and self.health > 30:
            # Find nearest enemy
            nearest_enemy = min(enemies, key=lambda e: e.position.distance_to(self.position))

            if nearest_enemy.position.distance_to(self.position) <= 20:
                # Attack if in range
                self.action_queue.append({
                    'type': 'attack',
                    'target_id': nearest_enemy.id
                })
                logger.info(f"{self.config.name} attacking {nearest_enemy.name}")
            else:
                # Move closer
                self.action_queue.append({
                    'type': 'move',
                    'target': nearest_enemy.position
                })
        elif self.health < 50:
            # Look for healing (NPCs or retreat)
            npcs = [e for e in nearby_entities if e.entity_type == 'npc']
            if npcs:
                nearest_npc = min(npcs, key=lambda e: e.position.distance_to(self.position))
                self.action_queue.append({
                    'type': 'move',
                    'target': nearest_npc.position
                })
        else:
            # Patrol/explore
            if random.random() < 0.2:
                target = Vector2(
                    random.uniform(100, 9900),
                    random.uniform(100, 9900)
                )
                self.action_queue.append({
                    'type': 'move',
                    'target': target
                })


async def run_agent(agent_class, name: str):
    """Run a single agent"""
    agent = agent_class(name)

    try:
        success = await agent.connect()
        if success:
            await agent.run()
        else:
            logger.error(f"Failed to connect agent {name}")
    except Exception as e:
        logger.error(f"Agent {name} error: {e}")


async def main():
    """Run multiple example agents"""
    print("Starting client agents...")

    # Try to load agent configuration for better defaults
    try:
        import sys
        sys.path.append('.')
        from config.config_loader import ConfigLoader

        config_loader = ConfigLoader("config")
        if config_loader.load_all_configs() and config_loader.agent_config:
            # Use configured scenario if available
            scenario = config_loader.get_test_scenario("basic_exploration")
            if scenario:
                print("Using configured agent scenario")
                agents = []
                for agent_group in scenario["agents"]:
                    template_name = agent_group["template"]
                    count = agent_group["count"]
                    base_name = agent_group["name"]

                    for i in range(count):
                        name = f"{base_name}_{i+1}"
                        if template_name.lower() in ['warrior', 'fighter']:
                            agents.append((CombatAgent, name))
                        else:
                            agents.append((SimpleExplorerAgent, name))
            else:
                raise Exception("No scenario found")
        else:
            raise Exception("No config available")

    except Exception:
        # Fallback to hardcoded agents
        print("Using default agent configuration")
        agents = [
            (SimpleExplorerAgent, "Explorer_Alice"),
            (SimpleExplorerAgent, "Explorer_Bob"),
            (CombatAgent, "Warrior_Chuck"),
            (SimpleExplorerAgent, "Explorer_Diana"),
            (CombatAgent, "Warrior_Eve"),
        ]

    print(f"Starting {len(agents)} agents...")

    # Run all agents concurrently
    tasks = []
    for agent_class, name in agents:
        task = asyncio.create_task(run_agent(agent_class, name))
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