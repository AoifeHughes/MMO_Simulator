#!/usr/bin/env python3
"""
Movement debugging script to investigate flickering/jumping issues.
This script focuses specifically on movement synchronization between client and server.
"""

import asyncio
import sys
import time
import math
from server.server import GameServer
from client.client import GameClient
from scenarios.scenario_manager import ScenarioManager
import logging

# Setup movement-focused logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

class MovementDebugger:
    """Debug movement synchronization issues"""

    def __init__(self):
        self.server = None
        self.client = None
        self.start_time = 0
        self.movement_log = []

    async def start_server(self):
        """Start minimal server for movement testing"""
        self.server = GameServer(100, 100)

        # Load simple duel for 2 agents
        manager = ScenarioManager()
        scenario = await manager.load_scenario("simple_duel", self.server)
        if not scenario:
            logger.error("Failed to load simple_duel scenario!")
            return False

        # Start server
        server_task = asyncio.create_task(self.server.start())
        await asyncio.sleep(1)

        return True

    async def connect_single_agent(self):
        """Connect one AI agent for testing"""
        agents = self.server.world.get_all_agents()

        if agents:
            target_agent = agents[0]  # Take first agent
            logger.info(f"🤖 Connecting to {target_agent.agent_type} agent {target_agent.id[:8]}")

            self.client = GameClient()
            connected = await self.client.connect(agent_type=target_agent.agent_type)

            if connected:
                logger.info(f"✅ Connected to agent {self.client.agent_id[:8]}")
                return True
            else:
                logger.error("❌ Failed to connect agent")
                return False

        return False

    async def monitor_movement_sync(self, duration: float = 15.0):
        """Monitor movement synchronization between client and server"""
        self.start_time = time.time()
        end_time = self.start_time + duration

        logger.info("="*80)
        logger.info("🔍 MOVEMENT SYNCHRONIZATION DEBUG")
        logger.info(f"📊 Duration: {duration} seconds")
        logger.info("🎯 Focus: Client vs Server position synchronization")
        logger.info("="*80)

        last_report_time = self.start_time
        report_interval = 2.0

        while time.time() < end_time:
            current_time = time.time()
            elapsed = current_time - self.start_time

            # Update client
            if self.client and self.client.connected:
                await self.client.update()

            # Log movement state
            self.log_movement_state(current_time)

            # Periodic detailed report
            if current_time - last_report_time >= report_interval:
                await self.report_movement_status(elapsed)
                last_report_time = current_time

            await asyncio.sleep(0.033)  # ~30 FPS

        # Final analysis
        logger.info("="*80)
        logger.info("📊 MOVEMENT ANALYSIS COMPLETE")
        await self.analyze_movement_patterns()
        logger.info("="*80)

    def log_movement_state(self, timestamp):
        """Log current movement state for both client and server"""
        if not self.client or not self.client.agent:
            return

        agent_id = self.client.agent_id

        # Client state
        client_agent = self.client.agent
        client_pos = (client_agent.x, client_agent.y)
        client_vel = (client_agent.velocity_x, client_agent.velocity_y)

        # Server state
        server_agent = self.server.world.get_agent(agent_id)
        server_pos = (server_agent.x, server_agent.y) if server_agent else (0, 0)
        server_vel = (getattr(server_agent, 'velocity_x', 0), getattr(server_agent, 'velocity_y', 0)) if server_agent else (0, 0)

        # Calculate position difference
        pos_diff = math.sqrt((client_pos[0] - server_pos[0])**2 + (client_pos[1] - server_pos[1])**2)

        # Log significant desynchronization
        if pos_diff > 0.5:  # More than 0.5 units difference
            logger.warning(f"[DESYNC] Position diff: {pos_diff:.2f} units")
            logger.warning(f"  Client: pos{client_pos} vel{client_vel}")
            logger.warning(f"  Server: pos{server_pos} vel{server_vel}")

        # Store movement data
        self.movement_log.append({
            'timestamp': timestamp,
            'client_pos': client_pos,
            'client_vel': client_vel,
            'server_pos': server_pos,
            'server_vel': server_vel,
            'pos_diff': pos_diff
        })

    async def report_movement_status(self, elapsed: float):
        """Report current movement status"""
        if not self.client or not self.client.agent:
            return

        agent_id = self.client.agent_id
        client_agent = self.client.agent
        server_agent = self.server.world.get_agent(agent_id)

        logger.info(f"\n🔍 --- MOVEMENT STATUS at {elapsed:.1f}s ---")

        if server_agent:
            logger.info(f"📍 Client Position: ({client_agent.x:.2f}, {client_agent.y:.2f})")
            logger.info(f"📍 Server Position: ({server_agent.x:.2f}, {server_agent.y:.2f})")

            pos_diff = math.sqrt((client_agent.x - server_agent.x)**2 + (client_agent.y - server_agent.y)**2)
            logger.info(f"📏 Position Difference: {pos_diff:.3f} units")

            logger.info(f"🏃 Client Velocity: ({client_agent.velocity_x:.2f}, {client_agent.velocity_y:.2f})")
            logger.info(f"🏃 Server Velocity: ({getattr(server_agent, 'velocity_x', 0):.2f}, {getattr(server_agent, 'velocity_y', 0):.2f})")

            vel_diff = math.sqrt((client_agent.velocity_x - getattr(server_agent, 'velocity_x', 0))**2 +
                               (client_agent.velocity_y - getattr(server_agent, 'velocity_y', 0))**2)
            logger.info(f"🏃 Velocity Difference: {vel_diff:.3f} units/sec")

            # Movement status
            if pos_diff < 0.1 and vel_diff < 0.1:
                logger.info("✅ Client-Server SYNCHRONIZED")
            elif pos_diff > 1.0:
                logger.info("⚠️  SIGNIFICANT DESYNCHRONIZATION")
            else:
                logger.info("🟡 Minor desynchronization")

    async def analyze_movement_patterns(self):
        """Analyze recorded movement patterns"""
        if len(self.movement_log) < 10:
            logger.info("❌ Insufficient movement data for analysis")
            return

        logger.info(f"📊 Analyzed {len(self.movement_log)} movement samples")

        # Calculate desync statistics
        pos_diffs = [entry['pos_diff'] for entry in self.movement_log]

        avg_desync = sum(pos_diffs) / len(pos_diffs)
        max_desync = max(pos_diffs)
        significant_desyncs = len([d for d in pos_diffs if d > 0.5])

        logger.info(f"📏 Average Position Desync: {avg_desync:.3f} units")
        logger.info(f"📏 Maximum Position Desync: {max_desync:.3f} units")
        logger.info(f"⚠️  Significant Desyncs (>0.5u): {significant_desyncs}/{len(pos_diffs)} ({significant_desyncs/len(pos_diffs)*100:.1f}%)")

        # Movement pattern analysis
        moving_samples = [entry for entry in self.movement_log
                         if (entry['client_vel'][0]**2 + entry['client_vel'][1]**2) > 0.01]

        logger.info(f"🏃 Moving Samples: {len(moving_samples)}/{len(self.movement_log)} ({len(moving_samples)/len(self.movement_log)*100:.1f}%)")

        if avg_desync > 0.1:
            logger.warning("🚨 MOVEMENT SYNCHRONIZATION ISSUE DETECTED")
            logger.warning("   Possible causes:")
            logger.warning("   - Client prediction vs server authority conflicts")
            logger.warning("   - Collision detection differences")
            logger.warning("   - Network timing issues")
        else:
            logger.info("✅ Movement synchronization appears stable")

    async def cleanup(self):
        """Clean up connections"""
        logger.info("🧹 Cleaning up...")

        if self.client and self.client.connected:
            await self.client.disconnect()

        if self.server:
            self.server.stop()

        logger.info("✅ Cleanup complete")

    async def run(self):
        """Main execution method"""
        try:
            # Start server
            logger.info("🚀 Starting movement debug server...")
            if not await self.start_server():
                return

            await asyncio.sleep(1)

            # Connect single agent for testing
            logger.info("🔗 Connecting test agent...")
            if not await self.connect_single_agent():
                logger.error("❌ Failed to connect test agent!")
                return

            await asyncio.sleep(2)

            # Monitor movement synchronization
            await self.monitor_movement_sync(duration=15.0)

        except KeyboardInterrupt:
            logger.info("\n⏹️ Interrupted by user")
        except Exception as e:
            logger.error(f"💥 Error during execution: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.cleanup()

def main():
    """Entry point"""
    debugger = MovementDebugger()
    asyncio.run(debugger.run())

if __name__ == "__main__":
    main()