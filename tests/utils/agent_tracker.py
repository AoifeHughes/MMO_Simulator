import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class AgentSnapshot:
    """Single snapshot of agent state at a point in time"""

    timestamp: float
    agent_id: str
    agent_type: str
    x: float
    y: float
    rotation: float
    health: float
    state: str = "unknown"
    target: Optional[tuple] = None
    velocity: tuple = (0.0, 0.0)
    extra_data: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra_data is None:
            self.extra_data = {}


@dataclass
class AgentPath:
    """Track an agent's movement over time"""

    agent_id: str
    agent_type: str
    snapshots: List[AgentSnapshot]
    start_time: float
    end_time: Optional[float] = None

    def get_total_distance(self) -> float:
        """Calculate total distance traveled"""
        if len(self.snapshots) < 2:
            return 0.0

        total = 0.0
        for i in range(1, len(self.snapshots)):
            prev = self.snapshots[i - 1]
            curr = self.snapshots[i]
            dx = curr.x - prev.x
            dy = curr.y - prev.y
            total += (dx * dx + dy * dy) ** 0.5
        return total

    def get_speed_over_time(self) -> List[float]:
        """Get speed at each timestamp"""
        speeds = []
        for i in range(1, len(self.snapshots)):
            prev = self.snapshots[i - 1]
            curr = self.snapshots[i]
            dt = curr.timestamp - prev.timestamp
            if dt > 0:
                dx = curr.x - prev.x
                dy = curr.y - prev.y
                distance = (dx * dx + dy * dy) ** 0.5
                speed = distance / dt
                speeds.append(speed)
            else:
                speeds.append(0.0)
        return speeds

    def get_area_coverage(self, tile_size: float = 1.0) -> Set[tuple]:
        """Get unique tiles/areas visited"""
        tiles = set()
        for snapshot in self.snapshots:
            tile_x = int(snapshot.x / tile_size)
            tile_y = int(snapshot.y / tile_size)
            tiles.add((tile_x, tile_y))
        return tiles


