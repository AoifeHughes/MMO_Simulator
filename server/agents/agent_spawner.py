"""
Automatic agent spawning and management system
"""

import asyncio
import random
import time
import logging
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field

from shared.math_utils import Vector2
from config.config_loader import AgentTemplate

logger = logging.getLogger(__name__)


@dataclass
class SpawnedAgentInfo:
    """Information about a spawned agent"""
    agent_id: str
    name: str
    template_name: str
    spawn_time: float
    last_seen: float
    entity_id: Optional[str] = None
    is_connected: bool = False
    respawn_count: int = 0


class AgentSpawner:
    """Handles automatic spawning and management of test agents"""

    def __init__(self, world_server, agent_config=None):
        self.world_server = world_server
        self.agent_config = agent_config
        self.spawned_agents: Dict[str, SpawnedAgentInfo] = {}
        self.spawn_queue: List[Dict[str, Any]] = []
        self.running = False

        # Spawning parameters
        self.max_agents = 50
        self.spawn_interval = 5.0  # seconds between spawn attempts
        self.respawn_delay = 30.0  # seconds before respawning disconnected agent
        self.agent_timeout = 60.0  # seconds before considering agent disconnected

        if agent_config:
            global_settings = agent_config.global_settings
            self.max_agents = global_settings.get('max_agents', 50)
            self.respawn_delay = global_settings.get('respawn_delay', 30.0)

        logger.info(f"AgentSpawner initialized (max_agents: {self.max_agents})")

    async def start(self):
        """Start the agent spawning system"""
        self.running = True
        logger.info("Agent spawning system started")

        # Start spawning loop
        asyncio.create_task(self._spawn_loop())
        asyncio.create_task(self._cleanup_loop())

    def stop(self):
        """Stop the agent spawning system"""
        self.running = False
        logger.info("Agent spawning system stopped")

    def queue_agent_spawn(self, template_name: str, name: str, count: int = 1, delay: float = 0):
        """Queue agents for spawning"""
        for i in range(count):
            agent_name = f"{name}_{i+1}" if count > 1 else name
            spawn_info = {
                'template_name': template_name,
                'name': agent_name,
                'spawn_time': time.time() + delay + (i * 1.0),  # Stagger spawning
                'priority': 1
            }
            self.spawn_queue.append(spawn_info)

        logger.info(f"Queued {count} agents of type '{template_name}' for spawning")

    def spawn_scenario(self, scenario_name: str):
        """Spawn agents for a specific scenario"""
        if not self.agent_config:
            logger.warning("No agent config available for scenario spawning")
            return

        scenario = self.agent_config.test_scenarios.get(scenario_name)
        if not scenario:
            logger.warning(f"Scenario '{scenario_name}' not found")
            return

        logger.info(f"Spawning scenario: {scenario_name}")

        for agent_group in scenario["agents"]:
            template_name = agent_group["template"]
            base_name = agent_group["name"]
            count = agent_group["count"]

            self.queue_agent_spawn(template_name, base_name, count)

    def spawn_balanced_mix(self, total_count: int):
        """Spawn a balanced mix of different agent types"""
        if not self.agent_config:
            logger.warning("No agent config available for balanced spawning")
            return

        templates = list(self.agent_config.agent_templates.keys())
        if not templates:
            logger.warning("No agent templates available")
            return

        # Distribute agents evenly across templates
        agents_per_template = max(1, total_count // len(templates))
        remaining = total_count % len(templates)

        for i, template_name in enumerate(templates):
            count = agents_per_template
            if i < remaining:
                count += 1

            self.queue_agent_spawn(template_name, template_name.title(), count)

        logger.info(f"Queued {total_count} agents across {len(templates)} templates")

    async def _spawn_loop(self):
        """Main spawning loop"""
        while self.running:
            try:
                current_time = time.time()

                # Process spawn queue
                ready_to_spawn = [
                    spawn for spawn in self.spawn_queue
                    if spawn['spawn_time'] <= current_time
                ]

                for spawn_info in ready_to_spawn:
                    if len(self.spawned_agents) >= self.max_agents:
                        logger.warning("Maximum agent limit reached, skipping spawn")
                        break

                    await self._spawn_agent(spawn_info)
                    self.spawn_queue.remove(spawn_info)

                # Check for disconnected agents that need respawning
                await self._check_respawns()

                await asyncio.sleep(self.spawn_interval)

            except Exception as e:
                logger.error(f"Error in spawn loop: {e}")
                await asyncio.sleep(5.0)

    async def _spawn_agent(self, spawn_info: Dict[str, Any]) -> bool:
        """Spawn a single agent"""
        try:
            template_name = spawn_info['template_name']
            agent_name = spawn_info['name']

            # Get template
            if not self.agent_config:
                logger.error("No agent config available")
                return False

            template = self.agent_config.agent_templates.get(template_name)
            if not template:
                logger.error(f"Agent template '{template_name}' not found")
                return False

            # Create agent process
            agent_process = await self._create_agent_process(agent_name, template)
            if not agent_process:
                logger.error(f"Failed to create agent process for {agent_name}")
                return False

            # Track spawned agent
            agent_info = SpawnedAgentInfo(
                agent_id=agent_name,
                name=agent_name,
                template_name=template_name,
                spawn_time=time.time(),
                last_seen=time.time(),
                is_connected=False
            )

            self.spawned_agents[agent_name] = agent_info
            logger.info(f"Spawned agent: {agent_name} ({template_name})")

            return True

        except Exception as e:
            logger.error(f"Error spawning agent {spawn_info.get('name', 'unknown')}: {e}")
            return False

    async def _create_agent_process(self, name: str, template: AgentTemplate) -> Optional[asyncio.subprocess.Process]:
        """Create an agent subprocess"""
        try:
            import sys
            import json

            # Create a temporary agent configuration
            agent_config = {
                'name': name,
                'class': template.class_name,
                'personality': template.personality,
                'behavior_params': template.behavior_params,
                'starting_equipment': template.starting_equipment,
                'starting_stats': template.starting_stats
            }

            # Create agent script content
            agent_script = f"""
import asyncio
import sys
import json
from client.core.agent_client import AgentClient, AgentConfig
from examples.simple_agent import SimpleExplorerAgent, CombatAgent

async def run_agent():
    config_data = {json.dumps(agent_config)}
    config = AgentConfig(
        name=config_data['name'],
        agent_class=config_data['class'],
        personality=config_data['personality'],
        behavior_params=config_data['behavior_params']
    )

    # Choose agent class based on template
    if config_data['class'].lower() in ['warrior', 'fighter']:
        agent = CombatAgent(config_data['name'])
    else:
        agent = SimpleExplorerAgent(config_data['name'])

    agent.config = config

    try:
        if await agent.connect():
            await agent.run()
    except Exception as e:
        print(f"Agent {{config_data['name']}} error: {{e}}")

if __name__ == "__main__":
    asyncio.run(run_agent())
"""

            # Start agent process
            process = await asyncio.create_subprocess_exec(
                sys.executable, '-c', agent_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            return process

        except Exception as e:
            logger.error(f"Error creating agent process: {e}")
            return None

    async def _check_respawns(self):
        """Check for agents that need respawning"""
        current_time = time.time()

        for agent_id, agent_info in list(self.spawned_agents.items()):
            # Check if agent hasn't been seen for too long
            if (current_time - agent_info.last_seen > self.agent_timeout and
                agent_info.is_connected):

                logger.info(f"Agent {agent_id} timed out, marking as disconnected")
                agent_info.is_connected = False

            # Check if disconnected agent should be respawned
            if (not agent_info.is_connected and
                current_time - agent_info.last_seen > self.respawn_delay):

                # Check global settings for auto-respawn
                if (self.agent_config and
                    self.agent_config.global_settings.get('auto_respawn', True)):

                    logger.info(f"Respawning agent {agent_id}")

                    # Queue for respawn
                    self.queue_agent_spawn(
                        agent_info.template_name,
                        f"{agent_info.name}_respawn_{agent_info.respawn_count}",
                        1, 0
                    )

                    agent_info.respawn_count += 1
                    agent_info.last_seen = current_time  # Reset timer

    async def _cleanup_loop(self):
        """Cleanup loop for old agent data"""
        while self.running:
            try:
                current_time = time.time()
                agents_to_remove = []

                for agent_id, agent_info in self.spawned_agents.items():
                    # Remove agents that have been disconnected for a very long time
                    if (not agent_info.is_connected and
                        current_time - agent_info.last_seen > 300):  # 5 minutes
                        agents_to_remove.append(agent_id)

                for agent_id in agents_to_remove:
                    logger.info(f"Cleaning up old agent data: {agent_id}")
                    del self.spawned_agents[agent_id]

                # Clean up spawn queue of old items
                current_time = time.time()
                self.spawn_queue = [
                    spawn for spawn in self.spawn_queue
                    if current_time - spawn['spawn_time'] < 60  # Remove items older than 1 minute
                ]

                await asyncio.sleep(60)  # Run cleanup every minute

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(30)

    def on_agent_connected(self, agent_id: str, entity_id: str):
        """Called when an agent connects to the server"""
        if agent_id in self.spawned_agents:
            agent_info = self.spawned_agents[agent_id]
            agent_info.is_connected = True
            agent_info.entity_id = entity_id
            agent_info.last_seen = time.time()
            logger.info(f"Agent {agent_id} connected with entity {entity_id}")

    def on_agent_disconnected(self, agent_id: str):
        """Called when an agent disconnects from the server"""
        if agent_id in self.spawned_agents:
            agent_info = self.spawned_agents[agent_id]
            agent_info.is_connected = False
            agent_info.last_seen = time.time()
            logger.info(f"Agent {agent_id} disconnected")

    def on_agent_heartbeat(self, agent_id: str):
        """Called when an agent sends a heartbeat"""
        if agent_id in self.spawned_agents:
            agent_info = self.spawned_agents[agent_id]
            agent_info.last_seen = time.time()

    def get_agent_stats(self) -> Dict[str, Any]:
        """Get statistics about spawned agents"""
        total_agents = len(self.spawned_agents)
        connected_agents = sum(1 for info in self.spawned_agents.values() if info.is_connected)
        queued_spawns = len(self.spawn_queue)

        template_counts = {}
        for info in self.spawned_agents.values():
            template_counts[info.template_name] = template_counts.get(info.template_name, 0) + 1

        return {
            'total_agents': total_agents,
            'connected_agents': connected_agents,
            'disconnected_agents': total_agents - connected_agents,
            'queued_spawns': queued_spawns,
            'template_distribution': template_counts,
            'max_agents': self.max_agents
        }