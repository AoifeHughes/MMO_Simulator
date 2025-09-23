import math
from typing import Any, Dict, List, Optional, Tuple

from tests.utils.agent_tracker import AgentPath, AgentTracker
from tests.utils.metrics import BehaviorMetrics


class AgentAssertions:
    """Custom assertions for agent behavior testing"""

    @staticmethod
    def assert_agent_moved(
        tracker: AgentTracker, agent_id: str, min_distance: float = 1.0
    ):
        """Assert that agent moved at least minimum distance"""
        path = tracker.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        distance = path.get_total_distance()
        assert (
            distance >= min_distance
        ), f"Agent {agent_id} moved only {distance:.2f}, expected >= {min_distance}"

    @staticmethod
    def assert_agent_stayed_in_area(
        tracker: AgentTracker, agent_id: str, center: Tuple[float, float], radius: float
    ):
        """Assert agent stayed within specified area"""
        path = tracker.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        violations = []
        for snapshot in path.snapshots:
            distance = math.sqrt(
                (snapshot.x - center[0]) ** 2 + (snapshot.y - center[1]) ** 2
            )
            if distance > radius:
                violations.append((snapshot.timestamp, distance))

        assert len(violations) == 0, (
            f"Agent {agent_id} left allowed area {len(violations)} times. "
            f"Max distance: {max(v[1] for v in violations):.2f}, allowed: {radius}"
        )

    @staticmethod
    def assert_agent_explored_area(
        tracker: AgentTracker, agent_id: str, min_tiles: int
    ):
        """Assert agent explored minimum number of unique tiles"""
        path = tracker.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        coverage = len(path.get_area_coverage())
        assert (
            coverage >= min_tiles
        ), f"Agent {agent_id} explored only {coverage} tiles, expected >= {min_tiles}"

    @staticmethod
    def assert_exploration_efficiency(
        metrics: BehaviorMetrics, agent_id: str, min_efficiency: float = 0.1
    ):
        """Assert exploration efficiency is above threshold"""
        if agent_id not in metrics.movement_patterns:
            raise AssertionError(f"No movement data for agent {agent_id}")

        pattern = metrics.movement_patterns[agent_id]
        efficiency = pattern.get_exploration_efficiency()

        assert (
            efficiency >= min_efficiency
        ), f"Agent {agent_id} exploration efficiency {efficiency:.3f} < {min_efficiency}"

    @staticmethod
    def assert_movement_smoothness(
        metrics: BehaviorMetrics, agent_id: str, max_variance: float = 10.0
    ):
        """Assert agent movement is reasonably smooth (low velocity variance)"""
        if agent_id not in metrics.movement_patterns:
            raise AssertionError(f"No movement data for agent {agent_id}")

        pattern = metrics.movement_patterns[agent_id]
        variance = pattern.get_velocity_variance()

        assert (
            variance <= max_variance
        ), f"Agent {agent_id} movement too erratic: variance {variance:.2f} > {max_variance}"

    @staticmethod
    def assert_state_transitions(
        metrics: BehaviorMetrics,
        agent_id: str,
        expected_states: List[str],
        min_transitions: int = 1,
    ):
        """Assert agent went through expected state transitions"""
        if agent_id not in metrics.state_transitions:
            raise AssertionError(f"No state transition data for agent {agent_id}")

        transitions = metrics.state_transitions[agent_id]
        states_seen = set(state for _, state in transitions)

        missing_states = set(expected_states) - states_seen
        assert (
            len(missing_states) == 0
        ), f"Agent {agent_id} never entered expected states: {missing_states}"

        assert (
            len(transitions) >= min_transitions
        ), f"Agent {agent_id} had only {len(transitions)} transitions, expected >= {min_transitions}"

    @staticmethod
    def assert_interaction_occurred(
        metrics: BehaviorMetrics, agent1_id: str, agent2_id: str, interaction_type: str
    ):
        """Assert specific interaction occurred between agents"""
        interactions = [
            event
            for event in metrics.interaction_events
            if (
                (event["agent1"] == agent1_id and event["agent2"] == agent2_id)
                or (event["agent1"] == agent2_id and event["agent2"] == agent1_id)
            )
            and event["type"] == interaction_type
        ]

        assert (
            len(interactions) > 0
        ), f"No {interaction_type} interaction found between {agent1_id} and {agent2_id}"

    @staticmethod
    def assert_performance_acceptable(
        metrics: BehaviorMetrics,
        min_tick_rate: float = 20.0,
        max_latency: float = 100.0,
    ):
        """Assert simulation performance is acceptable"""
        avg_tick_rate = metrics.performance.get_average_tick_rate()
        avg_latency = metrics.performance.get_average_latency()

        assert (
            avg_tick_rate >= min_tick_rate
        ), f"Average tick rate {avg_tick_rate:.1f} < {min_tick_rate}"

        assert (
            avg_latency <= max_latency
        ), f"Average latency {avg_latency:.1f}ms > {max_latency}ms"


