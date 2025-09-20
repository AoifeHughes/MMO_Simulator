#!/usr/bin/env python3
"""
Unified MMO Simulation Startup Script

This script provides a single entry point to start the complete MMO simulation:
- Starts the server with configuration
- Spawns configured test agents
- Launches the visualization monitor
- Handles graceful shutdown

Usage:
    python start_mmo.py                    # Start with default settings
    python start_mmo.py --scenario basic   # Run specific test scenario
    python start_mmo.py --agents 10        # Override agent count
    python start_mmo.py --no-visual        # Start without visualization
    python start_mmo.py --config-dir ./my_config  # Use custom config directory
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


class MMOLauncher:
    """Main launcher for the MMO simulation"""

    def __init__(self, config: StartupConfig):
        self.config = config
        self.config_loader = ConfigLoader(config.config_dir)
        self.server_process: Optional[subprocess.Popen] = None
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

            # Step 3: Start visualization (unless disabled or server-only)
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
            # Start server process
            self.server_process = subprocess.Popen(
                [sys.executable, 'run_server.py'],
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

            logger.error("❌ Server failed to start within timeout")
            raise RuntimeError("Server startup timeout")

        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            raise

    async def _start_agents(self):
        """Start test agents based on configuration"""
        logger.info("🤖 Starting test agents...")

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
                    {"template": "explorer", "name": "Explorer", "count": 2},
                    {"template": "warrior", "name": "Warrior", "count": 1}
                ]
            }

        # Override agent count if specified
        if self.config.agent_count:
            total_requested = self.config.agent_count
            # Distribute evenly across agent types
            agent_types = scenario["agents"]
            if agent_types:
                count_per_type = max(1, total_requested // len(agent_types))
                for agent_type in agent_types:
                    agent_type["count"] = count_per_type

        # Create and start agents
        agent_tasks = []
        total_agents = 0

        for agent_group in scenario["agents"]:
            template_name = agent_group["template"]
            base_name = agent_group["name"]
            count = agent_group["count"]

            template = self.config_loader.agent_config.agent_templates.get(template_name)
            if not template:
                logger.warning(f"Agent template '{template_name}' not found, skipping")
                continue

            for i in range(count):
                agent_name = f"{base_name}_{i+1}"
                task = asyncio.create_task(
                    self._run_agent(agent_name, template)
                )
                agent_tasks.append(task)
                total_agents += 1

        self.agent_tasks = agent_tasks
        logger.info(f"✅ Started {total_agents} agents")

        # Wait a moment for agents to connect
        await asyncio.sleep(1)

    async def _start_visualization(self):
        """Start the visualization monitor"""
        logger.info("🎮 Starting visualization...")

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

    async def _run_agent(self, name: str, template) -> None:
        """Run a single agent"""
        try:
            # Create agent config from template
            agent_config = AgentConfig(
                name=name,
                agent_class=template.class_name,
                personality=template.personality,
                behavior_params=template.behavior_params
            )

            # Create agent client
            from examples.simple_agent import SimpleExplorerAgent, CombatAgent

            # Choose agent class based on template
            if template.class_name.lower() in ['warrior', 'fighter']:
                agent = CombatAgent(name)
            else:
                agent = SimpleExplorerAgent(name)

            # Override config
            agent.config = agent_config

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
        logger.info("🔄 MMO simulation running...")
        logger.info("Press Ctrl+C to stop")

        start_time = time.time()
        last_status_time = time.time()

        try:
            while self.running:
                current_time = time.time()

                # Print status update every 30 seconds
                if current_time - last_status_time >= 30:
                    await self._print_status(current_time - start_time)
                    last_status_time = current_time

                # Check for auto-shutdown
                if (self.config.auto_shutdown and
                    current_time - start_time >= self.config.auto_shutdown):
                    logger.info(f"Auto-shutdown after {self.config.auto_shutdown} seconds")
                    break

                # Check if server process died
                if (self.server_process and
                    self.server_process.poll() is not None):
                    logger.error("Server process died unexpectedly")
                    break

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Shutdown requested by user")

        logger.info("📤 Exiting main loop, starting cleanup...")

    async def _print_status(self, uptime: float):
        """Print simulation status"""
        # Check server status
        server_status = "✅ Running" if await self._check_server_running() else "❌ Down"

        # Count active agents
        active_agents = len([task for task in self.agent_tasks if not task.done()])

        # Print status
        logger.info("=" * 60)
        logger.info("MMO SIMULATION STATUS")
        logger.info("=" * 60)
        logger.info(f"Uptime: {uptime:.1f} seconds")
        logger.info(f"Server: {server_status}")
        logger.info(f"Active Agents: {active_agents}")
        logger.info(f"Visualization: {'✅ Running' if self.visualization_process else '❌ Not started'}")
        logger.info("=" * 60)

    async def _check_server_running(self) -> bool:
        """Check if server is responding"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"http://{self.config.host}:8080/status"
                async with session.get(url, timeout=2.0) as response:
                    return response.status == 200
        except Exception:
            return False

    async def _cleanup(self):
        """Clean up all processes"""
        logger.info("🧹 Cleaning up...")

        # Cancel agent tasks
        for task in self.agent_tasks:
            if not task.done():
                task.cancel()

        # Wait for agent tasks to complete
        if self.agent_tasks:
            await asyncio.gather(*self.agent_tasks, return_exceptions=True)

        # Stop visualization
        if self.visualization_process:
            try:
                self.visualization_process.terminate()
                self.visualization_process.wait(timeout=5)
                logger.info("✅ Visualization stopped")
            except Exception as e:
                logger.warning(f"⚠️  Error stopping visualization: {e}")
                try:
                    self.visualization_process.kill()
                except Exception:
                    pass

        # Stop server
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=10)
                logger.info("✅ Server stopped")
            except Exception as e:
                logger.warning(f"⚠️  Error stopping server: {e}")
                try:
                    self.server_process.kill()
                except Exception:
                    pass

        logger.info("🏁 Cleanup complete")


