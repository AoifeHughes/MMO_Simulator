#!/usr/bin/env python3
"""
Enhanced debugging script for analyzing agent behavior in combat scenarios.
This script provides detailed logging of agent decision-making, movement patterns,
and behavior tree execution to understand why combat behavior isn't working as expected.
"""

import asyncio
import sys
import time
import json
from server.server import GameServer
from client.client import GameClient
from scenarios.scenario_manager import ScenarioManager
import logging

# Setup comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)

# Enable detailed behavior tree logging
logger = logging.getLogger(__name__)

class BehaviorDebugger:
    """Comprehensive agent behavior analysis tool"""

    def __init__(self):
        self.server = None
        self.clients = []
        self.start_time = 0
        self.update_count = 0
        self.agent_history = {}
        self.behavior_log = []
        self.combat_events = []

    async def start_server(self):
        """Start the game server with duel scenario"""
        self.server = GameServer(100, 100)

        # Load the duel scenario
        manager = ScenarioManager()
        scenario = await manager.load_scenario("simple_duel", self.server)
        if not scenario:
            logger.error("Failed to load simple_duel scenario!")
            return False

        # Start server
        server_task = asyncio.create_task(self.server.start())
        await asyncio.sleep(1)  # Give server time to start

        return True

    async def connect_agents(self):
        """Connect AI clients with enhanced behavior logging"""
        # Get all spawned agents
        agents = self.server.world.get_all_agents()

        # Initialize agent history tracking
        for agent_data in agents:
            self.agent_history[agent_data.id] = {
                'positions': [],
                'decisions': [],
                'targets': [],
                'states': [],
                'combat_actions': []
            }

        for agent_data in agents:
            agent_type = agent_data.agent_type
            logger.info(f"🤖 Connecting AI client for {agent_type} agent {agent_data.id[:8]}")

            client = GameClient()
            connected = await client.connect(agent_type=agent_type)

            if connected:
                self.clients.append(client)
                logger.info(f"✅ Connected {agent_type} agent {agent_data.id[:8]}")

                # Enable detailed logging for this agent's behavior tree
                if hasattr(client.agent, 'behavior_tree'):
                    logger.info(f"🌳 Behavior tree initialized for {agent_type} agent")

            else:
                logger.error(f"❌ Failed to connect {agent_type} agent")

        return len(self.clients) == 2

    def log_agent_state(self, agent_data, timestamp):
        """Log detailed agent state for analysis"""
        agent_id = agent_data.id

        state_info = {
            'timestamp': timestamp,
            'position': (agent_data.x, agent_data.y),
            'rotation': agent_data.rotation,
            'velocity': (agent_data.velocity_x, agent_data.velocity_y),
            'health': agent_data.health
        }

        self.agent_history[agent_id]['positions'].append(state_info)

        # Calculate movement vector and speed
        if len(self.agent_history[agent_id]['positions']) > 1:
            prev = self.agent_history[agent_id]['positions'][-2]
            curr = state_info

            dx = curr['position'][0] - prev['position'][0]
            dy = curr['position'][1] - prev['position'][1]
            dt = curr['timestamp'] - prev['timestamp']

            if dt > 0:
                speed = ((dx**2 + dy**2)**0.5) / dt
                direction = (dx, dy)

                # Log significant movement changes
                if speed > 0.5:  # Moving
                    logger.debug(f"📍 Agent {agent_id[:8]} moving: speed={speed:.1f}, direction=({dx:.1f}, {dy:.1f})")

    def analyze_agent_interactions(self, agents):
        """Analyze interactions between agents"""
        if len(agents) != 2:
            return

        agent1, agent2 = agents

        # Calculate distance and relative positions
        dx = agent2.x - agent1.x
        dy = agent2.y - agent1.y
        distance = (dx**2 + dy**2)**0.5

        # Log combat-relevant events
        if distance < 3:
            event = {
                'timestamp': time.time(),
                'type': 'MELEE_RANGE',
                'distance': distance,
                'agent1_pos': (agent1.x, agent1.y),
                'agent2_pos': (agent2.x, agent2.y),
                'agent1_health': agent1.health,
                'agent2_health': agent2.health
            }
            self.combat_events.append(event)
            logger.info(f"⚔️ MELEE RANGE: Distance {distance:.1f} between {agent1.agent_type} and {agent2.agent_type}")

        elif distance < 8:
            logger.debug(f"🎯 APPROACH RANGE: Distance {distance:.1f}")
        elif distance < 15:
            logger.debug(f"👁️ VISION RANGE: Distance {distance:.1f}")

    async def monitor_detailed_behavior(self, duration: float = 30.0):
        """Enhanced behavior monitoring with detailed analysis"""
        self.start_time = time.time()
        end_time = self.start_time + duration

        logger.info("="*80)
        logger.info("🔬 DETAILED BEHAVIOR ANALYSIS STARTED")
        logger.info(f"📊 Duration: {duration} seconds")
        logger.info(f"🎯 Focus: Combat decision-making and movement patterns")
        logger.info("="*80)

        last_analysis_time = self.start_time
        analysis_interval = 1.0  # Analyze every second

        while time.time() < end_time:
            current_time = time.time()
            elapsed = current_time - self.start_time

            # Update all clients
            update_tasks = []
            for client in self.clients:
                if client.connected:
                    update_tasks.append(client.update())

            if update_tasks:
                await asyncio.gather(*update_tasks, return_exceptions=True)

            self.update_count += 1

            # Get current agent states
            agents = self.server.world.get_all_agents()

            # Log agent states
            for agent in agents:
                self.log_agent_state(agent, current_time)

            # Analyze interactions
            self.analyze_agent_interactions(agents)

            # Detailed analysis report
            if current_time - last_analysis_time >= analysis_interval:
                await self.detailed_status_report(elapsed, agents)
                last_analysis_time = current_time

            await asyncio.sleep(0.033)  # ~30 FPS update rate

        # Final comprehensive analysis
        logger.info("="*80)
        logger.info("🏁 BEHAVIOR ANALYSIS COMPLETE")
        await self.comprehensive_analysis_report()
        logger.info("="*80)

    async def detailed_status_report(self, elapsed: float, agents):
        """Detailed status report with behavior analysis"""
        logger.info(f"\n🔍 --- DETAILED ANALYSIS at {elapsed:.1f}s ---")

        for i, agent in enumerate(agents, 1):
            logger.info(f"\n🤖 Agent {i} ({agent.agent_type.upper()}):")
            logger.info(f"   ID: {agent.id[:8]}")
            logger.info(f"   Position: ({agent.x:.1f}, {agent.y:.1f})")
            logger.info(f"   Health: {agent.health:.0f}/100")
            logger.info(f"   Velocity: ({agent.velocity_x:.2f}, {agent.velocity_y:.2f})")
            logger.info(f"   Rotation: {agent.rotation:.1f}°")

            # Movement analysis
            history = self.agent_history.get(agent.id, {}).get('positions', [])
            if len(history) >= 2:
                prev_pos = history[-2]['position']
                curr_pos = history[-1]['position']

                movement_x = curr_pos[0] - prev_pos[0]
                movement_y = curr_pos[1] - prev_pos[1]
                movement_distance = (movement_x**2 + movement_y**2)**0.5

                if movement_distance > 0.01:
                    logger.info(f"   Movement: Δ({movement_x:.2f}, {movement_y:.2f}) distance={movement_distance:.2f}")
                else:
                    logger.info(f"   Movement: STATIONARY")

        # Inter-agent analysis
        if len(agents) == 2:
            agent1, agent2 = agents
            dx = agent2.x - agent1.x
            dy = agent2.y - agent1.y
            distance = (dx**2 + dy**2)**0.5

            logger.info(f"\n🎲 TACTICAL SITUATION:")
            logger.info(f"   Distance: {distance:.1f} units")
            logger.info(f"   Vector: ({dx:.1f}, {dy:.1f})")

            # Analyze if agents are approaching or retreating
            if len(self.agent_history[agent1.id]['positions']) >= 2:
                prev_distance = None
                for i in range(len(self.agent_history[agent1.id]['positions']) - 2, -1, -1):
                    if i < len(self.agent_history[agent2.id]['positions']):
                        prev_pos1 = self.agent_history[agent1.id]['positions'][i]['position']
                        prev_pos2 = self.agent_history[agent2.id]['positions'][i]['position']
                        prev_dx = prev_pos2[0] - prev_pos1[0]
                        prev_dy = prev_pos2[1] - prev_pos1[1]
                        prev_distance = (prev_dx**2 + prev_dy**2)**0.5
                        break

                if prev_distance:
                    if distance < prev_distance - 0.1:
                        logger.info(f"   Trend: 🔥 APPROACHING (was {prev_distance:.1f})")
                    elif distance > prev_distance + 0.1:
                        logger.info(f"   Trend: 🏃 RETREATING (was {prev_distance:.1f})")
                    else:
                        logger.info(f"   Trend: 🟡 STABLE")

            # Combat status
            if distance < 2:
                logger.info(f"   Status: ⚔️ MELEE COMBAT RANGE")
            elif distance < 5:
                logger.info(f"   Status: 🗡️ CLOSE COMBAT RANGE")
            elif distance < 10:
                logger.info(f"   Status: 🏹 RANGED COMBAT RANGE")
            elif distance < 15:
                logger.info(f"   Status: 👁️ DETECTION RANGE")
            else:
                logger.info(f"   Status: 🌫️ OUT OF RANGE")

    async def comprehensive_analysis_report(self):
        """Generate comprehensive behavior analysis report"""
        logger.info(f"\n📊 === COMPREHENSIVE BEHAVIOR ANALYSIS ===")

        agents = self.server.world.get_all_agents()

        # Overall statistics
        logger.info(f"🎯 Total Updates: {self.update_count}")
        logger.info(f"⏱️ Average FPS: {self.update_count / (time.time() - self.start_time):.1f}")
        logger.info(f"⚔️ Combat Events: {len(self.combat_events)}")

        # Agent movement analysis
        for agent in agents:
            history = self.agent_history.get(agent.id, {})
            positions = history.get('positions', [])

            if len(positions) >= 2:
                total_distance = 0
                max_speed = 0

                for i in range(1, len(positions)):
                    prev = positions[i-1]
                    curr = positions[i]

                    dx = curr['position'][0] - prev['position'][0]
                    dy = curr['position'][1] - prev['position'][1]
                    dt = curr['timestamp'] - prev['timestamp']

                    distance = (dx**2 + dy**2)**0.5
                    total_distance += distance

                    if dt > 0:
                        speed = distance / dt
                        max_speed = max(max_speed, speed)

                start_pos = positions[0]['position']
                end_pos = positions[-1]['position']
                displacement = ((end_pos[0] - start_pos[0])**2 + (end_pos[1] - start_pos[1])**2)**0.5

                logger.info(f"\n🏃 {agent.agent_type.upper()} Agent {agent.id[:8]}:")
                logger.info(f"   Total Distance Traveled: {total_distance:.1f} units")
                logger.info(f"   Net Displacement: {displacement:.1f} units")
                logger.info(f"   Max Speed: {max_speed:.1f} units/sec")
                logger.info(f"   Start Position: ({start_pos[0]:.1f}, {start_pos[1]:.1f})")
                logger.info(f"   End Position: ({end_pos[0]:.1f}, {end_pos[1]:.1f})")
                logger.info(f"   Final Health: {agent.health:.0f}/100")

        # Combat event analysis
        if self.combat_events:
            logger.info(f"\n⚔️ COMBAT EVENTS ANALYSIS:")
            melee_time = 0
            close_time = 0

            for event in self.combat_events:
                if event['distance'] < 2:
                    melee_time += 1
                elif event['distance'] < 5:
                    close_time += 1

            logger.info(f"   Melee Range Time: {melee_time} updates ({melee_time/self.update_count*100:.1f}%)")
            logger.info(f"   Close Combat Time: {close_time} updates ({close_time/self.update_count*100:.1f}%)")

            if self.combat_events:
                min_distance = min(event['distance'] for event in self.combat_events)
                logger.info(f"   Closest Approach: {min_distance:.1f} units")
        else:
            logger.info(f"\n⚔️ NO COMBAT EVENTS DETECTED")

    async def cleanup(self):
        """Clean up connections and server"""
        logger.info("\n🧹 Cleaning up...")

        for client in self.clients:
            if client.connected:
                await client.disconnect()

        if self.server:
            self.server.stop()

        logger.info("✅ Cleanup complete")

    async def run(self):
        """Main execution method"""
        try:
            # Start server
            logger.info("🚀 Starting duel server...")
            if not await self.start_server():
                return

            await asyncio.sleep(1)

            # Connect agents
            logger.info("🔗 Connecting agent clients...")
            if not await self.connect_agents():
                logger.error("❌ Failed to connect all agents!")
                return

            await asyncio.sleep(2)

            # Monitor behavior with detailed analysis
            await self.monitor_detailed_behavior(duration=25.0)

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
    debugger = BehaviorDebugger()
    asyncio.run(debugger.run())

if __name__ == "__main__":
    main()