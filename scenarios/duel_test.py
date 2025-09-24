"""
Duel Test Scenario - Close combat testing scenario
Two agents spawn very close to each other for immediate combat.
Designed for testing death/respawn mechanics and tactical consistency.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List

from scenarios.base_scenario import BaseScenario
from world.terrain_generator import TerrainType

logger = logging.getLogger(__name__)


class DuelTestScenario(BaseScenario):
    """
    Close-quarters duel scenario for testing combat mechanics.

    Features:
    - Very small map (20x20)
    - Two agents spawn 5 units apart (guaranteed detection)
    - Close respawn points to maintain engagement
    - Automatic termination after 10 deaths
    - Detailed logging for analysis
    """

    def __init__(self):
        super().__init__(
            name="Duel Test",
            description="Close-quarters duel testing scenario with death counting",
            terrain_type=TerrainType.GRASSLAND,  # Open terrain for clear combat
            seed=200,  # Consistent small map
        )
        self.death_count = 0
        self.death_target = 10
        self.start_time = None
        self.death_log: List[Dict] = []

    async def setup(self, server) -> bool:
        """Setup the duel test scenario"""
        logger.info("Setting up duel test scenario")
        self.start_time = time.time()

        # Store server reference for later use
        self.server = server

        # Hook into death events
        self._hook_death_events(server)

        return True

    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn agents for the duel test"""
        if not self.server:
            return []

        # The world map is already created by the server
        map_width = self.server.world.world_map.width
        map_height = self.server.world.world_map.height

        logger.info(f"Using existing map size: {map_width}x{map_height}")

        # Clear any existing agents
        self.server.world.agents.clear()

        # Spawn positions - very close to each other in the center of the map
        center_x = map_width // 2
        center_y = map_height // 2
        player_spawn = (center_x - 2, center_y)   # Left of center
        enemy_spawn = (center_x + 2, center_y)    # Right of center, 4 units apart

        # Store spawn points for respawning
        self.spawn_points = {
            "player": player_spawn,
            "enemy": enemy_spawn
        }

        agent_configs = []

        # Spawn player
        logger.info(f"Spawning player at {player_spawn}")
        player_agent_id = self.server.world.spawn_agent(
            agent_type="player",
            x=player_spawn[0],
            y=player_spawn[1]
        )
        if player_agent_id:
            # Register agent so clients can take control
            self.server.agent_registry.register_agent(player_agent_id, "player", player_spawn[0], player_spawn[1])
            agent_configs.append({
                "type": "player",
                "position": player_spawn,
                "id": player_agent_id
            })

        # Spawn enemy
        logger.info(f"Spawning enemy at {enemy_spawn}")
        enemy_agent_id = self.server.world.spawn_agent(
            agent_type="enemy",
            x=enemy_spawn[0],
            y=enemy_spawn[1]
        )
        if enemy_agent_id:
            # Register agent so clients can take control
            self.server.agent_registry.register_agent(enemy_agent_id, "enemy", enemy_spawn[0], enemy_spawn[1])
            agent_configs.append({
                "type": "enemy",
                "position": enemy_spawn,
                "id": enemy_agent_id
            })

        logger.info("Duel test setup:")
        logger.info(f"  Map size: {map_width}x{map_height}")
        if player_agent_id:
            logger.info(f"  Player {player_agent_id[:8]} at {player_spawn}")
        if enemy_agent_id:
            logger.info(f"  Enemy {enemy_agent_id[:8]} at {enemy_spawn}")
        logger.info(f"  Distance: 4 units (guaranteed detection)")
        logger.info(f"  Target deaths: {self.death_target}")
        logger.info(f"  Expected behavior: Immediate combat engagement")

        return agent_configs

    def _hook_death_events(self, server):
        """Hook into server death events to count deaths"""
        original_process_death = server.process_agent_death

        async def death_counter(dead_agent_id, killer_id=None):
            # Call original death processing
            await original_process_death(dead_agent_id, killer_id)

            # Count and log the death
            self.death_count += 1
            elapsed = time.time() - self.start_time

            dead_agent = server.world.get_agent(dead_agent_id)
            killer_agent = server.world.get_agent(killer_id) if killer_id else None

            death_info = {
                "death_number": self.death_count,
                "elapsed_time": elapsed,
                "dead_agent_id": dead_agent_id[:8] if dead_agent_id else "unknown",
                "dead_agent_type": dead_agent.agent_type if dead_agent else "unknown",
                "killer_id": killer_id[:8] if killer_id else "none",
                "killer_type": killer_agent.agent_type if killer_agent else "none",
                "timestamp": time.time()
            }

            self.death_log.append(death_info)

            logger.info(f"[DUEL TEST] Death #{self.death_count}/{self.death_target}: "
                       f"{death_info['dead_agent_type']} {death_info['dead_agent_id']} "
                       f"killed by {death_info['killer_type']} {death_info['killer_id']} "
                       f"at {elapsed:.1f}s")

            # Check if we've reached the target
            if self.death_count >= self.death_target:
                logger.info(f"[DUEL TEST] Target of {self.death_target} deaths reached!")
                await self._finish_test(server)

            # Respawn close to maintain engagement
            await self._respawn_close(server, dead_agent_id)

        # Replace the server's death processing method
        server.process_agent_death = death_counter

    async def _respawn_close(self, server, dead_agent_id):
        """Respawn the dead agent close to the action"""
        dead_agent = server.world.get_agent(dead_agent_id)
        if not dead_agent:
            return

        agent_type = dead_agent.agent_type
        if agent_type in self.spawn_points:
            spawn_point = self.spawn_points[agent_type]

            # Respawn at the designated close spawn point
            dead_agent.x = spawn_point[0]
            dead_agent.y = spawn_point[1]
            dead_agent.health = getattr(dead_agent, 'max_health', 100)
            dead_agent.is_alive = True
            dead_agent.respawn_time = None

            logger.info(f"[DUEL TEST] Respawned {agent_type} {dead_agent_id[:8]} at {spawn_point}")

    async def _finish_test(self, server):
        """Finish the test and log results"""
        total_time = time.time() - self.start_time

        logger.info(f"[DUEL TEST] === TEST COMPLETED ===")
        logger.info(f"Total time: {total_time:.1f} seconds")
        logger.info(f"Total deaths: {self.death_count}")
        logger.info(f"Average time between deaths: {total_time/self.death_count:.1f}s")

        # Log death statistics
        player_deaths = sum(1 for d in self.death_log if d['dead_agent_type'] == 'player')
        enemy_deaths = sum(1 for d in self.death_log if d['dead_agent_type'] == 'enemy')

        logger.info(f"Player deaths: {player_deaths}")
        logger.info(f"Enemy deaths: {enemy_deaths}")

        # Stop the server after a brief delay to ensure logs are written
        def stop_server():
            server.stop()

        # Schedule server stop
        asyncio.get_event_loop().call_later(2.0, stop_server)

    def get_status(self) -> Dict:
        """Get current test status"""
        if self.start_time is None:
            return {"status": "not_started"}

        elapsed = time.time() - self.start_time
        return {
            "status": "running" if self.death_count < self.death_target else "completed",
            "deaths": self.death_count,
            "target": self.death_target,
            "progress": f"{self.death_count}/{self.death_target}",
            "elapsed_time": elapsed,
            "death_log": self.death_log
        }