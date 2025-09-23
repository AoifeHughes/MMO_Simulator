import asyncio
import logging
import time
from typing import TYPE_CHECKING

from shared.constants import SERVER_TICK_RATE

if TYPE_CHECKING:
    from server.server import GameServer
    from server.world import ServerWorld

logger = logging.getLogger(__name__)


class GameLoop:
    def __init__(self, world: "ServerWorld", server: "GameServer"):
        self.world = world
        self.server = server
        self.running = False
        self.tick_rate = SERVER_TICK_RATE
        self.tick_interval = 1.0 / self.tick_rate
        self.last_tick = time.time()
        self.tick_count = 0

    async def run(self):
        self.running = True
        logger.info(f"Game loop started at {self.tick_rate} ticks/second")

        while self.running and self.server.running:
            start_time = time.time()

            await self.tick()

            elapsed = time.time() - start_time
            sleep_time = max(0, self.tick_interval - elapsed)

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            else:
                logger.warning(
                    f"Tick took {elapsed:.3f}s, longer than interval {self.tick_interval:.3f}s"
                )

    async def tick(self):
        current_time = time.time()
        delta_time = current_time - self.last_tick
        self.last_tick = current_time
        self.tick_count += 1

        # Send standardized updates every 500ms (15 ticks at 30 TPS)
        if self.tick_count % 15 == 0:
            await self.server.send_client_updates()

    def stop(self):
        self.running = False
        logger.info("Game loop stopped")