def parse_arguments() -> StartupConfig:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Unified MMO Simulation Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_mmo.py                           # Start with defaults
  python start_mmo.py --scenario combat_test    # Run combat scenario
  python start_mmo.py --agents 20               # Start with 20 agents
  python start_mmo.py --no-visual               # No visualization
  python start_mmo.py --server-only             # Server only
  python start_mmo.py --auto-shutdown 300       # Auto-stop after 5 minutes
        """
    )

    parser.add_argument('--config-dir', default='config',
                       help='Configuration directory (default: config)')
    parser.add_argument('--scenario',
                       help='Test scenario to run (see agent_config.json)')
    parser.add_argument('--agents', type=int,
                       help='Override total number of agents to spawn')
    parser.add_argument('--no-visual', action='store_true',
                       help='Disable visualization')
    parser.add_argument('--server-only', action='store_true',
                       help='Start server only (no agents or visualization)')
    parser.add_argument('--agents-only', action='store_true',
                       help='Start agents only (assume server is running)')
    parser.add_argument('--host', default='127.0.0.1',
                       help='Server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=5555,
                       help='Server port (default: 5555)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    parser.add_argument('--auto-shutdown', type=int,
                       help='Auto-shutdown after N seconds')

    args = parser.parse_args()

    return StartupConfig(
        config_dir=args.config_dir,
        scenario=args.scenario,
        agent_count=args.agents,
        no_visual=args.no_visual,
        server_only=args.server_only,
        agents_only=args.agents_only,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        auto_shutdown=args.auto_shutdown
    )


def setup_logging(level: str):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Reduce noise from libraries
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('pygame').setLevel(logging.WARNING)


async def main():
    """Main entry point"""
    config = parse_arguments()
    setup_logging(config.log_level)

    # Create launcher first so we can reference it in signal handler
    launcher = MMOLauncher(config)

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        launcher.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start launcher
    await launcher.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete!")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)