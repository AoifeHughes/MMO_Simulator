#!/usr/bin/env python3
import argparse
import asyncio
import logging
import signal
import sys
from typing import List, Optional

import pygame

from client.agent_types.explorer import ExplorerAgent
from client.client import GameClient
from scenarios.scenario_manager import ScenarioManager
from server.server import GameServer
from visualizer.renderer import Renderer
from world.map import WorldMap

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SimulatorApp:
    def __init__(
        self, mode: str = "both", visualize: bool = True, scenario: Optional[str] = None
    ):
        self.mode = mode
        self.visualize = visualize
        self.scenario_name = scenario
        self.server: Optional[GameServer] = None
        self.client: Optional[GameClient] = None
        self.renderer: Optional[Renderer] = None
        self.agent_clients: List[GameClient] = []
        self.running = False
        self.clock = pygame.time.Clock()
        self.scenario_manager = ScenarioManager()

    async def start_server(self):
        self.server = GameServer(100, 100)
        logger.info("Starting server...")

        # Load scenario if specified
        if self.scenario_name:
            scenario = await self.scenario_manager.load_scenario(
                self.scenario_name, self.server
            )
            if not scenario:
                logger.error(f"Failed to load scenario: {self.scenario_name}")
                self.running = False
                return None
        else:
            # Default agents if no scenario
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

    async def spawn_scenario_agents(self):
        """Spawn AI client agents for the scenario"""
        if not self.scenario_name:
            return

        scenario = self.scenario_manager.get_active_scenario()
        if not scenario:
            return

        await asyncio.sleep(1)  # Wait for server to be ready

        # Get agent configs from scenario
        for agent_data in self.server.world.get_all_agents():
            agent_type = agent_data.agent_type
            if agent_type in ["explorer", "npc", "enemy", "player", "pathfinding_test"]:
                client = GameClient()
                connected = await client.connect(agent_type=agent_type)
                if connected:
                    self.agent_clients.append(client)
                    logger.info(f"Connected AI client for {agent_type}")

    async def run_visualization(self):
        if not self.visualize:
            return

        # If no player client, create observation-only view
        if not self.client:
            self.renderer = Renderer()
            focus_agent_id = None
            # Pick first agent to focus on if available
            if self.server:
                agents = self.server.world.get_all_agents()
                if agents:
                    focus_agent_id = agents[0].id
        else:
            self.renderer = Renderer()
            focus_agent_id = self.client.agent_id

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    logger.info("Window closed - shutting down...")
                    return  # Exit immediately to trigger cleanup
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_d:
                        self.renderer.toggle_debug()
                    elif event.key == pygame.K_v:
                        self.renderer.toggle_vision_cones()
                    elif event.key == pygame.K_f:
                        self.renderer.toggle_follow_mode()
                    elif event.key == pygame.K_EQUALS:
                        self.renderer.handle_zoom(0.1)
                    elif event.key == pygame.K_MINUS:
                        self.renderer.handle_zoom(-0.1)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 2:  # Middle mouse button
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        self.renderer.start_panning(mouse_x, mouse_y)
                    elif event.button == 3:  # Right mouse button for panning
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        self.renderer.start_panning(mouse_x, mouse_y)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button in [2, 3]:  # Middle or right mouse button
                        self.renderer.stop_panning()
                elif event.type == pygame.MOUSEMOTION:
                    if self.renderer.is_panning:
                        mouse_x, mouse_y = pygame.mouse.get_pos()
                        self.renderer.update_panning(mouse_x, mouse_y)

            # Get world state from client or directly from server
            if self.client:
                world_state = self.client.get_world_state()
                agents = world_state.get("agents", [])
            else:
                # Observation mode - get state from server
                world_state = self.server.world.get_world_state()
                agents = world_state.get("agents", [])

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

    async def run_agent_clients_loop(self):
        """Update loop for AI agent clients"""
        while self.running:
            update_tasks = []
            for client in self.agent_clients:
                if client.connected:
                    update_tasks.append(client.update())

            if update_tasks:
                await asyncio.gather(*update_tasks, return_exceptions=True)

            await asyncio.sleep(0.016)

    async def run(self):
        self.running = True
        tasks = []

        # Setup signal handler for graceful shutdown
        def signal_handler():
            logger.info("Received interrupt signal - shutting down...")
            self.running = False
            # Cancel all tasks to force shutdown
            for task in tasks:
                if not task.done():
                    task.cancel()

        if sys.platform != "win32":
            for sig in [signal.SIGINT, signal.SIGTERM]:
                asyncio.get_event_loop().add_signal_handler(sig, signal_handler)

        try:
            if self.mode in ["server", "both", "scenario"]:
                server_task = await self.start_server()
                if server_task:
                    tasks.append(server_task)

                # Spawn scenario agents if in scenario mode
                if self.scenario_name:
                    await self.spawn_scenario_agents()
                    if self.agent_clients:
                        agent_task = asyncio.create_task(self.run_agent_clients_loop())
                        tasks.append(agent_task)

            # Only create player client if not in pure scenario mode
            if self.mode in ["client", "both"]:
                await self.start_client("player")
                if self.client:
                    client_task = asyncio.create_task(self.run_client_update_loop())
                    tasks.append(client_task)

            # Always show visualization if enabled
            if self.visualize:
                viz_task = asyncio.create_task(self.run_visualization())
                tasks.append(viz_task)

            if tasks:
                # Wait for tasks or until shutdown signal
                try:
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_EXCEPTION
                    )

                    # If we reach here due to shutdown, cancel remaining tasks
                    if not self.running:
                        for task in pending:
                            task.cancel()

                        # Wait briefly for cancellation
                        if pending:
                            await asyncio.wait(
                                pending, timeout=1.0, return_when=asyncio.ALL_COMPLETED
                            )

                except asyncio.CancelledError:
                    logger.info("Tasks cancelled")

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error in main run loop: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        self.running = False
        logger.info("Cleaning up...")

        # Disconnect agent clients
        for client in self.agent_clients:
            if client.connected:
                await client.disconnect()

        if self.client:
            await self.client.disconnect()

        if self.server:
            self.server.stop()

        if self.renderer:
            self.renderer.cleanup()

        logger.info("Cleanup complete")


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
    parser = argparse.ArgumentParser(description="MMO Simulator")
    parser.add_argument(
        "--mode",
        choices=["server", "client", "both", "demo", "scenario"],
        default="both",
        help="Run mode",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Scenario to run (e.g., test_explore, basic_combat, peaceful_village)",
    )
    parser.add_argument(
        "--list-scenarios", action="store_true", help="List available scenarios"
    )
    parser.add_argument("--no-viz", action="store_true", help="Disable visualization")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Server host (for client mode)"
    )

    args = parser.parse_args()

    if args.list_scenarios:
        manager = ScenarioManager()
        print("Available scenarios:")
        for name in manager.list_scenarios():
            scenario = manager.get_scenario(name)
            print(f"  {name}: {scenario.description}")
        return

    if args.mode == "demo":
        asyncio.run(demo_multiple_clients())
    else:
        # If scenario is specified, use scenario mode
        if args.scenario:
            mode = "scenario"
        else:
            mode = args.mode

        app = SimulatorApp(mode=mode, visualize=not args.no_viz, scenario=args.scenario)
        asyncio.run(app.run())


if __name__ == "__main__":
    main()