class ExplorerAssertions:
    """Specific assertions for explorer agent behavior"""

    @staticmethod
    def assert_spiral_pattern(
        metrics: BehaviorMetrics, agent_id: str, tolerance: float = 2.0
    ):
        """Assert agent follows spiral exploration pattern"""
        if agent_id not in metrics.movement_patterns:
            raise AssertionError(f"No movement data for agent {agent_id}")

        pattern = metrics.movement_patterns[agent_id]
        positions = pattern.positions

        if len(positions) < 10:
            raise AssertionError(
                f"Not enough position data for spiral analysis: {len(positions)}"
            )

        # For spiral pattern, distance from start should generally increase
        start_pos = positions[0]
        distances = []
        for pos in positions:
            dist = math.sqrt(
                (pos[0] - start_pos[0]) ** 2 + (pos[1] - start_pos[1]) ** 2
            )
            distances.append(dist)

        # Check that max distance is significantly larger than initial
        max_distance = max(distances)
        initial_distance = distances[0]

        assert (
            max_distance > initial_distance + tolerance
        ), f"Spiral pattern not detected: max distance {max_distance:.2f} vs start {initial_distance:.2f}"

    @staticmethod
    def assert_random_exploration(
        metrics: BehaviorMetrics, agent_id: str, min_directional_entropy: float = 0.7
    ):
        """Assert agent explores randomly (not biased to one direction)"""
        if agent_id not in metrics.movement_patterns:
            raise AssertionError(f"No movement data for agent {agent_id}")

        pattern = metrics.movement_patterns[agent_id]
        directional_bias = pattern.get_directional_bias()

        # Calculate entropy of directional movement
        total = sum(directional_bias.values())
        if total == 0:
            raise AssertionError(
                f"Agent {agent_id} didn't move enough for directional analysis"
            )

        # Normalize and calculate entropy
        probabilities = [v / total for v in directional_bias.values() if v > 0]
        entropy = -sum(p * math.log2(p) for p in probabilities if p > 0)
        max_entropy = math.log2(len([v for v in directional_bias.values() if v > 0]))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0

        assert (
            normalized_entropy >= min_directional_entropy
        ), f"Agent {agent_id} movement too biased: entropy {normalized_entropy:.2f} < {min_directional_entropy}"

    @staticmethod
    def assert_no_overlap_with_other_explorers(
        tracker: AgentTracker, agent_id: str, min_separation: float = 5.0
    ):
        """Assert explorer maintains distance from other explorers"""
        target_path = tracker.get_agent_path(agent_id)
        assert target_path is not None, f"No tracking data for agent {agent_id}"

        other_explorers = [
            path
            for path in tracker.agent_paths.values()
            if path.agent_type == "explorer" and path.agent_id != agent_id
        ]

        violations = []
        for snapshot in target_path.snapshots:
            for other_path in other_explorers:
                # Find closest snapshot in time from other agent
                closest_snapshot = min(
                    other_path.snapshots,
                    key=lambda s: abs(s.timestamp - snapshot.timestamp),
                    default=None,
                )
                if (
                    closest_snapshot
                    and abs(closest_snapshot.timestamp - snapshot.timestamp) < 1.0
                ):
                    distance = math.sqrt(
                        (snapshot.x - closest_snapshot.x) ** 2
                        + (snapshot.y - closest_snapshot.y) ** 2
                    )
                    if distance < min_separation:
                        violations.append(
                            (snapshot.timestamp, distance, other_path.agent_id)
                        )

        assert len(violations) == 0, (
            f"Agent {agent_id} got too close to other explorers {len(violations)} times. "
            f"Min distance: {min(v[1] for v in violations):.2f}, required: {min_separation}"
        )


