#!/usr/bin/env python3
"""
Advanced Debugging System for MMO Simulator Agent Behavior

This system tracks agent movement, actions, and resource-seeking behavior
to identify position jumping and pathfinding issues.
"""

import logging
import time
import json
import sqlite3
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


@dataclass
class PositionSnapshot:
    """Single position measurement"""
    agent_id: str
    timestamp: float
    x: float
    y: float
    action_type: Optional[str]
    distance_from_previous: float = 0.0
    is_jump: bool = False  # Position change > threshold without movement


@dataclass
class ActionAttempt:
    """Action attempt with position context"""
    agent_id: str
    timestamp: float
    action_type: str
    target_x: Optional[float]
    target_y: Optional[float]
    agent_x: float
    agent_y: float
    distance_to_target: Optional[float]
    success: bool
    error_message: Optional[str] = None


@dataclass
class ResourceSeekingEvent:
    """Resource discovery and seeking behavior"""
    agent_id: str
    timestamp: float
    event_type: str  # 'discovered', 'seeking', 'reached', 'lost'
    resource_type: str  # 'water', 'wood', 'fire'
    resource_pos: Tuple[int, int]
    agent_pos: Tuple[float, float]
    distance: float
    behavior_tree_node: Optional[str] = None


class AgentDebugTracker:
    """Tracks individual agent debugging data"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.positions: List[PositionSnapshot] = []
        self.actions: List[ActionAttempt] = []
        self.resource_events: List[ResourceSeekingEvent] = []

        # Thresholds for detecting issues
        self.position_jump_threshold = 2.0  # Distance indicating teleportation
        self.max_history = 1000  # Keep last 1000 entries

        # State tracking
        self.last_position: Optional[Tuple[float, float]] = None
        self.last_position_time: Optional[float] = None

    def add_position(self, x: float, y: float, action_type: Optional[str] = None):
        """Record agent position"""
        timestamp = time.time()

        distance_from_previous = 0.0
        is_jump = False

        if self.last_position:
            dx = x - self.last_position[0]
            dy = y - self.last_position[1]
            distance_from_previous = (dx * dx + dy * dy) ** 0.5

            # Detect position jumps (large distance changes without time for movement)
            time_delta = timestamp - (self.last_position_time or timestamp)
            if time_delta < 0.5 and distance_from_previous > self.position_jump_threshold:
                is_jump = True
                logger.warning(f"🚨 POSITION JUMP detected for {self.agent_id[:8]}: "
                             f"moved {distance_from_previous:.2f} units in {time_delta:.2f}s "
                             f"from ({self.last_position[0]:.2f}, {self.last_position[1]:.2f}) "
                             f"to ({x:.2f}, {y:.2f}) during {action_type or 'unknown action'}")

        snapshot = PositionSnapshot(
            agent_id=self.agent_id,
            timestamp=timestamp,
            x=x, y=y,
            action_type=action_type,
            distance_from_previous=distance_from_previous,
            is_jump=is_jump
        )

        self.positions.append(snapshot)
        if len(self.positions) > self.max_history:
            self.positions.pop(0)

        self.last_position = (x, y)
        self.last_position_time = timestamp

    def add_action_attempt(self, action_type: str, target_pos: Optional[Tuple[float, float]],
                          agent_pos: Tuple[float, float], success: bool,
                          error_message: Optional[str] = None):
        """Record action attempt"""
        target_x, target_y = target_pos if target_pos else (None, None)
        distance_to_target = None

        if target_pos:
            dx = target_pos[0] - agent_pos[0]
            dy = target_pos[1] - agent_pos[1]
            distance_to_target = (dx * dx + dy * dy) ** 0.5

        attempt = ActionAttempt(
            agent_id=self.agent_id,
            timestamp=time.time(),
            action_type=action_type,
            target_x=target_x, target_y=target_y,
            agent_x=agent_pos[0], agent_y=agent_pos[1],
            distance_to_target=distance_to_target,
            success=success,
            error_message=error_message
        )

        self.actions.append(attempt)
        if len(self.actions) > self.max_history:
            self.actions.pop(0)

        # Log failed actions with distance issues
        if not success and distance_to_target and distance_to_target > 1.5:
            logger.warning(f"🚨 ACTION DISTANCE ISSUE: {self.agent_id[:8]} {action_type} failed, "
                         f"distance to target: {distance_to_target:.2f} > 1.5 limit")

    def add_resource_event(self, event_type: str, resource_type: str,
                          resource_pos: Tuple[int, int], agent_pos: Tuple[float, float],
                          behavior_node: Optional[str] = None):
        """Record resource-related events"""
        dx = resource_pos[0] - agent_pos[0]
        dy = resource_pos[1] - agent_pos[1]
        distance = (dx * dx + dy * dy) ** 0.5

        event = ResourceSeekingEvent(
            agent_id=self.agent_id,
            timestamp=time.time(),
            event_type=event_type,
            resource_type=resource_type,
            resource_pos=resource_pos,
            agent_pos=agent_pos,
            distance=distance,
            behavior_tree_node=behavior_node
        )

        self.resource_events.append(event)
        if len(self.resource_events) > self.max_history:
            self.resource_events.pop(0)

        # Log when agents discover resources but don't immediately head to them
        if event_type == 'discovered' and distance > 5.0:
            logger.info(f"🎯 RESOURCE DISCOVERY: {self.agent_id[:8]} found {resource_type} "
                       f"at {resource_pos} but is {distance:.1f} units away")

    def get_position_jumps(self) -> List[PositionSnapshot]:
        """Get all detected position jumps"""
        return [p for p in self.positions if p.is_jump]

    def get_failed_actions_by_distance(self) -> List[ActionAttempt]:
        """Get actions that failed due to distance issues"""
        return [a for a in self.actions
                if not a.success and a.distance_to_target and a.distance_to_target > 1.5]

    def get_resource_seeking_inefficiency(self) -> List[ResourceSeekingEvent]:
        """Get cases where agents discovered resources but didn't immediately pursue"""
        inefficient = []
        for event in self.resource_events:
            if event.event_type == 'discovered' and event.distance > 3.0:
                # Check if agent sought this resource within reasonable time
                seek_found = any(e.event_type == 'seeking' and
                               e.resource_pos == event.resource_pos and
                               e.timestamp - event.timestamp < 10.0
                               for e in self.resource_events)
                if not seek_found:
                    inefficient.append(event)
        return inefficient


