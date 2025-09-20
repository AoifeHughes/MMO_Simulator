import time
from typing import Optional
from dataclasses import dataclass, field
import threading
from queue import Queue, PriorityQueue
import logging

from src.world.world import World
from src.engine.request_manager import RequestManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GameConfig:
    target_fps: int = 60
    agent_update_interval: float = 0.5  # Update agents every 0.5 seconds
    request_resolution_interval: float = 0.1  # Resolve requests every 0.1 seconds
    max_pending_requests: int = 1000


class Game:
    def __init__(self, config: Optional[GameConfig] = None):
        self.config = config or GameConfig()
        self.world: Optional[World] = None
        self.request_manager: Optional[RequestManager] = None

        self.running = False
        self.paused = False
        self.current_tick = 0
        self.delta_time = 1.0 / self.config.target_fps

        self._last_agent_update = 0.0
        self._last_request_resolution = 0.0

        self._initialize()

    def _initialize(self):
        self.world = World()
        self.request_manager = RequestManager(self.world)
        logger.info(f"Game initialized with {self.config.target_fps} FPS target")

    def start(self):
        if self.running:
            logger.warning("Game is already running")
            return

        self.running = True
        logger.info("Starting game loop...")
        self._game_loop()

    def stop(self):
        logger.info("Stopping game...")
        self.running = False

    def pause(self):
        self.paused = True
        logger.info("Game paused")

    def resume(self):
        self.paused = False
        logger.info("Game resumed")

    def _game_loop(self):
        last_time = time.perf_counter()
        accumulator = 0.0

        while self.running:
            current_time = time.perf_counter()
            frame_time = current_time - last_time
            last_time = current_time

            if self.paused:
                time.sleep(0.01)
                continue

            accumulator += frame_time

            # Fixed timestep updates
            while accumulator >= self.delta_time:
                self._fixed_update(self.delta_time)
                accumulator -= self.delta_time
                self.current_tick += 1

            # Variable timestep updates
            self._update(frame_time)

            # Frame rate limiting
            elapsed = time.perf_counter() - current_time
            if elapsed < self.delta_time:
                time.sleep(self.delta_time - elapsed)

    def _fixed_update(self, delta_time: float):
        """Fixed timestep update (60 Hz)"""
        if self.world:
            self.world.fixed_update(delta_time)

    def _update(self, delta_time: float):
        """Variable timestep update for non-critical systems"""
        current_time = time.perf_counter()

        # Update agents at fixed intervals
        if current_time - self._last_agent_update >= self.config.agent_update_interval:
            self._update_agents(delta_time)
            self._last_agent_update = current_time

        # Resolve requests at fixed intervals
        if current_time - self._last_request_resolution >= self.config.request_resolution_interval:
            self._resolve_requests()
            self._last_request_resolution = current_time

    def _update_agents(self, delta_time: float):
        """Update all agents in the world"""
        if self.world:
            agents = self.world.get_all_agents()
            for agent in agents:
                agent.update(delta_time, self.world, self.request_manager)

    def _resolve_requests(self):
        """Process and resolve pending agent requests"""
        if self.request_manager:
            self.request_manager.process_requests()

    def get_stats(self) -> dict:
        """Get game statistics"""
        stats = {
            'current_tick': self.current_tick,
            'running': self.running,
            'paused': self.paused,
            'target_fps': self.config.target_fps,
        }

        if self.world:
            stats['world_stats'] = self.world.get_stats()

        if self.request_manager:
            stats['pending_requests'] = self.request_manager.get_pending_count()

        return stats