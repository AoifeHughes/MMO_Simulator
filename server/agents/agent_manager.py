"""
High-level agent management and coordination
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any

from .agent_spawner import AgentSpawner, SpawnedAgentInfo

logger = logging.getLogger(__name__)


class AgentManager:
    """High-level agent management system"""

    def __init__(self, world_server):
        self.world_server = world_server
        self.agent_spawner = AgentSpawner(world_server, world_server.agent_config)
        self.running = False

        # Agent performance tracking
        self.agent_metrics: Dict[str, Dict[str, Any]] = {}
        self.last_metrics_update = 0

        logger.info("AgentManager initialized")

    async def start(self):
        """Start the agent management system"""
        self.running = True
        await self.agent_spawner.start()

        # Start management tasks
        asyncio.create_task(self._metrics_loop())
        asyncio.create_task(self._balance_loop())

        logger.info("Agent management system started")

    def stop(self):
        """Stop the agent management system"""
        self.running = False
        self.agent_spawner.stop()
        logger.info("Agent management system stopped")

    def start_scenario(self, scenario_name: str):
        """Start a specific test scenario"""
        logger.info(f"Starting scenario: {scenario_name}")
        self.agent_spawner.spawn_scenario(scenario_name)

    def spawn_agents(self, template_name: str, count: int, base_name: str = None):
        """Spawn a specific number of agents of a given type"""
        if not base_name:
            base_name = template_name.title()

        self.agent_spawner.queue_agent_spawn(template_name, base_name, count)
        logger.info(f"Spawning {count} {template_name} agents")

    def spawn_balanced_mix(self, total_count: int):
        """Spawn a balanced mix of different agent types"""
        self.agent_spawner.spawn_balanced_mix(total_count)

    def get_agent_list(self) -> List[Dict[str, Any]]:
        """Get list of all managed agents"""
        agents = []
        for agent_id, agent_info in self.agent_spawner.spawned_agents.items():
            agent_data = {
                'id': agent_id,
                'name': agent_info.name,
                'template': agent_info.template_name,
                'connected': agent_info.is_connected,
                'entity_id': agent_info.entity_id,
                'spawn_time': agent_info.spawn_time,
                'last_seen': agent_info.last_seen,
                'respawn_count': agent_info.respawn_count
            }

            # Add metrics if available
            if agent_id in self.agent_metrics:
                agent_data['metrics'] = self.agent_metrics[agent_id]

            agents.append(agent_data)

        return agents

    def get_agent_stats(self) -> Dict[str, Any]:
        """Get comprehensive agent statistics"""
        spawner_stats = self.agent_spawner.get_agent_stats()

        # Add performance metrics
        total_actions = sum(
            metrics.get('total_actions', 0)
            for metrics in self.agent_metrics.values()
        )

        avg_apm = 0
        if self.agent_metrics:
            avg_apm = sum(
                metrics.get('actions_per_minute', 0)
                for metrics in self.agent_metrics.values()
            ) / len(self.agent_metrics)

        return {
            **spawner_stats,
            'total_actions_performed': total_actions,
            'average_actions_per_minute': avg_apm,
            'agents_with_metrics': len(self.agent_metrics)
        }

    def kick_agent(self, agent_id: str) -> bool:
        """Manually disconnect an agent"""
        if agent_id in self.agent_spawner.spawned_agents:
            # Mark as disconnected
            self.agent_spawner.on_agent_disconnected(agent_id)

            # Remove from server if connected
            if self.world_server.game_state.agents.get(agent_id):
                entity_id = self.world_server.game_state.agents[agent_id]
                self.world_server.remove_agent_entity(agent_id)

            logger.info(f"Kicked agent: {agent_id}")
            return True

        return False

    def set_agent_limit(self, max_agents: int):
        """Update the maximum number of agents"""
        self.agent_spawner.max_agents = max_agents
        logger.info(f"Agent limit set to {max_agents}")

    async def _metrics_loop(self):
        """Collect agent performance metrics"""
        while self.running:
            try:
                current_time = time.time()

                # Update metrics every 30 seconds
                if current_time - self.last_metrics_update >= 30:
                    await self._update_agent_metrics()
                    self.last_metrics_update = current_time

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
                await asyncio.sleep(30)

    async def _update_agent_metrics(self):
        """Update metrics for all agents"""
        # Get action statistics from validators
        if (hasattr(self.world_server, 'action_validator') and
            hasattr(self.world_server, 'movement_validator')):

            for agent_id in self.agent_spawner.spawned_agents:
                # Get action stats
                action_stats = self.world_server.action_validator.get_action_stats(agent_id)
                movement_stats = self.world_server.movement_validator.get_movement_stats(agent_id)

                # Combine metrics
                self.agent_metrics[agent_id] = {
                    **action_stats,
                    **movement_stats,
                    'last_update': time.time()
                }

    async def _balance_loop(self):
        """Monitor and balance agent population"""
        while self.running:
            try:
                stats = self.get_agent_stats()

                # Check if we need to spawn more agents for balance
                connected = stats['connected_agents']
                max_agents = stats['max_agents']

                # If we have very few connected agents, spawn some more
                if connected < max_agents * 0.3:  # Less than 30% of capacity
                    needed = min(5, max_agents - connected)  # Spawn up to 5 more
                    if needed > 0:
                        logger.info(f"Population low ({connected}/{max_agents}), spawning {needed} agents")
                        self.spawn_balanced_mix(needed)

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Error in balance loop: {e}")
                await asyncio.sleep(60)

    def on_agent_connected(self, agent_id: str, entity_id: str):
        """Handle agent connection"""
        self.agent_spawner.on_agent_connected(agent_id, entity_id)

    def on_agent_disconnected(self, agent_id: str):
        """Handle agent disconnection"""
        self.agent_spawner.on_agent_disconnected(agent_id)

    def on_agent_heartbeat(self, agent_id: str):
        """Handle agent heartbeat"""
        self.agent_spawner.on_agent_heartbeat(agent_id)

    def get_scenario_list(self) -> List[str]:
        """Get list of available test scenarios"""
        if not self.world_server.agent_config:
            return []

        return list(self.world_server.agent_config.test_scenarios.keys())

    def get_template_list(self) -> List[str]:
        """Get list of available agent templates"""
        if not self.world_server.agent_config:
            return []

        return list(self.world_server.agent_config.agent_templates.keys())