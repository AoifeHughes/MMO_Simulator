"""
Agent Test Harness with Behavioral Contracts

Provides a framework for testing agent behaviors through contracts
rather than implementation details. Focuses on observable outcomes
and behavioral invariants.
"""

import asyncio
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from client.agent import BaseAgent
from client.agent_types.enemy import EnemyAgent
from client.agent_types.explorer import ExplorerAgent
from client.agent_types.player import PlayerAgent
from server.world import ServerWorld


class BehaviorContract(Enum):
    """Predefined behavioral contracts for agent testing"""

    EVENTUALLY_MOVES = "eventually_moves"
    REACHES_TARGET = "reaches_target"
    AVOIDS_OBSTACLES = "avoids_obstacles"
    MAINTAINS_DISTANCE = "maintains_distance"
    RESPONDS_TO_STIMULUS = "responds_to_stimulus"
    CONSERVES_RESOURCES = "conserves_resources"
    FOLLOWS_ORDERS = "follows_orders"


@dataclass
class TestPosition:
    """Position data for test tracking"""

    x: float
    y: float
    timestamp: float

    def distance_to(self, other: "TestPosition") -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


@dataclass
class BehaviorExpectation:
    """Defines what behavior is expected from an agent"""

    contract: BehaviorContract
    timeout_seconds: float
    tolerance: float = 1.0
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class AgentTestHarness:
    """
    Test harness for agent behavior validation.

    Provides methods to:
    1. Set up agents in controlled environments
    2. Define behavioral expectations through contracts
    3. Monitor agent behavior over time
    4. Validate that contracts are satisfied
    """

    def __init__(self, world: ServerWorld, time_acceleration: float = 10.0):
        self.world = world
        self.time_acceleration = time_acceleration
        self.agents: Dict[str, BaseAgent] = {}
        self.position_history: Dict[str, List[TestPosition]] = {}
        self.start_time = time.time()
        self.current_test_time = 0.0

    def add_agent(
        self,
        agent_type: str,
        agent_id: str,
        x: float,
        y: float,
        behavior_config: Optional[Dict] = None,
    ) -> BaseAgent:
        """Add agent to test harness with optional behavior configuration"""
        # Create agent based on type
        if agent_type == "explorer":
            agent = ExplorerAgent(agent_id, x, y)
            if behavior_config and "exploration_mode" in behavior_config:
                agent.set_exploration_mode(behavior_config["exploration_mode"])
        elif agent_type == "player":
            agent = PlayerAgent(agent_id, x, y)
        elif agent_type == "enemy":
            agent = EnemyAgent(agent_id, x, y)
        else:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Set up agent for testing
        agent.set_world_bounds(self.world.world_map.width, self.world.world_map.height)
        agent.has_initial_map_data = True
        agent.use_behavior_tree = True

        # Initialize behavior tree if needed
        if hasattr(agent, "_initialize_behavior_tree"):
            if not getattr(agent, "behavior_tree_initialized", True):
                agent._initialize_behavior_tree()

        # Create test action manager that updates position directly
        agent.action_manager = TestActionManager(self.world, agent_id)

        self.agents[agent_id] = agent
        self.position_history[agent_id] = []

        # Spawn in server world (it will generate its own ID)
        server_agent_id = self.world.spawn_agent(agent_type, x, y)

        return agent

    def step_simulation(self, delta_time: float = 0.1) -> None:
        """Step the simulation forward by delta_time seconds"""
        self.current_test_time += delta_time

        # Update all agents
        for agent_id, agent in self.agents.items():
            # Update agent behavior
            agent.update(delta_time)

            # Record position
            position = TestPosition(agent.x, agent.y, self.current_test_time)
            self.position_history[agent_id].append(position)

    def run_for_duration(self, duration_seconds: float, step_size: float = 0.1) -> None:
        """Run simulation for specified duration"""
        end_time = self.current_test_time + duration_seconds
        while self.current_test_time < end_time:
            self.step_simulation(step_size)

    async def run_until_condition(
        self,
        condition: Callable[[], bool],
        max_duration: float = 30.0,
        step_size: float = 0.1,
    ) -> bool:
        """Run simulation until condition is met or timeout"""
        end_time = self.current_test_time + max_duration
        while self.current_test_time < end_time:
            self.step_simulation(step_size)
            if condition():
                return True
            await asyncio.sleep(0.001)  # Yield control
        return False

    def verify_contract(self, agent_id: str, expectation: BehaviorExpectation) -> bool:
        """Verify that an agent satisfies a behavioral contract"""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not found in harness")

        agent = self.agents[agent_id]
        positions = self.position_history[agent_id]

        contract = expectation.contract
        timeout = expectation.timeout_seconds
        tolerance = expectation.tolerance
        params = expectation.parameters

        if contract == BehaviorContract.EVENTUALLY_MOVES:
            return self._verify_eventually_moves(positions, timeout, tolerance)

        elif contract == BehaviorContract.REACHES_TARGET:
            target = params.get("target", (0, 0))
            return self._verify_reaches_target(positions, target, timeout, tolerance)

        elif contract == BehaviorContract.AVOIDS_OBSTACLES:
            obstacles = params.get("obstacles", [])
            return self._verify_avoids_obstacles(positions, obstacles, tolerance)

        elif contract == BehaviorContract.MAINTAINS_DISTANCE:
            other_agent_id = params.get("other_agent_id")
            min_distance = params.get("min_distance", 2.0)
            return self._verify_maintains_distance(
                agent_id, other_agent_id, min_distance
            )

        elif contract == BehaviorContract.RESPONDS_TO_STIMULUS:
            stimulus_time = params.get("stimulus_time", 0)
            response_window = params.get("response_window", 5.0)
            return self._verify_responds_to_stimulus(
                positions, stimulus_time, response_window
            )

        else:
            raise ValueError(f"Unknown contract: {contract}")

    def _verify_eventually_moves(
        self, positions: List[TestPosition], timeout: float, tolerance: float
    ) -> bool:
        """Verify agent eventually moves from starting position"""
        if len(positions) < 2:
            return False

        start_pos = positions[0]
        for pos in positions[1:]:
            if pos.timestamp > timeout:
                break
            if start_pos.distance_to(pos) > tolerance:
                return True
        return False

    def _verify_reaches_target(
        self,
        positions: List[TestPosition],
        target: Tuple[float, float],
        timeout: float,
        tolerance: float,
    ) -> bool:
        """Verify agent reaches target within timeout"""
        target_x, target_y = target
        for pos in positions:
            if pos.timestamp > timeout:
                break
            distance = math.sqrt((pos.x - target_x) ** 2 + (pos.y - target_y) ** 2)
            if distance <= tolerance:
                return True
        return False

    def _verify_avoids_obstacles(
        self,
        positions: List[TestPosition],
        obstacles: List[Tuple[float, float]],
        tolerance: float,
    ) -> bool:
        """Verify agent doesn't collide with obstacles"""
        for pos in positions:
            for obs_x, obs_y in obstacles:
                distance = math.sqrt((pos.x - obs_x) ** 2 + (pos.y - obs_y) ** 2)
                if distance < tolerance:
                    return False
        return True

    def _verify_maintains_distance(
        self, agent1_id: str, agent2_id: str, min_distance: float
    ) -> bool:
        """Verify two agents maintain minimum distance"""
        if agent2_id not in self.position_history:
            return False

        pos1_list = self.position_history[agent1_id]
        pos2_list = self.position_history[agent2_id]

        # Check positions at same timestamps
        for pos1 in pos1_list:
            # Find closest timestamp in agent2's history
            closest_pos2 = min(
                pos2_list, key=lambda p: abs(p.timestamp - pos1.timestamp)
            )
            if pos1.distance_to(closest_pos2) < min_distance:
                return False

        return True

    def _verify_responds_to_stimulus(
        self,
        positions: List[TestPosition],
        stimulus_time: float,
        response_window: float,
    ) -> bool:
        """Verify agent responds to stimulus within window"""
        # Find position before stimulus
        pre_stimulus_pos = None
        for pos in positions:
            if pos.timestamp >= stimulus_time:
                break
            pre_stimulus_pos = pos

        if not pre_stimulus_pos:
            return False

        # Check for movement after stimulus
        for pos in positions:
            if stimulus_time <= pos.timestamp <= stimulus_time + response_window:
                if pre_stimulus_pos.distance_to(pos) > 1.0:
                    return True

        return False

    def get_agent_path(self, agent_id: str) -> List[Tuple[float, float]]:
        """Get the path taken by an agent"""
        if agent_id not in self.position_history:
            return []
        return [(pos.x, pos.y) for pos in self.position_history[agent_id]]

    def get_total_distance_traveled(self, agent_id: str) -> float:
        """Calculate total distance traveled by agent"""
        positions = self.position_history.get(agent_id, [])
        if len(positions) < 2:
            return 0.0

        total_distance = 0.0
        for i in range(1, len(positions)):
            total_distance += positions[i - 1].distance_to(positions[i])

        return total_distance

    def get_agent_velocity_over_time(self, agent_id: str) -> List[Tuple[float, float]]:
        """Get agent velocity measurements over time"""
        positions = self.position_history.get(agent_id, [])
        if len(positions) < 2:
            return []

        velocities = []
        for i in range(1, len(positions)):
            dt = positions[i].timestamp - positions[i - 1].timestamp
            if dt > 0:
                distance = positions[i - 1].distance_to(positions[i])
                velocity = distance / dt
                velocities.append((positions[i].timestamp, velocity))

        return velocities

    def reset(self):
        """Reset harness for new test"""
        self.agents.clear()
        self.position_history.clear()
        self.current_test_time = 0.0