class MMOSimulatorDebugger:
    """Main debugging coordinator"""

    def __init__(self, db_path: str = "debug_data.db"):
        self.agents: Dict[str, AgentDebugTracker] = {}
        self.db_path = db_path
        self.lock = threading.Lock()

        # Initialize database
        self._init_database()

        # Setup logging
        self._setup_debug_logging()

    def _init_database(self):
        """Initialize SQLite database for debug data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Position tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                agent_id TEXT,
                timestamp REAL,
                x REAL,
                y REAL,
                action_type TEXT,
                distance_from_previous REAL,
                is_jump BOOLEAN
            )
        ''')

        # Action attempts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS actions (
                agent_id TEXT,
                timestamp REAL,
                action_type TEXT,
                target_x REAL,
                target_y REAL,
                agent_x REAL,
                agent_y REAL,
                distance_to_target REAL,
                success BOOLEAN,
                error_message TEXT
            )
        ''')

        # Resource events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resource_events (
                agent_id TEXT,
                timestamp REAL,
                event_type TEXT,
                resource_type TEXT,
                resource_x INTEGER,
                resource_y INTEGER,
                agent_x REAL,
                agent_y REAL,
                distance REAL,
                behavior_tree_node TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def _setup_debug_logging(self):
        """Setup dedicated debug logging"""
        debug_logger = logging.getLogger('mmo_debug')
        debug_logger.setLevel(logging.DEBUG)

        handler = logging.FileHandler('mmo_debug.log')
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        debug_logger.addHandler(handler)

    def get_or_create_agent_tracker(self, agent_id: str) -> AgentDebugTracker:
        """Get or create tracker for agent"""
        with self.lock:
            if agent_id not in self.agents:
                self.agents[agent_id] = AgentDebugTracker(agent_id)
            return self.agents[agent_id]

    def track_position(self, agent_id: str, x: float, y: float, action_type: Optional[str] = None):
        """Track agent position"""
        tracker = self.get_or_create_agent_tracker(agent_id)
        tracker.add_position(x, y, action_type)

        # Save to database
        self._save_position_to_db(tracker.positions[-1])

    def track_action_attempt(self, agent_id: str, action_type: str,
                           target_pos: Optional[Tuple[float, float]],
                           agent_pos: Tuple[float, float], success: bool,
                           error_message: Optional[str] = None):
        """Track action attempt"""
        tracker = self.get_or_create_agent_tracker(agent_id)
        tracker.add_action_attempt(action_type, target_pos, agent_pos, success, error_message)

        # Save to database
        self._save_action_to_db(tracker.actions[-1])

    def track_resource_event(self, agent_id: str, event_type: str, resource_type: str,
                           resource_pos: Tuple[int, int], agent_pos: Tuple[float, float],
                           behavior_node: Optional[str] = None):
        """Track resource-related event"""
        tracker = self.get_or_create_agent_tracker(agent_id)
        tracker.add_resource_event(event_type, resource_type, resource_pos, agent_pos, behavior_node)

        # Save to database
        self._save_resource_event_to_db(tracker.resource_events[-1])

    def _save_position_to_db(self, position: PositionSnapshot):
        """Save position data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO positions VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (position.agent_id, position.timestamp, position.x, position.y,
              position.action_type, position.distance_from_previous, position.is_jump))

        conn.commit()
        conn.close()

    def _save_action_to_db(self, action: ActionAttempt):
        """Save action data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (action.agent_id, action.timestamp, action.action_type,
              action.target_x, action.target_y, action.agent_x, action.agent_y,
              action.distance_to_target, action.success, action.error_message))

        conn.commit()
        conn.close()

    def _save_resource_event_to_db(self, event: ResourceSeekingEvent):
        """Save resource event to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO resource_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (event.agent_id, event.timestamp, event.event_type, event.resource_type,
              event.resource_pos[0], event.resource_pos[1],
              event.agent_pos[0], event.agent_pos[1], event.distance, event.behavior_tree_node))

        conn.commit()
        conn.close()

    def generate_debug_report(self) -> str:
        """Generate comprehensive debug report"""
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("MMO SIMULATOR DEBUG REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Agents tracked: {len(self.agents)}")
        report_lines.append("")

        for agent_id, tracker in self.agents.items():
            report_lines.append(f"AGENT: {agent_id[:8]}")
            report_lines.append("-" * 40)

            # Position jumps
            jumps = tracker.get_position_jumps()
            report_lines.append(f"Position jumps detected: {len(jumps)}")
            for jump in jumps[-5:]:  # Show last 5
                report_lines.append(f"  {jump.timestamp:.2f}: Jumped {jump.distance_from_previous:.2f} units "
                                  f"to ({jump.x:.2f}, {jump.y:.2f}) during {jump.action_type}")

            # Distance failures
            distance_failures = tracker.get_failed_actions_by_distance()
            report_lines.append(f"Distance-related action failures: {len(distance_failures)}")
            for failure in distance_failures[-3:]:  # Show last 3
                report_lines.append(f"  {failure.action_type} failed: distance {failure.distance_to_target:.2f}")

            # Resource seeking inefficiency
            inefficient = tracker.get_resource_seeking_inefficiency()
            report_lines.append(f"Inefficient resource seeking: {len(inefficient)}")
            for event in inefficient[-3:]:  # Show last 3
                report_lines.append(f"  Found {event.resource_type} at distance {event.distance:.1f} "
                                  f"but didn't pursue immediately")

            report_lines.append("")

        return "\n".join(report_lines)

    def save_debug_report(self, filename: str = None):
        """Save debug report to file"""
        if filename is None:
            filename = f"debug_report_{int(time.time())}.txt"

        report = self.generate_debug_report()

        with open(filename, 'w') as f:
            f.write(report)

        logger.info(f"Debug report saved to {filename}")
        return filename


