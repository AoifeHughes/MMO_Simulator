#!/usr/bin/env python3
"""
Modified MMO Simulation Startup Script to use Improved Explorer
"""

import asyncio
import argparse
import sys
import os
import time
import subprocess
import signal
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

# Add current directory to path
sys.path.append('.')

from config.config_loader import ConfigLoader
from server.core.world_server import WorldServer
from client.core.agent_client import AgentClient, AgentConfig
from shared.math_utils import Vector2

logger = logging.getLogger(__name__)


@dataclass
class StartupConfig:
    """Configuration for the startup process"""
    config_dir: str = "config"
    scenario: Optional[str] = None
    agent_count: Optional[int] = None
    no_visual: bool = False
    server_only: bool = False
    agents_only: bool = False
    host: str = "127.0.0.1"
    port: int = 5555
    log_level: str = "INFO"
    auto_shutdown: Optional[int] = None  # Auto-shutdown after N seconds
    integrated_visual: bool = True  # Use integrated visualization by default
    use_improved: bool = True  # Use improved explorer by default


class MMOLauncher:
    """Main launcher for the MMO simulation"""

    def __init__(self, config: StartupConfig):
        self.config = config
        self.config_loader = ConfigLoader(config.config_dir)
        self.server_process: Optional[subprocess.Popen] = None
        self.server_task: Optional[asyncio.Task] = None  # For integrated server
        self.server_instance = None  # Direct server instance
        self.agent_tasks: List[asyncio.Task] = []
        self.visualization_process: Optional[subprocess.Popen] = None
        self.running = True

        # Load configurations
        if not self.config_loader.load_all_configs():
            logger.error("Failed to load configurations")
            sys.exit(1)

        # Validate configurations
        issues = self.config_loader.validate_configs()
        if issues:
            logger.warning("Configuration issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")

        logger.info("MMO Launcher initialized successfully")

    async def start(self):
        """Start the complete MMO simulation"""
        try:
            print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                    MMO SIMULATION LAUNCHER                   ║
    ║                  (IMPROVED EXPLORER VERSION)                 ║
    ║                                                              ║
    ║  🚀 Starting integrated MMO simulation...                   ║
    ║  📊 Loading configurations                                   ║
    ║  🔧 Initializing server and agents                          ║
    ║  🎮 Launching visualization                                  ║
    ╚══════════════════════════════════════════════════════════════╝
            """)

            # Step 1: Start server (unless agents-only mode)
            if not self.config.agents_only:
                await self._start_server()
                await asyncio.sleep(2)  # Give server time to start

            # Step 2: Start test agents (unless server-only mode)
            if not self.config.server_only:
                await self._start_agents()

            # Step 3: Start visualization (unless disabled)
            if not self.config.no_visual and not self.config.server_only:
                await self._start_visualization()

            # Step 4: Monitor and manage processes
            await self._run_main_loop()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            await self._cleanup()

    async def _start_server(self):
        """Start the MMO server"""
        logger.info("🚀 Starting MMO server...")

        # Check if server is already running
        if await self._check_server_running():
            logger.info("✅ Server already running, skipping startup")
            return

        try:
            # Always run server as subprocess for stability
            server_cmd = [sys.executable, 'run_server.py']

            logger.info("📊 Starting server (subprocess)")

            # Start server process
            self.server_process = subprocess.Popen(
                server_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd()
            )

            # Wait for server to be ready
            max_wait = 10  # seconds
            for _ in range(max_wait * 2):  # Check every 0.5 seconds
                if await self._check_server_running():
                    logger.info("✅ Server started successfully")
                    return
                await asyncio.sleep(0.5)

            logger.error("Server failed to start within timeout")

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise

    async def _check_server_running(self):
        """Check if server is running on configured port"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((self.config.host, self.config.port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _start_agents(self):
        """Start test agents based on configuration"""
        logger.info("🤖 Starting test agents with IMPROVED EXPLORER...")

        if not self.config_loader.agent_config:
            logger.warning("No agent configuration found, skipping agent startup")
            return

        # Determine which scenario to run
        scenario_name = self.config.scenario or "basic_exploration"
        scenario = self.config_loader.get_test_scenario(scenario_name)

        if not scenario:
            logger.warning(f"Scenario '{scenario_name}' not found, using default")
            scenario = {
                "agents": [
                    {"template": "warrior", "name": "Explorer", "count": 3},
                    {"template": "mage", "name": "Scout", "count": 2}
                ]
            }

        # Override agent count if specified
        if self.config.agent_count:
            total_requested = self.config.agent_count
            # All agents will use improved explorer
            scenario = {
                "agents": [
                    {"template": "explorer", "name": "Explorer", "count": total_requested}
                ]
            }

        # Create and start agents
        agent_tasks = []
        total_agents = 0

        for agent_group in scenario["agents"]:
            base_name = agent_group["name"]
            count = agent_group["count"]

            for i in range(count):
                agent_name = f"{base_name}_{i+1}"
                task = asyncio.create_task(
                    self._run_agent(agent_name)
                )
                agent_tasks.append(task)
                total_agents += 1

        self.agent_tasks = agent_tasks
        logger.info(f"✅ Started {total_agents} improved explorer agents")

        # Wait a moment for agents to connect
        await asyncio.sleep(1)

    async def _start_visualization(self):
        """Start the visualization monitor"""
        logger.info("🎮 Starting visualization monitor...")

        try:
            self.visualization_process = subprocess.Popen(
                [sys.executable, 'visualization/live_monitor.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd()
            )
            logger.info("✅ Visualization started")

        except Exception as e:
            logger.warning(f"⚠️  Failed to start visualization: {e}")

    async def _run_agent(self, name: str) -> None:
        """Run a single improved explorer agent"""
        try:
            # Import the improved explorer
            from examples.improved_explorer import ImprovedExplorerAgent

            # Create and run the agent
            agent = ImprovedExplorerAgent(name)

            # Connect and run
            if await agent.connect(self.config.host, self.config.port):
                logger.info(f"Agent {name} connected successfully")
                await agent.run()
            else:
                logger.error(f"Agent {name} failed to connect")

        except Exception as e:
            logger.error(f"Agent {name} error: {e}")

    async def _run_main_loop(self):
        """Main monitoring loop"""
        logger.info("🔄 MMO simulation running with IMPROVED EXPLORERS...")
        logger.info("Press Ctrl+C to stop")

        start_time = time.time()
        last_status_time = time.time()

        try:
            while self.running:
                current_time = time.time()

                # Check auto-shutdown
                if self.config.auto_shutdown:
                    elapsed = current_time - start_time
                    if elapsed >= self.config.auto_shutdown:
                        logger.info(f"Auto-shutdown after {elapsed:.0f} seconds")
                        break

                # Periodic status update
                if current_time - last_status_time >= 30:  # Every 30 seconds
                    alive_agents = sum(1 for task in self.agent_tasks if not task.done())
                    logger.info(f"📊 Status: {alive_agents} agents running")
                    last_status_time = current_time

                # Check if agents have all exited
                if self.agent_tasks:
                    if all(task.done() for task in self.agent_tasks):
                        logger.info("All agents have exited")
                        break

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("Main loop cancelled")

    async def _cleanup(self):
        """Clean up all processes and tasks"""
        logger.info("🧹 Cleaning up...")

        # Cancel agent tasks
        for task in self.agent_tasks:
            if not task.done():
                task.cancel()

        # Wait for cancellation
        if self.agent_tasks:
            await asyncio.gather(*self.agent_tasks, return_exceptions=True)

        # Stop server
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            logger.info("✅ Server stopped")

        # Stop visualization
        if self.visualization_process:
            try:
                self.visualization_process.terminate()
                self.visualization_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.visualization_process.kill()
            logger.info("✅ Visualization stopped")

        logger.info("✨ Cleanup complete")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Start the MMO simulation with improved explorers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python start_mmo_improved.py                  # Default: 5 improved explorers
    python start_mmo_improved.py --agents 10      # Start 10 improved explorers
    python start_mmo_improved.py --no-visual      # Start without visualization
    python start_mmo_improved.py --auto-shutdown 60  # Auto-shutdown after 60 seconds
        """
    )

    parser.add_argument(
        '--config-dir',
        default='config',
        help='Configuration directory path'
    )

    parser.add_argument(
        '--scenario',
        help='Test scenario to run (from agent_config.json)'
    )

    parser.add_argument(
        '--agents',
        type=int,
        dest='agent_count',
        help='Override number of agents to spawn'
    )

    parser.add_argument(
        '--no-visual',
        action='store_true',
        help='Skip starting visualization'
    )

    parser.add_argument(
        '--server-only',
        action='store_true',
        help='Start only the server (no agents or visualization)'
    )

    parser.add_argument(
        '--agents-only',
        action='store_true',
        help='Start only agents (server must be running separately)'
    )

    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Server host address'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=5555,
        help='Server port'
    )

    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )

    parser.add_argument(
        '--auto-shutdown',
        type=int,
        help='Automatically shutdown after N seconds'
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Create startup config
    config = StartupConfig(
        config_dir=args.config_dir,
        scenario=args.scenario,
        agent_count=args.agent_count,
        no_visual=args.no_visual,
        server_only=args.server_only,
        agents_only=args.agents_only,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        auto_shutdown=args.auto_shutdown
    )

    # Create and run launcher
    launcher = MMOLauncher(config)

    try:
        asyncio.run(launcher.start())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()