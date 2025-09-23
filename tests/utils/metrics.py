import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PerformanceMetrics:
    """Performance metrics for the simulation"""

    cpu_usage: List[float]
    memory_usage: List[float]
    tick_rates: List[float]
    network_latency: List[float]
    agent_counts: List[int]
    timestamps: List[float]

    def get_average_tick_rate(self) -> float:
        return sum(self.tick_rates) / len(self.tick_rates) if self.tick_rates else 0.0

    def get_average_latency(self) -> float:
        return (
            sum(self.network_latency) / len(self.network_latency)
            if self.network_latency
            else 0.0
        )


@dataclass
class MovementPattern:
    """Analyze movement patterns for agents"""

    positions: List[Tuple[float, float]]
    timestamps: List[float]
    agent_type: str

    def get_velocity_variance(self) -> float:
        """Calculate variance in velocity (indicates erratic vs smooth movement)"""
        if len(self.positions) < 3:
            return 0.0

        velocities = []
        for i in range(1, len(self.positions) - 1):
            dt1 = self.timestamps[i] - self.timestamps[i - 1]
            dt2 = self.timestamps[i + 1] - self.timestamps[i]

            if dt1 > 0 and dt2 > 0:
                # Calculate velocity vectors
                v1_x = (self.positions[i][0] - self.positions[i - 1][0]) / dt1
                v1_y = (self.positions[i][1] - self.positions[i - 1][1]) / dt1
                v2_x = (self.positions[i + 1][0] - self.positions[i][0]) / dt2
                v2_y = (self.positions[i + 1][1] - self.positions[i][1]) / dt2

                # Calculate velocity magnitude difference
                v1_mag = math.sqrt(v1_x * v1_x + v1_y * v1_y)
                v2_mag = math.sqrt(v2_x * v2_x + v2_y * v2_y)
                velocities.append(abs(v2_mag - v1_mag))

        if not velocities:
            return 0.0

        mean_vel = sum(velocities) / len(velocities)
        variance = sum((v - mean_vel) ** 2 for v in velocities) / len(velocities)
        return variance

    def get_exploration_efficiency(self) -> float:
        """Calculate exploration efficiency (unique area / total distance)"""
        if len(self.positions) < 2:
            return 0.0

        # Calculate total distance
        total_distance = 0.0
        for i in range(1, len(self.positions)):
            dx = self.positions[i][0] - self.positions[i - 1][0]
            dy = self.positions[i][1] - self.positions[i - 1][1]
            total_distance += math.sqrt(dx * dx + dy * dy)

        if total_distance == 0:
            return 0.0

        # Calculate unique tiles visited
        tiles = set()
        for pos in self.positions:
            tile_x = int(pos[0])
            tile_y = int(pos[1])
            tiles.add((tile_x, tile_y))

        unique_area = len(tiles)
        return unique_area / total_distance

    def get_directional_bias(self) -> Dict[str, float]:
        """Calculate directional movement bias"""
        directions = {"north": 0, "south": 0, "east": 0, "west": 0}
        total_moves = 0

        for i in range(1, len(self.positions)):
            dx = self.positions[i][0] - self.positions[i - 1][0]
            dy = self.positions[i][1] - self.positions[i - 1][1]

            if abs(dx) > 0.1 or abs(dy) > 0.1:  # Only count significant moves
                total_moves += 1
                if abs(dx) > abs(dy):
                    if dx > 0:
                        directions["east"] += 1
                    else:
                        directions["west"] += 1
                else:
                    if dy > 0:
                        directions["south"] += 1
                    else:
                        directions["north"] += 1

        if total_moves == 0:
            return {k: 0.0 for k in directions}

        return {k: v / total_moves for k, v in directions.items()}


