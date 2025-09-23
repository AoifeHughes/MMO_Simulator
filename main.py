#!/usr/bin/env python3
import asyncio
import pygame
from typing import Optional
import sys
import argparse
from server.server import GameServer
from client.client import GameClient
from visualizer.renderer import Renderer
from world.map import WorldMap
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimulatorApp:
    def __init__(self, mode: str = "both", visualize: bool = True):
        self.mode = mode
        self.visualize = visualize
        self.server: Optional[GameServer] = None
        self.client: Optional[GameClient] = None
        self.renderer: Optional[Renderer] = None
        self.running = False
        self.clock = pygame.time.Clock()

    async def start_server(self):
        self.server = GameServer(100, 100)
        logger.info("Starting server...")

        for i in range(3):
            self.server.world.spawn_agent("npc")

        for i in range(2):
            self.server.world.spawn_agent("enemy")

        server_task = asyncio.create_task(self.server.start())
        return server_task

    async def start_client(self, agent_type: str = "player"):
        self.client = GameClient()
        await asyncio.sleep(0.5)

        logger.info(f"Connecting client as {agent_type}...")
        connected = await self.client.connect(agent_type=agent_type)

        if not connected:
            logger.error("Failed to connect client")
            return None

        return self.client

    async def run_visualization(self):
        if not self.visualize or not self.client:
            return

        self.renderer = Renderer()
        focus_agent_id = self.client.agent_id

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_d:
                        self.renderer.toggle_debug()
                    elif event.key == pygame.K_v:
                        self.renderer.toggle_vision_cones()
                    elif event.key == pygame.K_EQUALS:
                        self.renderer.handle_zoom(0.1)
                    elif event.key == pygame.K_MINUS:
                        self.renderer.handle_zoom(-0.1)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        world_x, world_y = self.renderer.screen_to_world(mouse_x, mouse_y)
                        await self.client.move_to(world_x, world_y)

            world_state = self.client.get_world_state()
            agents = world_state.get('agents', [])

            if self.server:
                world_map = self.server.world.world_map
            else:
                world_map = WorldMap(100, 100)

            self.renderer.render_frame(world_map, agents, focus_agent_id)
            self.clock.tick(60)

            await asyncio.sleep(0.001)

    async def run_client_update_loop(self):
        while self.running and self.client:
            await self.client.update()
            await asyncio.sleep(0.016)

    async def run(self):
        self.running = True
        tasks = []

        try:
            if self.mode in ["server", "both"]:
                server_task = await self.start_server()
                tasks.append(server_task)

            if self.mode in ["client", "both"]:
                await self.start_client("player")
                if self.client:
                    client_task = asyncio.create_task(self.run_client_update_loop())
                    tasks.append(client_task)

                    if self.visualize:
                        viz_task = asyncio.create_task(self.run_visualization())
                        tasks.append(viz_task)

            if tasks:
                await asyncio.gather(*tasks)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await self.cleanup()

    async def cleanup(self):
        self.running = False

        if self.client:
            await self.client.disconnect()

        if self.server:
            self.server.stop()

        if self.renderer:
            self.renderer.cleanup()

async def demo_multiple_clients():
    server = GameServer(100, 100)
    server_task = asyncio.create_task(server.start())

    await asyncio.sleep(1)

    clients = []
    for i in range(5):
        client = GameClient()
        agent_type = "player" if i == 0 else ("npc" if i < 3 else "enemy")
        connected = await client.connect(agent_type=agent_type)
        if connected:
            clients.append(client)
            logger.info(f"Client {i} connected as {agent_type}")

    try:
        update_tasks = []
        for client in clients:
            update_task = asyncio.create_task(update_client_loop(client))
            update_tasks.append(update_task)

        await asyncio.gather(server_task, *update_tasks)

    except KeyboardInterrupt:
        logger.info("Shutting down demo...")
    finally:
        for client in clients:
            await client.disconnect()
        server.stop()

async def update_client_loop(client: GameClient):
    while True:
        await client.update()
        await asyncio.sleep(0.016)

def main():
    parser = argparse.ArgumentParser(description='MMO Simulator')
    parser.add_argument('--mode', choices=['server', 'client', 'both', 'demo'],
                       default='both', help='Run mode')
    parser.add_argument('--no-viz', action='store_true',
                       help='Disable visualization')
    parser.add_argument('--host', default='127.0.0.1',
                       help='Server host (for client mode)')

    args = parser.parse_args()

    if args.mode == 'demo':
        asyncio.run(demo_multiple_clients())
    else:
        app = SimulatorApp(mode=args.mode, visualize=not args.no_viz)
        asyncio.run(app.run())

if __name__ == "__main__":
    main()