class TestActionManager:
    """Action manager that directly updates agent positions for testing"""

    def __init__(self, world: ServerWorld, agent_id: str):
        self.world = world
        self.agent_id = agent_id

    async def request_action(
        self,
        action_type,
        parameters: Dict[str, Any],
        priority=None,
        predict: bool = True,
    ) -> str:
        """Handle action requests by updating world state directly"""
        import uuid

        from shared.actions import ActionType

        action_id = str(uuid.uuid4())

        if action_type == ActionType.MOVE_TO:
            target_x = parameters.get("target_x")
            target_y = parameters.get("target_y")

            # Use world's movement validation
            if self.world.move_agent(self.agent_id, target_x, target_y, 0):
                # Success - position updated in world
                pass
            else:
                # Rejected by server - no position update
                pass

        return action_id

    def register_action_callback(self, action_type, callback):
        """Register callback (no-op for testing)"""
        pass


# Convenience functions for common test scenarios


def create_movement_test(
    world_builder, agent_type: str = "explorer"
) -> AgentTestHarness:
    """Create harness for testing basic movement behaviors"""
    world = world_builder.build()
    harness = AgentTestHarness(world)

    # Add agent at a spawn point if available
    if world_builder.agent_spawns:
        spawn = world_builder.agent_spawns[0]
        harness.add_agent(spawn[0], "test_agent", spawn[1], spawn[2])
    else:
        harness.add_agent(agent_type, "test_agent", 5.0, 5.0)

    return harness


def create_navigation_test(
    world_builder, start: Tuple[float, float], target: Tuple[float, float]
) -> AgentTestHarness:
    """Create harness for testing navigation from start to target"""
    world = world_builder.build()
    harness = AgentTestHarness(world)

    agent = harness.add_agent("explorer", "navigator", start[0], start[1])

    # Set target if agent supports it
    if hasattr(agent, "set_target"):
        agent.set_target(target[0], target[1])

    return harness


def create_multi_agent_test(
    world_builder, agents: List[Tuple[str, str, float, float]]
) -> AgentTestHarness:
    """Create harness for testing multiple agent interactions"""
    world = world_builder.build()
    harness = AgentTestHarness(world)

    for agent_type, agent_id, x, y in agents:
        harness.add_agent(agent_type, agent_id, x, y)

    return harness