class BehaviorMetrics:
    """Collect and analyze agent behavior metrics"""

    def __init__(self):
        self.movement_patterns: Dict[str, MovementPattern] = {}
        self.state_transitions: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        self.interaction_events: List[Dict[str, Any]] = []
        self.performance: PerformanceMetrics = PerformanceMetrics(
            cpu_usage=[],
            memory_usage=[],
            tick_rates=[],
            network_latency=[],
            agent_counts=[],
            timestamps=[],
        )

    def record_agent_position(
        self,
        agent_id: str,
        agent_type: str,
        position: Tuple[float, float],
        timestamp: float,
    ):
        """Record agent position for movement analysis"""
        if agent_id not in self.movement_patterns:
            self.movement_patterns[agent_id] = MovementPattern(
                positions=[], timestamps=[], agent_type=agent_type
            )

        pattern = self.movement_patterns[agent_id]
        pattern.positions.append(position)
        pattern.timestamps.append(timestamp)

    def record_state_transition(self, agent_id: str, new_state: str, timestamp: float):
        """Record agent state change"""
        self.state_transitions[agent_id].append((timestamp, new_state))

    def record_interaction(
        self,
        agent1_id: str,
        agent2_id: str,
        interaction_type: str,
        timestamp: float,
        details: Optional[Dict] = None,
    ):
        """Record interaction between agents"""
        event = {
            "timestamp": timestamp,
            "agent1": agent1_id,
            "agent2": agent2_id,
            "type": interaction_type,
            "details": details or {},
        }
        self.interaction_events.append(event)

    def record_performance(
        self,
        tick_rate: float,
        agent_count: int,
        timestamp: float,
        cpu_usage: float = 0.0,
        memory_usage: float = 0.0,
        latency: float = 0.0,
    ):
        """Record performance metrics"""
        self.performance.tick_rates.append(tick_rate)
        self.performance.agent_counts.append(agent_count)
        self.performance.timestamps.append(timestamp)
        self.performance.cpu_usage.append(cpu_usage)
        self.performance.memory_usage.append(memory_usage)
        self.performance.network_latency.append(latency)

    def analyze_explorer_behavior(self) -> Dict[str, Any]:
        """Analyze explorer-specific behavior patterns"""
        explorer_patterns = {
            agent_id: pattern
            for agent_id, pattern in self.movement_patterns.items()
            if pattern.agent_type == "explorer"
        }

        if not explorer_patterns:
            return {"error": "No explorer data found"}

        analysis = {
            "total_explorers": len(explorer_patterns),
            "average_efficiency": 0.0,
            "movement_variance": 0.0,
            "coverage_overlap": 0.0,
            "individual_stats": {},
        }

        efficiencies = []
        variances = []
        all_tiles = set()
        individual_tiles = {}

        for agent_id, pattern in explorer_patterns.items():
            efficiency = pattern.get_exploration_efficiency()
            variance = pattern.get_velocity_variance()
            directional_bias = pattern.get_directional_bias()

            efficiencies.append(efficiency)
            variances.append(variance)

            # Calculate tiles for overlap analysis
            tiles = set()
            for pos in pattern.positions:
                tile = (int(pos[0]), int(pos[1]))
                tiles.add(tile)
                all_tiles.add(tile)

            individual_tiles[agent_id] = tiles

            analysis["individual_stats"][agent_id] = {
                "efficiency": efficiency,
                "variance": variance,
                "directional_bias": directional_bias,
                "tiles_explored": len(tiles),
                "total_distance": self._calculate_total_distance(pattern.positions),
            }

        # Calculate averages
        analysis["average_efficiency"] = sum(efficiencies) / len(efficiencies)
        analysis["movement_variance"] = sum(variances) / len(variances)

        # Calculate overlap (how much agents explored the same areas)
        total_unique_tiles = len(all_tiles)
        total_individual_tiles = sum(len(tiles) for tiles in individual_tiles.values())
        if total_individual_tiles > 0:
            analysis["coverage_overlap"] = 1.0 - (
                total_unique_tiles / total_individual_tiles
            )

        return analysis

    def analyze_npc_behavior(self) -> Dict[str, Any]:
        """Analyze NPC-specific behavior patterns"""
        npc_patterns = {
            agent_id: pattern
            for agent_id, pattern in self.movement_patterns.items()
            if pattern.agent_type == "npc"
        }

        if not npc_patterns:
            return {"error": "No NPC data found"}

        analysis = {
            "total_npcs": len(npc_patterns),
            "average_wander_radius": 0.0,
            "state_transition_frequency": 0.0,
            "individual_stats": {},
        }

        wander_radii = []

        for agent_id, pattern in npc_patterns.items():
            if not pattern.positions:
                continue

            # Calculate wander radius (max distance from starting position)
            start_pos = pattern.positions[0]
            max_distance = 0.0
            for pos in pattern.positions:
                distance = math.sqrt(
                    (pos[0] - start_pos[0]) ** 2 + (pos[1] - start_pos[1]) ** 2
                )
                max_distance = max(max_distance, distance)

            wander_radii.append(max_distance)

            # Analyze state transitions
            transitions = self.state_transitions.get(agent_id, [])
            transition_frequency = (
                len(transitions) / (pattern.timestamps[-1] - pattern.timestamps[0])
                if len(pattern.timestamps) > 1
                else 0
            )

            analysis["individual_stats"][agent_id] = {
                "wander_radius": max_distance,
                "transition_frequency": transition_frequency,
                "total_distance": self._calculate_total_distance(pattern.positions),
            }

        if wander_radii:
            analysis["average_wander_radius"] = sum(wander_radii) / len(wander_radii)

        return analysis

    def analyze_enemy_behavior(self) -> Dict[str, Any]:
        """Analyze enemy-specific behavior patterns"""
        enemy_patterns = {
            agent_id: pattern
            for agent_id, pattern in self.movement_patterns.items()
            if pattern.agent_type == "enemy"
        }

        if not enemy_patterns:
            return {"error": "No enemy data found"}

        analysis = {
            "total_enemies": len(enemy_patterns),
            "chase_events": 0,
            "attack_events": 0,
            "patrol_efficiency": 0.0,
            "individual_stats": {},
        }

        # Count interaction events
        for event in self.interaction_events:
            if event["type"] == "chase":
                analysis["chase_events"] += 1
            elif event["type"] == "attack":
                analysis["attack_events"] += 1

        patrol_efficiencies = []

        for agent_id, pattern in enemy_patterns.items():
            # Analyze patrol pattern (how well they cover their patrol route)
            efficiency = pattern.get_exploration_efficiency()
            patrol_efficiencies.append(efficiency)

            # Count state transitions for this enemy
            transitions = self.state_transitions.get(agent_id, [])
            patrol_states = sum(1 for _, state in transitions if state == "patrol")
            chase_states = sum(1 for _, state in transitions if state == "chase")
            attack_states = sum(1 for _, state in transitions if state == "attack")

            analysis["individual_stats"][agent_id] = {
                "patrol_efficiency": efficiency,
                "patrol_time": patrol_states,
                "chase_time": chase_states,
                "attack_time": attack_states,
                "total_distance": self._calculate_total_distance(pattern.positions),
            }

        if patrol_efficiencies:
            analysis["patrol_efficiency"] = sum(patrol_efficiencies) / len(
                patrol_efficiencies
            )

        return analysis

    def _calculate_total_distance(self, positions: List[Tuple[float, float]]) -> float:
        """Helper to calculate total distance traveled"""
        if len(positions) < 2:
            return 0.0

        total = 0.0
        for i in range(1, len(positions)):
            dx = positions[i][0] - positions[i - 1][0]
            dy = positions[i][1] - positions[i - 1][1]
            total += math.sqrt(dx * dx + dy * dy)
        return total

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive behavior analysis report"""
        return {
            "explorer_analysis": self.analyze_explorer_behavior(),
            "npc_analysis": self.analyze_npc_behavior(),
            "enemy_analysis": self.analyze_enemy_behavior(),
            "performance_summary": {
                "average_tick_rate": self.performance.get_average_tick_rate(),
                "average_latency": self.performance.get_average_latency(),
                "total_interactions": len(self.interaction_events),
            },
        }
