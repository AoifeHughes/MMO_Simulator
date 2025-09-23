import asyncio
import time
from typing import TYPE_CHECKING
from shared.constants import SERVER_TICK_RATE
import logging

if TYPE_CHECKING:
    from server.server import GameServer
    from server.world import ServerWorld

logger = logging.getLogger(__name__)

class GameLoop:
    def __init__(self, world: 'ServerWorld', server: 'GameServer'):
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
                logger.warning(f"Tick took {elapsed:.3f}s, longer than interval {self.tick_interval:.3f}s")

    async def tick(self):
        current_time = time.time()
        delta_time = current_time - self.last_tick
        self.last_tick = current_time
        self.tick_count += 1

        self.update_ai_agents(delta_time)

        if self.tick_count % 3 == 0:
            await self.server.broadcast_world_state()

        if self.tick_count % 2 == 0:
            for client_id in list(self.server.clients.keys()):
                await self.server.send_visible_entities(client_id)

    def update_ai_agents(self, delta_time: float):
        for agent in self.world.get_all_agents():
            if agent.agent_type in ["npc", "enemy"]:
                self.simulate_ai_movement(agent, delta_time)

    def simulate_ai_movement(self, agent, delta_time: float):
        import math
        import random

        if agent.agent_type == "npc":
            if random.random() < 0.01:
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(0.5, 2.0)
                new_x = agent.x + math.cos(angle) * distance
                new_y = agent.y + math.sin(angle) * distance

                if self.world.validate_position(new_x, new_y):
                    agent.x = new_x
                    agent.y = new_y
                    agent.rotation = math.degrees(angle)

        elif agent.agent_type == "enemy":
            players = [a for a in self.world.get_all_agents() if a.agent_type == "player"]
            if players:
                closest_player = min(players, key=lambda p:
                    math.sqrt((p.x - agent.x)**2 + (p.y - agent.y)**2))

                dx = closest_player.x - agent.x
                dy = closest_player.y - agent.y
                distance = math.sqrt(dx*dx + dy*dy)

                if distance < 20 and distance > 2:
                    move_speed = 3.0 * delta_time
                    new_x = agent.x + (dx / distance) * move_speed
                    new_y = agent.y + (dy / distance) * move_speed

                    if self.world.validate_position(new_x, new_y):
                        agent.x = new_x
                        agent.y = new_y
                        agent.rotation = math.degrees(math.atan2(dy, dx))

    def stop(self):
        self.running = False
        logger.info("Game loop stopped")