class NPCAssertions:
    """Specific assertions for NPC agent behavior"""

    @staticmethod
    def assert_wandering_behavior(
        tracker: AgentTracker, agent_id: str, max_wander_radius: float = 20.0
    ):
        """Assert NPC wanders within expected radius"""
        path = tracker.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        if not path.snapshots:
            raise AssertionError(f"No snapshots for NPC {agent_id}")

        home_pos = (path.snapshots[0].x, path.snapshots[0].y)
        AgentAssertions.assert_agent_stayed_in_area(
            tracker, agent_id, home_pos, max_wander_radius
        )

    @staticmethod
    def assert_idle_wandering_cycle(
        metrics: BehaviorMetrics,
        agent_id: str,
        expected_cycle_time: Tuple[float, float] = (2.0, 10.0),
    ):
        """Assert NPC cycles between idle and wandering states"""
        if agent_id not in metrics.state_transitions:
            raise AssertionError(f"No state transition data for NPC {agent_id}")

        transitions = metrics.state_transitions[agent_id]
        states = [state for _, state in transitions]

        # Should see both idle and wandering states
        assert "idle" in states, f"NPC {agent_id} never entered idle state"
        assert "wandering" in states, f"NPC {agent_id} never entered wandering state"

        # Analyze cycle timing
        idle_durations = []
        wander_durations = []
        current_state = None
        state_start_time = None

        for timestamp, state in transitions:
            if current_state != state:
                if current_state is not None and state_start_time is not None:
                    duration = timestamp - state_start_time
                    if current_state == "idle":
                        idle_durations.append(duration)
                    elif current_state == "wandering":
                        wander_durations.append(duration)

                current_state = state
                state_start_time = timestamp

        # Check that idle times are within expected range
        if idle_durations:
            avg_idle = sum(idle_durations) / len(idle_durations)
            assert (
                expected_cycle_time[0] <= avg_idle <= expected_cycle_time[1]
            ), f"NPC {agent_id} idle time {avg_idle:.2f}s outside expected range {expected_cycle_time}"


class EnemyAssertions:
    """Specific assertions for enemy agent behavior"""

    @staticmethod
    def assert_patrol_behavior(
        tracker: AgentTracker, agent_id: str, expected_patrol_area: float = 15.0
    ):
        """Assert enemy follows patrol pattern"""
        path = tracker.get_agent_path(agent_id)
        assert path is not None, f"No tracking data for agent {agent_id}"

        if len(path.snapshots) < 5:
            raise AssertionError(
                f"Not enough data for patrol analysis: {len(path.snapshots)}"
            )

        # Enemy should revisit similar areas (patrol pattern)
        positions = [(s.x, s.y) for s in path.snapshots]
        start_area = positions[: len(positions) // 3]
        end_area = positions[-len(positions) // 3 :]

        # Check if agent returns to starting area
        start_center_x = sum(pos[0] for pos in start_area) / len(start_area)
        start_center_y = sum(pos[1] for pos in start_area) / len(start_area)

        returns_to_start = any(
            math.sqrt((pos[0] - start_center_x) ** 2 + (pos[1] - start_center_y) ** 2)
            < expected_patrol_area
            for pos in end_area
        )

        assert (
            returns_to_start
        ), f"Enemy {agent_id} didn't return to patrol area (center: {start_center_x:.1f}, {start_center_y:.1f})"

    @staticmethod
    def assert_chase_behavior(metrics: BehaviorMetrics, agent_id: str):
        """Assert enemy demonstrates chase behavior when appropriate"""
        if agent_id not in metrics.state_transitions:
            raise AssertionError(f"No state transition data for enemy {agent_id}")

        transitions = metrics.state_transitions[agent_id]
        states = [state for _, state in transitions]

        # Should transition from patrol to chase
        chase_found = "chase" in states
        assert chase_found, f"Enemy {agent_id} never entered chase state"

        # Should have chase interactions
        chase_interactions = [
            event
            for event in metrics.interaction_events
            if (event["agent1"] == agent_id or event["agent2"] == agent_id)
            and event["type"] == "chase"
        ]

        assert (
            len(chase_interactions) > 0
        ), f"Enemy {agent_id} never performed chase interactions"
