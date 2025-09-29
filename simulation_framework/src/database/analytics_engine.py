from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
import statistics
from collections import defaultdict, Counter
from datetime import datetime

from .database import Database
from .models import Analytics, AgentSnapshot, WorldSnapshot, ActionLog, TradeLog, CombatLog


class AnalyticsEngine:
    """Analytics engine for calculating simulation metrics and insights"""

    def __init__(self, database: Database):
        self.db = database

    def calculate_all_metrics(self, simulation_id: int, current_tick: int) -> None:
        """Calculate and save all available metrics for a simulation"""

        # Economic metrics
        self._calculate_economic_metrics(simulation_id, current_tick)

        # Social metrics
        self._calculate_social_metrics(simulation_id, current_tick)

        # Combat metrics
        self._calculate_combat_metrics(simulation_id, current_tick)

        # Exploration metrics
        self._calculate_exploration_metrics(simulation_id, current_tick)

        # Agent performance metrics
        self._calculate_agent_performance_metrics(simulation_id, current_tick)

    def _calculate_economic_metrics(self, simulation_id: int, current_tick: int) -> None:
        """Calculate economy-related metrics"""

        # Get recent world snapshots for market data
        world_snapshots = self.db.get_world_snapshots(
            simulation_id,
            start_tick=max(0, current_tick - 100),
            end_tick=current_tick
        )

        if world_snapshots:
            latest_snapshot = world_snapshots[0]
            market_prices = latest_snapshot.market_prices

            if market_prices:
                # Average market price
                avg_price = statistics.mean(market_prices.values())
                self._save_metric(simulation_id, current_tick, "average_market_price", avg_price, "economy")

                # Price volatility (standard deviation)
                if len(market_prices) > 1:
                    price_volatility = statistics.stdev(market_prices.values())
                    self._save_metric(simulation_id, current_tick, "price_volatility", price_volatility, "economy")

                # Most expensive item
                max_price = max(market_prices.values())
                self._save_metric(simulation_id, current_tick, "max_item_price", max_price, "economy")

        # Trade volume and frequency
        recent_trades = self.db.get_action_logs(
            simulation_id,
            action_type="trade",
            start_tick=max(0, current_tick - 50)
        )

        trade_volume = len(recent_trades)
        self._save_metric(simulation_id, current_tick, "recent_trade_volume", trade_volume, "economy")

        # Trade success rate
        if trade_volume > 0:
            successful_trades = sum(1 for trade in recent_trades if trade.success)
            trade_success_rate = successful_trades / trade_volume
            self._save_metric(simulation_id, current_tick, "trade_success_rate", trade_success_rate, "economy")

    def _calculate_social_metrics(self, simulation_id: int, current_tick: int) -> None:
        """Calculate social interaction metrics"""

        # Get recent agent snapshots
        recent_agents = self.db.get_agent_snapshots(
            simulation_id,
            start_tick=max(0, current_tick - 10),
            end_tick=current_tick
        )

        if not recent_agents:
            return

        # Group by agent_id to get latest snapshot per agent
        agent_data = {}
        for snapshot in recent_agents:
            if snapshot.agent_id not in agent_data or snapshot.tick > agent_data[snapshot.agent_id].tick:
                agent_data[snapshot.agent_id] = snapshot

        # Calculate relationship metrics
        total_relationships = 0
        positive_relationships = 0
        relationship_scores = []

        for agent in agent_data.values():
            if agent.relationships:
                total_relationships += len(agent.relationships)
                for score in agent.relationships.values():
                    relationship_scores.append(score)
                    if score > 0:
                        positive_relationships += 1

        if total_relationships > 0:
            avg_relationship_score = statistics.mean(relationship_scores)
            self._save_metric(simulation_id, current_tick, "average_relationship_score", avg_relationship_score, "social")

            positive_relationship_ratio = positive_relationships / total_relationships
            self._save_metric(simulation_id, current_tick, "positive_relationship_ratio", positive_relationship_ratio, "social")

        # Agent clustering (agents in proximity)
        agent_positions = [(agent.position_x, agent.position_y) for agent in agent_data.values()]
        clustering_metric = self._calculate_clustering(agent_positions)
        self._save_metric(simulation_id, current_tick, "agent_clustering", clustering_metric, "social")

    def _calculate_combat_metrics(self, simulation_id: int, current_tick: int) -> None:
        """Calculate combat-related metrics"""

        # Get recent combat actions
        recent_combats = self.db.get_action_logs(
            simulation_id,
            action_type="combat",
            start_tick=max(0, current_tick - 100)
        )

        combat_frequency = len(recent_combats) / 100.0  # per tick
        self._save_metric(simulation_id, current_tick, "combat_frequency", combat_frequency, "combat")

        if recent_combats:
            successful_combats = sum(1 for combat in recent_combats if combat.success)
            combat_success_rate = successful_combats / len(recent_combats)
            self._save_metric(simulation_id, current_tick, "combat_success_rate", combat_success_rate, "combat")

        # Death rate
        death_actions = self.db.get_action_logs(
            simulation_id,
            action_type="death",
            start_tick=max(0, current_tick - 100)
        )

        death_rate = len(death_actions) / 100.0  # per tick
        self._save_metric(simulation_id, current_tick, "death_rate", death_rate, "combat")

    def _calculate_exploration_metrics(self, simulation_id: int, current_tick: int) -> None:
        """Calculate exploration and movement metrics"""

        # Get exploration actions
        explore_actions = self.db.get_action_logs(
            simulation_id,
            action_type="explore",
            start_tick=max(0, current_tick - 50)
        )

        exploration_rate = len(explore_actions) / 50.0  # per tick
        self._save_metric(simulation_id, current_tick, "exploration_rate", exploration_rate, "exploration")

        # Movement diversity (how spread out agents are)
        recent_agents = self.db.get_agent_snapshots(
            simulation_id,
            start_tick=current_tick,
            end_tick=current_tick
        )

        if recent_agents:
            positions = [(agent.position_x, agent.position_y) for agent in recent_agents]
            movement_spread = self._calculate_position_spread(positions)
            self._save_metric(simulation_id, current_tick, "agent_spread", movement_spread, "exploration")

    def _calculate_agent_performance_metrics(self, simulation_id: int, current_tick: int) -> None:
        """Calculate individual agent performance metrics"""

        # Get current agent snapshots
        current_agents = self.db.get_agent_snapshots(
            simulation_id,
            start_tick=current_tick,
            end_tick=current_tick
        )

        if not current_agents:
            return

        # Health metrics
        health_ratios = [agent.health / agent.max_health for agent in current_agents]
        avg_health = statistics.mean(health_ratios)
        self._save_metric(simulation_id, current_tick, "average_agent_health", avg_health, "agents")

        # Stamina metrics
        stamina_ratios = [agent.stamina / agent.max_stamina for agent in current_agents]
        avg_stamina = statistics.mean(stamina_ratios)
        self._save_metric(simulation_id, current_tick, "average_agent_stamina", avg_stamina, "agents")

        # Inventory metrics
        inventory_sizes = [agent.inventory_items for agent in current_agents]
        avg_inventory = statistics.mean(inventory_sizes)
        self._save_metric(simulation_id, current_tick, "average_inventory_size", avg_inventory, "agents")

        # Gold distribution
        gold_amounts = [agent.gold for agent in current_agents]
        avg_gold = statistics.mean(gold_amounts)
        self._save_metric(simulation_id, current_tick, "average_agent_gold", avg_gold, "economy")

        if len(gold_amounts) > 1:
            gold_inequality = self._calculate_gini_coefficient(gold_amounts)
            self._save_metric(simulation_id, current_tick, "gold_inequality", gold_inequality, "economy")

    def _calculate_clustering(self, positions: List[Tuple[int, int]]) -> float:
        """Calculate how clustered agents are (0 = spread out, 1 = clustered)"""
        if len(positions) < 2:
            return 0.0

        total_distance = 0
        count = 0

        for i, pos1 in enumerate(positions):
            for j, pos2 in enumerate(positions[i+1:], i+1):
                distance = ((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)**0.5
                total_distance += distance
                count += 1

        avg_distance = total_distance / count

        # Normalize to 0-1 range (assuming max distance is ~100)
        return max(0, 1 - (avg_distance / 100))

    def _calculate_position_spread(self, positions: List[Tuple[int, int]]) -> float:
        """Calculate how spread out positions are"""
        if len(positions) < 2:
            return 0.0

        x_coords = [pos[0] for pos in positions]
        y_coords = [pos[1] for pos in positions]

        x_spread = max(x_coords) - min(x_coords)
        y_spread = max(y_coords) - min(y_coords)

        return (x_spread + y_spread) / 2.0

    def _calculate_gini_coefficient(self, values: List[float]) -> float:
        """Calculate Gini coefficient for inequality measurement"""
        if not values:
            return 0.0

        # Sort values
        sorted_values = sorted(values)
        n = len(sorted_values)

        # Calculate Gini coefficient
        cumsum = 0
        for i, value in enumerate(sorted_values):
            cumsum += (i + 1) * value

        total = sum(sorted_values)
        if total == 0:
            return 0.0

        gini = (2 * cumsum) / (n * total) - (n + 1) / n
        return gini

    def _save_metric(self, simulation_id: int, tick: int, name: str, value: float, category: str, metadata: Dict = None) -> None:
        """Helper to save a metric to the database"""
        analytics = Analytics(
            simulation_id=simulation_id,
            metric_name=name,
            metric_value=value,
            tick=tick,
            category=category,
            metadata=metadata or {}
        )
        self.db.save_analytics(analytics)

    def get_trend_analysis(self, simulation_id: int, metric_name: str, window_size: int = 100) -> Dict[str, Any]:
        """Analyze trends for a specific metric"""
        analytics_data = self.db.get_analytics(
            simulation_id,
            metric_name=metric_name,
            limit=window_size
        )

        if len(analytics_data) < 2:
            return {"trend": "insufficient_data", "points": len(analytics_data)}

        # Sort by tick
        analytics_data.sort(key=lambda x: x.tick)

        values = [data.metric_value for data in analytics_data]
        ticks = [data.tick for data in analytics_data]

        # Calculate trend
        if len(values) > 1:
            slope = (values[-1] - values[0]) / (ticks[-1] - ticks[0])
            trend = "increasing" if slope > 0.01 else "decreasing" if slope < -0.01 else "stable"
        else:
            trend = "stable"
            slope = 0

        # Calculate statistics
        avg_value = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0
        min_value = min(values)
        max_value = max(values)

        return {
            "trend": trend,
            "slope": slope,
            "average": avg_value,
            "std_deviation": std_dev,
            "min_value": min_value,
            "max_value": max_value,
            "data_points": len(values),
            "tick_range": (ticks[0], ticks[-1]) if ticks else None
        }

    def get_correlation_analysis(self, simulation_id: int, metric1: str, metric2: str) -> Dict[str, Any]:
        """Analyze correlation between two metrics"""
        data1 = self.db.get_analytics(simulation_id, metric_name=metric1, limit=500)
        data2 = self.db.get_analytics(simulation_id, metric_name=metric2, limit=500)

        if len(data1) < 2 or len(data2) < 2:
            return {"correlation": "insufficient_data"}

        # Create tick-aligned datasets
        data1_dict = {d.tick: d.metric_value for d in data1}
        data2_dict = {d.tick: d.metric_value for d in data2}

        common_ticks = set(data1_dict.keys()) & set(data2_dict.keys())

        if len(common_ticks) < 2:
            return {"correlation": "no_common_timepoints"}

        values1 = [data1_dict[tick] for tick in common_ticks]
        values2 = [data2_dict[tick] for tick in common_ticks]

        # Calculate Pearson correlation coefficient
        try:
            correlation = statistics.correlation(values1, values2) if len(values1) > 1 else 0
        except AttributeError:
            # Fallback for Python < 3.10
            correlation = self._calculate_correlation(values1, values2)

        return {
            "correlation": correlation,
            "strength": self._interpret_correlation(correlation),
            "common_points": len(common_ticks),
            "metric1": metric1,
            "metric2": metric2
        }

    def _calculate_correlation(self, values1: List[float], values2: List[float]) -> float:
        """Calculate Pearson correlation coefficient (fallback implementation)"""
        if len(values1) != len(values2) or len(values1) < 2:
            return 0.0

        mean1 = statistics.mean(values1)
        mean2 = statistics.mean(values2)

        numerator = sum((x - mean1) * (y - mean2) for x, y in zip(values1, values2))

        sum_sq1 = sum((x - mean1) ** 2 for x in values1)
        sum_sq2 = sum((y - mean2) ** 2 for y in values2)

        denominator = (sum_sq1 * sum_sq2) ** 0.5

        return numerator / denominator if denominator != 0 else 0.0

    def _interpret_correlation(self, correlation: float) -> str:
        """Interpret correlation strength"""
        abs_corr = abs(correlation)
        if abs_corr >= 0.8:
            return "very_strong"
        elif abs_corr >= 0.6:
            return "strong"
        elif abs_corr >= 0.4:
            return "moderate"
        elif abs_corr >= 0.2:
            return "weak"
        else:
            return "very_weak"

    def generate_simulation_report(self, simulation_id: int) -> Dict[str, Any]:
        """Generate comprehensive simulation report"""
        simulation = self.db.get_simulation_run(simulation_id)
        if not simulation:
            return {"error": "Simulation not found"}

        report = {
            "simulation": {
                "id": simulation.id,
                "name": simulation.name,
                "description": simulation.description,
                "current_tick": simulation.current_tick,
                "total_agents": simulation.total_agents
            },
            "summaries": {
                "agents": self.db.get_agent_summary(simulation_id),
                "actions": self.db.get_action_summary(simulation_id),
                "trades": self.db.get_trade_summary(simulation_id),
                "combat": self.db.get_combat_summary(simulation_id)
            },
            "key_metrics": {},
            "trends": {}
        }

        # Get key metrics
        key_metrics = [
            "average_agent_health", "average_agent_stamina", "exploration_rate",
            "combat_frequency", "trade_success_rate", "agent_clustering"
        ]

        for metric in key_metrics:
            latest_data = self.db.get_analytics(simulation_id, metric_name=metric, limit=1)
            if latest_data:
                report["key_metrics"][metric] = latest_data[0].metric_value
                report["trends"][metric] = self.get_trend_analysis(simulation_id, metric, window_size=50)

        return report