class AgentTracker:
    """Tracks agent behavior and movement over time"""

    def __init__(self, server, tracking_interval: float = 0.1):
        self.server = server
        self.tracking_interval = tracking_interval
        self.tracking = False
        self.start_time = 0.0

        # Data storage
        self.agent_paths: Dict[str, AgentPath] = {}
        self.snapshots_by_time: List[List[AgentSnapshot]] = []
        self.state_transitions: Dict[str, List[tuple]] = defaultdict(list)

        # Tracking task
        self.tracking_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start tracking agents"""
        if self.tracking:
            return

        self.tracking = True
        self.start_time = time.time()
        self.tracking_task = asyncio.create_task(self._tracking_loop())
        logger.info("Started agent tracking")

    async def stop(self):
        """Stop tracking agents"""
        if not self.tracking:
            return

        self.tracking = False
        if self.tracking_task:
            self.tracking_task.cancel()
            try:
                await self.tracking_task
            except asyncio.CancelledError:
                pass

        # Finalize all paths
        end_time = time.time()
        for path in self.agent_paths.values():
            if path.end_time is None:
                path.end_time = end_time

        logger.info("Stopped agent tracking")

    async def _tracking_loop(self):
        """Main tracking loop"""
        try:
            while self.tracking:
                await self._capture_snapshot()
                await asyncio.sleep(self.tracking_interval)
        except asyncio.CancelledError:
            logger.info("Tracking loop cancelled")
        except Exception as e:
            logger.error(f"Error in tracking loop: {e}")

    async def _capture_snapshot(self):
        """Capture current state of all agents"""
        current_time = time.time()
        current_snapshots = []

        agents = self.server.world.get_all_agents()
        for agent_data in agents:
            snapshot = AgentSnapshot(
                timestamp=current_time,
                agent_id=agent_data.id,
                agent_type=agent_data.agent_type,
                x=agent_data.x,
                y=agent_data.y,
                rotation=agent_data.rotation,
                health=agent_data.health,
                velocity=(0.0, 0.0),  # Would need client data for actual velocity
                extra_data={},
            )

            current_snapshots.append(snapshot)

            # Add to agent path
            if agent_data.id not in self.agent_paths:
                self.agent_paths[agent_data.id] = AgentPath(
                    agent_id=agent_data.id,
                    agent_type=agent_data.agent_type,
                    snapshots=[],
                    start_time=current_time,
                )

            self.agent_paths[agent_data.id].snapshots.append(snapshot)

        self.snapshots_by_time.append(current_snapshots)

    def get_agent_path(self, agent_id: str) -> Optional[AgentPath]:
        """Get path data for specific agent"""
        return self.agent_paths.get(agent_id)

    def get_agents_by_type(self, agent_type: str) -> List[AgentPath]:
        """Get all agents of specific type"""
        return [
            path for path in self.agent_paths.values() if path.agent_type == agent_type
        ]

    def get_tracking_duration(self) -> float:
        """Get total tracking duration"""
        if not self.tracking and self.agent_paths:
            # Use end time from any path
            path = next(iter(self.agent_paths.values()))
            return (path.end_time or time.time()) - self.start_time
        return time.time() - self.start_time

    def get_summary_report(self) -> Dict[str, Any]:
        """Generate summary report of agent behavior"""
        duration = self.get_tracking_duration()

        report = {
            "tracking_duration": duration,
            "total_agents": len(self.agent_paths),
            "agents_by_type": defaultdict(int),
            "agent_stats": {},
        }

        for agent_id, path in self.agent_paths.items():
            agent_type = path.agent_type
            report["agents_by_type"][agent_type] += 1

            # Calculate stats for this agent
            total_distance = path.get_total_distance()
            speeds = path.get_speed_over_time()
            avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
            max_speed = max(speeds) if speeds else 0.0
            coverage = len(path.get_area_coverage())

            report["agent_stats"][agent_id] = {
                "type": agent_type,
                "total_distance": total_distance,
                "average_speed": avg_speed,
                "max_speed": max_speed,
                "area_coverage": coverage,
                "snapshots_count": len(path.snapshots),
            }

        return report

    def print_debug_info(self):
        """Print debug information about tracked agents"""
        report = self.get_summary_report()

        print(f"\n=== Agent Tracking Report ===")
        print(f"Duration: {report['tracking_duration']:.2f}s")
        print(f"Total Agents: {report['total_agents']}")

        print(f"\nAgents by Type:")
        for agent_type, count in report["agents_by_type"].items():
            print(f"  {agent_type}: {count}")

        print(f"\nAgent Details:")
        for agent_id, stats in report["agent_stats"].items():
            print(f"  {agent_id[:8]}... ({stats['type']}):")
            print(f"    Distance: {stats['total_distance']:.2f}")
            print(f"    Avg Speed: {stats['average_speed']:.2f}")
            print(f"    Max Speed: {stats['max_speed']:.2f}")
            print(f"    Coverage: {stats['area_coverage']} tiles")
            print(f"    Snapshots: {stats['snapshots_count']}")

    def assert_agent_moved(self, agent_id: str, min_distance: float = 1.0):
        """Assert that agent moved at least minimum distance"""
        path = self.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        distance = path.get_total_distance()
        assert (
            distance >= min_distance
        ), f"Agent {agent_id} moved {distance:.2f}, expected >= {min_distance}"

    def assert_agent_stayed_in_area(self, agent_id: str, center: tuple, radius: float):
        """Assert agent stayed within specified area"""
        path = self.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        for snapshot in path.snapshots:
            distance = (
                (snapshot.x - center[0]) ** 2 + (snapshot.y - center[1]) ** 2
            ) ** 0.5
            assert (
                distance <= radius
            ), f"Agent {agent_id} went {distance:.2f} from center {center}, max allowed: {radius}"

    def assert_agent_explored_area(self, agent_id: str, min_tiles: int):
        """Assert agent explored minimum number of unique tiles"""
        path = self.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        coverage = len(path.get_area_coverage())
        assert (
            coverage >= min_tiles
        ), f"Agent {agent_id} explored {coverage} tiles, expected >= {min_tiles}"
