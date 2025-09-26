#!/usr/bin/env python3
"""
Simplified MMO Simulator Launcher

This demonstrates the simplified architecture that:
- Preserves client-side behavior trees and decision making
- Eliminates sync issues through streamlined communication
- Reduces complexity while maintaining functionality
- Uses single TCP protocol with clear message patterns

The server remains authoritative for validation, but clients retain AI autonomy.
"""

import argparse
import asyncio
import logging
import signal
import sys
from typing import List, Optional

import pygame

from client.simplified_client import SimplifiedGameClient
from server.simple_server import SimpleGameServer
from visualizer.renderer import Renderer
from world.map import WorldMap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimplifiedSimulatorApp:
    """Simplified MMO simulator using the new architecture"""

    def __init__(self, mode: str = "both", visualize: bool = True,
                 num_agents: int = 5, timeout: Optional[int] = None):
        self.mode = mode
        self.visualize = visualize
        self.num_agents = num_agents
        self.timeout = timeout

        self.server: Optional[SimpleGameServer] = None
        self.clients: List[SimplifiedGameClient] = []
        self.renderer: Optional[Renderer] = None
        self.running = False
        self.clock = pygame.time.Clock()

    async def start_server(self):
        """Start the simplified server"""
        self.server = SimpleGameServer(world_width=100, world_height=100)
        logger.info("Starting simplified server...")

        # Spawn some initial agents for testing
        for i in range(self.num_agents):
            if i == 0:
                agent_type = "player"
            elif i < 3:
                agent_type = "explorer"
            else:
                agent_type = "npc"

            agent_id = self.server.world.spawn_agent(agent_type)
            logger.info(f"Spawned {agent_type} agent {agent_id[:8]}")

        # Start server in background
        server_task = asyncio.create_task(self.server.start())
        return server_task

    async def start_clients(self):
        """Start simplified AI clients"""
        if not self.server:
            return

        await asyncio.sleep(1.0)  # Wait for server to be ready

        # Get all agents from server
        all_agents = self.server.world.get_all_agents()

        for i, agent in enumerate(all_agents):
            client = SimplifiedGameClient()

            # Connect client to control this agent
            agent_type = agent.agent_type
            connected = await client.connect(agent_type=agent_type)

            if connected:
                self.clients.append(client)
                logger.info(f"Connected client {i} as {agent_type} agent {client.agent_id[:8]}")
            else:
                logger.error(f"Failed to connect client {i}")

    async def run_visualization(self):
        """Run the visualization system"""
        if not self.visualize:
            return

        self.renderer = Renderer()
        focus_agent_id = None

        # Focus on first client's agent if available
        if self.clients:
            focus_agent_id = self.clients[0].agent_id

        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    logger.info("Window closed - shutting down...")
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_d:
                        self.renderer.toggle_debug()
                    elif event.key == pygame.K_v:
                        self.renderer.toggle_vision_cones()

            # Get world state for visualization
            if self.clients:
                world_state = self.clients[0].get_world_state()
                agents_data = world_state.get("agents", [])
            else:
                agents_data = []

            # Create world map for renderer
            world_map = WorldMap(100, 100) if self.server else WorldMap(100, 100)

            # Render frame
            self.renderer.render_frame(world_map, agents_data, focus_agent_id)
            self.clock.tick(60)

            await asyncio.sleep(0.001)

    async def run_clients_loop(self):
        """Update loop for all AI clients"""
        while self.running:
            update_tasks = []

            for client in self.clients:
                if client.connected:
                    update_tasks.append(client.update())

            if update_tasks:
                await asyncio.gather(*update_tasks, return_exceptions=True)

            await asyncio.sleep(0.033)  # ~30 FPS

    async def run(self):
        """Main run method"""
        self.running = True
        tasks = []

        # Setup signal handler for graceful shutdown
        def signal_handler():
            logger.info("Received interrupt signal - shutting down...")
            self.running = False
            for task in tasks:
                if not task.done():
                    task.cancel()

        if sys.platform != "win32":
            for sig in [signal.SIGINT, signal.SIGTERM]:
                asyncio.get_event_loop().add_signal_handler(sig, signal_handler)

        try:
            # Start server
            if self.mode in ["server", "both"]:
                server_task = await self.start_server()
                if server_task:
                    tasks.append(server_task)

                # Start AI clients
                await self.start_clients()
                if self.clients:
                    client_task = asyncio.create_task(self.run_clients_loop())
                    tasks.append(client_task)

            # Start visualization
            if self.visualize:
                viz_task = asyncio.create_task(self.run_visualization())
                tasks.append(viz_task)

            # Add timeout if specified
            if self.timeout:
                timeout_task = asyncio.create_task(self._timeout_handler())
                tasks.append(timeout_task)
                logger.info(f"Timeout set for {self.timeout} seconds")

            if tasks:
                # Wait for tasks or shutdown
                try:
                    done, pending = await asyncio.wait(
                        tasks, return_when=asyncio.FIRST_COMPLETED
                    )

                    # Cancel remaining tasks on shutdown
                    if not self.running:
                        for task in pending:
                            task.cancel()

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
        """Cleanup resources"""
        self.running = False
        logger.info("Cleaning up simplified simulator...")

        # Disconnect clients
        for client in self.clients:
            if client.connected:
                await client.disconnect()

        # Stop server
        if self.server:
            await self.server.stop()

        # Cleanup renderer
        if self.renderer:
            self.renderer.cleanup()

        logger.info("Cleanup complete")

    async def _timeout_handler(self):
        """Handle timeout shutdown"""
        await asyncio.sleep(self.timeout)
        logger.info(f"Timeout reached ({self.timeout}s), shutting down...")
        self.running = False

    def print_stats(self):
        """Print statistics about the simplified system"""
        if self.server:
            server_stats = self.server.get_stats()
            logger.info(f"Server stats: {server_stats}")

        for i, client in enumerate(self.clients):
            client_stats = client.get_stats()
            logger.info(f"Client {i} stats: {client_stats}")


def main():
    parser = argparse.ArgumentParser(description="Simplified MMO Simulator")
    parser.add_argument(
        "--mode",
        choices=["server", "both"],
        default="both",
        help="Run mode (simplified - no pure client mode)"
    )
    parser.add_argument(
        "--agents",
        type=int,
        default=5,
        help="Number of AI agents to spawn"
    )
    parser.add_argument(
        "--no-viz",
        action="store_true",
        help="Disable visualization"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Automatic shutdown timeout in seconds"
    )

    args = parser.parse_args()

    # Create and run simplified simulator
    app = SimplifiedSimulatorApp(
        mode=args.mode,
        visualize=not args.no_viz,
        num_agents=args.agents,
        timeout=args.timeout
    )

    # Run the simplified system
    try:
        asyncio.run(app.run())
        app.print_stats()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()