# Global debug instance
global_debugger = MMOSimulatorDebugger()


def get_debugger() -> MMOSimulatorDebugger:
    """Get the global debugger instance"""
    return global_debugger


# Convenience functions for easy integration
def track_agent_position(agent_id: str, x: float, y: float, action_type: Optional[str] = None):
    """Track agent position - convenience function"""
    global_debugger.track_position(agent_id, x, y, action_type)


def track_agent_action(agent_id: str, action_type: str, target_pos: Optional[Tuple[float, float]],
                      agent_pos: Tuple[float, float], success: bool, error_message: Optional[str] = None):
    """Track agent action attempt - convenience function"""
    global_debugger.track_action_attempt(agent_id, action_type, target_pos, agent_pos, success, error_message)


def track_resource_event(agent_id: str, event_type: str, resource_type: str,
                        resource_pos: Tuple[int, int], agent_pos: Tuple[float, float],
                        behavior_node: Optional[str] = None):
    """Track resource event - convenience function"""
    global_debugger.track_resource_event(agent_id, event_type, resource_type, resource_pos, agent_pos, behavior_node)


def generate_debug_report() -> str:
    """Generate debug report - convenience function"""
    return global_debugger.generate_debug_report()


def save_debug_report(filename: str = None) -> str:
    """Save debug report - convenience function"""
    return global_debugger.save_debug_report(filename)


if __name__ == "__main__":
    # Test the debugging system
    debugger = MMOSimulatorDebugger("test_debug.db")

    # Simulate some debug events
    debugger.track_position("agent_123", 10.0, 10.0, "fishing")
    debugger.track_position("agent_123", 15.5, 10.2, "fishing")  # Large jump

    debugger.track_action_attempt("agent_123", "fish", (16.0, 10.0), (10.0, 10.0), False, "Too far from water")

    debugger.track_resource_event("agent_123", "discovered", "water", (20, 15), (10.0, 10.0))

    print(debugger.generate_debug_report())