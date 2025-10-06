from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..database.analytics_engine import AnalyticsEngine
from ..database.database import Database
from ..database.models import (
    ActionLog,
    AgentSnapshot,
    CombatLog,
    SimulationRun,
    WorldSnapshot,
)
from ..entities.agent import Agent
from ..entities.npc import NPC
from ..systems.fog_of_war import FogOfWar
from ..systems.respawn import RespawnManager
from ..systems.trading import Market, TradingSystem
from .config import SimulationConfig
from .time_manager import TimeManager
from .world import World

logger = logging.getLogger(__name__)


class Simulation:
    """Main simulation orchestrator that manages the game loop and all systems"""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.time_manager = TimeManager()

        # Initialize database and analytics
        self.db = Database(config.database_path)
        self.analytics = AnalyticsEngine(self.db)

        # Initialize world
        self.world = World(
            width=config.world_width, height=config.world_height, seed=config.world_seed
        )

        # Initialize systems
        self.fog_of_war = FogOfWar(self.world.width, self.world.height)
        self.trading_system = TradingSystem()
        self.respawn_manager = RespawnManager(self.world.width, self.world.height)
        self.market = Market()

        # Entity containers
        self.agents: List[Agent] = []
        self.npcs: List[NPC] = []

        # Simulation state
        self.running = False
        self.paused = False
        self.simulation_run: Optional[SimulationRun] = None
        self.simulation_id: Optional[int] = None

        # Performance tracking
        self.tick_times: List[float] = []
        self.last_save_tick = 0

        # Event handlers
        self.on_tick_complete: Optional[Callable[[int], None]] = None
        self.on_simulation_complete: Optional[Callable[[Simulation], None]] = None

    def initialize_simulation(self, name: str, description: str = "") -> None:
        """Initialize a new simulation run in the database"""
        self.simulation_run = SimulationRun(
            name=name,
            description=description,
            world_seed=self.config.world_seed,
            world_width=self.config.world_width,
            world_height=self.config.world_height,
            start_time=datetime.now(),
            total_agents=len(self.agents),
            config={
                "max_ticks": self.config.max_ticks,
                "save_interval": self.config.save_interval,
                "analytics_interval": self.config.analytics_interval,
                "tick_rate": self.config.tick_rate,
            },
        )

        self.simulation_id = self.db.create_simulation_run(self.simulation_run)
        self.simulation_run.id = self.simulation_id

        logger.info(f"Initialized simulation '{name}' with ID {self.simulation_id}")

    def add_agent(self, agent: Agent) -> None:
        """Add an agent to the simulation"""
        agent.world = self.world
        agent.fog_of_war = self.fog_of_war
        self.agents.append(agent)

        # Add agent to world entities for threat detection and interactions
        self.world.add_entity(agent)

        # Update fog of war for new agent
        if hasattr(self.fog_of_war, "update_agent_vision"):
            self.fog_of_war.update_agent_vision(agent, self.world)

    def add_agents(self, agents: List[Agent]) -> None:
        """Add multiple agents to the simulation"""
        for agent in agents:
            self.add_agent(agent)

    def add_npc(self, npc: NPC) -> None:
        """Add an NPC to the simulation"""
        npc.world = self.world
        self.npcs.append(npc)

        # Add NPC to world entities for threat detection and interactions
        self.world.add_entity(npc)

        # Note: NPCs with respawn_delay will be handled by respawn manager when they die
        # The RespawnManager.schedule_respawn method will be called when needed

    def add_npcs(self, npcs: List[NPC]) -> None:
        """Add multiple NPCs to the simulation"""
        for npc in npcs:
            self.add_npc(npc)

    def step(self) -> None:
        """Execute one simulation tick"""
        if not self.running or self.paused:
            return

        start_time = time.time()
        current_tick = self.time_manager.current_tick

        try:
            # 1. Update NPC controllers
            self._update_npcs()

            # 2. Agent perception updates
            self._update_agent_perception()

            # 3. Agent decision-making and action planning
            self._update_agent_decisions()

            # 4. Execute all queued actions
            self._execute_actions()

            # 5. Update game systems
            self._update_systems()

            # 6. Handle respawns
            self._process_respawns()

            # 7. Update market prices
            self._update_market()

            # 8. Periodic saves and analytics
            self._periodic_tasks()

            # Advance time
            self.time_manager.tick()
            self.world.current_tick = self.time_manager.current_tick

            # Track performance
            tick_duration = time.time() - start_time
            self.tick_times.append(tick_duration)

            # Keep only last 100 tick times for rolling average
            if len(self.tick_times) > 100:
                self.tick_times.pop(0)

            # Call tick completion handler
            if self.on_tick_complete:
                self.on_tick_complete(current_tick)

            logger.debug(f"Tick {current_tick} completed in {tick_duration:.4f}s")

        except Exception as e:
            logger.error(f"Error in simulation step {current_tick}: {e}")
            self.stop_simulation()
            raise

    def _update_npcs(self) -> None:
        """Update NPC AI and behaviors"""
        for npc in self.npcs:
            if npc.stats.is_alive():
                # Update NPC AI decision making
                if hasattr(npc, "update"):
                    npc.update(self.world)

                # Handle aggro and combat for hostile NPCs
                if hasattr(npc, "aggro_range") and npc.aggro_range > 0:
                    self._check_npc_aggro(npc)

    def _check_npc_aggro(self, npc: NPC) -> None:
        """Check if NPC should become aggressive towards nearby agents"""
        # Only check aggro if NPC doesn't already have a target
        if hasattr(npc, "target_id") and npc.target_id is not None:
            return  # Already has a target

        if not (hasattr(npc, "aggro_range") and npc.aggro_range > 0):
            return  # No aggro range

        # Find nearest agent within aggro range
        nearest_agent = None
        nearest_distance = float("inf")

        for agent in self.agents:
            if agent.stats.is_alive():
                # Calculate distance manually since positions are tuples
                dx = npc.position[0] - agent.position[0]
                dy = npc.position[1] - agent.position[1]
                distance = (dx * dx + dy * dy) ** 0.5

                if distance <= npc.aggro_range and distance < nearest_distance:
                    nearest_agent = agent
                    nearest_distance = distance

        # Set target to nearest agent in range
        if nearest_agent:
            npc.target_id = nearest_agent.id
            logger.info(
                f"NPC {npc.name} acquired target: Agent {nearest_agent.name} at distance {nearest_distance:.1f}"
            )

    def _update_agent_perception(self) -> None:
        """Update agent vision and perception"""
        for agent in self.agents:
            if agent.stats.is_alive():
                # Update fog of war
                self.fog_of_war.update_agent_vision(agent, self.world)

    def _update_agent_decisions(self) -> None:
        """Update agent AI decision making"""
        for agent in self.agents:
            if agent.stats.is_alive():
                agent.update(self.world)

    def _execute_actions(self) -> None:
        """Execute all queued actions for all entities"""
        all_entities = self.agents + self.npcs

        for entity in all_entities:
            if entity.stats.is_alive() and hasattr(entity, "current_action"):
                action = entity.current_action

                if action and action.is_active:
                    try:
                        # Execute the action (progressive execution)
                        result = action.execute(entity, self.world)

                        # Log the action if it completed or failed
                        if self.simulation_id and (
                            not result.success
                            or action.is_complete(self.time_manager.current_tick)
                        ):
                            action_log = ActionLog(
                                simulation_id=self.simulation_id,
                                tick=self.time_manager.current_tick,
                                agent_id=entity.id,
                                action_type=action.__class__.__name__,
                                action_data=(
                                    action.to_dict()
                                    if hasattr(action, "to_dict")
                                    else {}
                                ),
                                success=result.success,
                                result_message=result.message,
                                duration=action.get_duration(),
                            )
                            self.db.log_action(action_log)

                            # Log combat-specific events to combat_logs table
                            if hasattr(result, "events") and result.events:
                                for event in result.events:
                                    if event.event_type in [
                                        "attack_hit",
                                        "attack_miss",
                                    ]:
                                        combat_log = CombatLog(
                                            simulation_id=self.simulation_id,
                                            tick=self.time_manager.current_tick,
                                            attacker_id=event.actor_id,
                                            target_id=(
                                                event.target_id
                                                if event.target_id
                                                else 0
                                            ),
                                            damage_dealt=(
                                                event.data.get("damage", 0)
                                                if event.event_type == "attack_hit"
                                                else 0
                                            ),
                                            damage_type=event.data.get(
                                                "damage_type", "physical"
                                            ),
                                            was_critical=(
                                                event.data.get("is_critical", False)
                                                if event.event_type == "attack_hit"
                                                else False
                                            ),
                                            weapon_used=action.__class__.__name__,
                                            target_died=(
                                                event.data.get("target_died", False)
                                                if event.event_type == "attack_hit"
                                                else False
                                            ),
                                        )
                                        self.db.log_combat(combat_log)

                        # Clear action if completed or failed
                        if not result.success or action.is_complete(
                            self.time_manager.current_tick
                        ):
                            entity.current_action = None

                            # Notify the goal that the action completed
                            if (
                                hasattr(entity, "current_goals")
                                and entity.current_goals
                            ):
                                active_goal = entity.current_goals[0]
                                if hasattr(active_goal, "on_action_completed"):
                                    active_goal.on_action_completed(
                                        action, result.success, entity, self.world
                                    )

                    except Exception as e:
                        logger.error(
                            f"Error executing action {action} for entity {entity.id}: {e}"
                        )
                        entity.current_action = None

    def _update_systems(self) -> None:
        """Update all game systems"""
        # Update trading system
        self.trading_system.update(self.time_manager.current_tick)

        # Process any completed trades
        completed_trades = self.trading_system.get_completed_trades()
        for trade in completed_trades:
            # Log trades to database
            if self.simulation_id:
                from ..database.models import TradeLog

                trade_log = TradeLog(
                    simulation_id=self.simulation_id,
                    tick=self.time_manager.current_tick,
                    initiator_id=trade.get("initiator_id", 0),
                    target_id=trade.get("target_id", 0),
                    offered_items={
                        item: qty for item, qty in trade.get("offered_items", [])
                    },
                    requested_items={
                        item: qty for item, qty in trade.get("requested_items", [])
                    },
                    offered_gold=trade.get("offered_gold", 0),
                    requested_gold=trade.get("requested_gold", 0),
                    completed=True,
                )
                self.db.log_trade(trade_log)

    def _process_respawns(self) -> None:
        """Process entity respawns"""
        respawned_entities = self.respawn_manager.process_respawns(self.world)

        for entity in respawned_entities:
            if isinstance(entity, NPC):
                self.npcs.append(entity)
                entity.world = self.world
                logger.info(f"Respawned NPC {entity.name} at {entity.position}")

                # Log respawn event to database
                if self.simulation_id:
                    action_log = ActionLog(
                        simulation_id=self.simulation_id,
                        tick=self.time_manager.current_tick,
                        agent_id=entity.id,
                        action_type="Respawn",
                        action_data={
                            "entity_type": "NPC",
                            "npc_type": getattr(entity, "npc_type", "unknown"),
                            "position": entity.position,
                        },
                        success=True,
                        result_message=f"Respawned {entity.name} at {entity.position}",
                        duration=0,
                    )
                    self.db.log_action(action_log)
            elif isinstance(entity, Agent):
                self.agents.append(entity)
                entity.world = self.world
                entity.fog_of_war = self.fog_of_war
                logger.info(f"Respawned Agent {entity.name} at {entity.position}")

                # Log respawn event to database
                if self.simulation_id:
                    action_log = ActionLog(
                        simulation_id=self.simulation_id,
                        tick=self.time_manager.current_tick,
                        agent_id=entity.id,
                        action_type="Respawn",
                        action_data={
                            "entity_type": "Agent",
                            "character_class": (
                                getattr(entity.character_class, "name", "unknown")
                                if hasattr(entity, "character_class")
                                else "unknown"
                            ),
                            "position": entity.position,
                        },
                        success=True,
                        result_message=f"Respawned {entity.name} at {entity.position}",
                        duration=0,
                    )
                    self.db.log_action(action_log)

    def _update_market(self) -> None:
        """Update market prices based on recent trades"""
        if self.time_manager.current_tick % 50 == 0:  # Update every 50 ticks
            # Get recent trade data and update market prices
            self.market.update_prices(self.time_manager.current_tick)

    def _periodic_tasks(self) -> None:
        """Handle periodic database saves and analytics"""
        current_tick = self.time_manager.current_tick

        # Save snapshots periodically
        if current_tick - self.last_save_tick >= self.config.save_interval:
            self._save_snapshots()
            self.last_save_tick = current_tick

        # Calculate analytics periodically
        if current_tick % self.config.analytics_interval == 0 and self.simulation_id:
            self.analytics.calculate_all_metrics(self.simulation_id, current_tick)

    def _save_snapshots(self) -> None:
        """Save agent and world snapshots to database"""
        if not self.simulation_id:
            return

        current_tick = self.time_manager.current_tick

        # Save agent snapshots (including NPCs for testing purposes)
        agent_snapshots = []

        # Save agent snapshots
        for agent in self.agents:
            snapshot = AgentSnapshot(
                simulation_id=self.simulation_id,
                agent_id=agent.id,
                tick=current_tick,
                name=agent.name,
                position_x=agent.position[0],
                position_y=agent.position[1],
                health=agent.stats.health,
                max_health=agent.stats.max_health,
                stamina=agent.stats.stamina,
                max_stamina=agent.stats.max_stamina,
                personality=(
                    agent.personality.to_dict() if hasattr(agent, "personality") else {}
                ),
                character_class=(
                    agent.character_class.name
                    if hasattr(agent, "character_class")
                    else ""
                ),
                skills=agent.skills if hasattr(agent, "skills") else {},
                current_goals=(
                    [str(goal) for goal in agent.current_goals]
                    if hasattr(agent, "current_goals")
                    else []
                ),
                relationships=(
                    agent.relationships if hasattr(agent, "relationships") else {}
                ),
                inventory_items=(
                    len(agent.inventory.items) if hasattr(agent, "inventory") else 0
                ),
                gold=0,  # TODO: Implement gold system
            )
            agent_snapshots.append(snapshot)

        # Also save NPC snapshots (treat as agents for tracking purposes)
        for npc in self.npcs:
            snapshot = AgentSnapshot(
                simulation_id=self.simulation_id,
                agent_id=npc.id,
                tick=current_tick,
                name=npc.name,
                position_x=npc.position[0],
                position_y=npc.position[1],
                health=npc.stats.health,
                max_health=npc.stats.max_health,
                stamina=npc.stats.stamina,
                max_stamina=npc.stats.max_stamina,
                personality={},  # NPCs don't have personality
                character_class=npc.npc_type,  # Use NPC type as class
                skills={},
                current_goals=[],
                relationships={},
                inventory_items=0,
                gold=0,
            )
            agent_snapshots.append(snapshot)

        if agent_snapshots:
            self.db.save_agent_snapshots_batch(agent_snapshots)

        # Save world snapshot
        world_snapshot = WorldSnapshot(
            simulation_id=self.simulation_id,
            tick=current_tick,
            total_entities=len(self.agents) + len(self.npcs),
            active_agents=len([a for a in self.agents if a.stats.is_alive()]),
            active_npcs=len([n for n in self.npcs if n.stats.is_alive()]),
            resource_nodes=0,  # TODO: Implement resource node counting
            world_events=[],  # TODO: Implement world events
            market_prices=self.market.get_current_prices(),
        )
        self.db.save_world_snapshot(world_snapshot)

        logger.debug(f"Saved snapshots for tick {current_tick}")

    def run(self, num_ticks: Optional[int] = None) -> None:
        """Run the simulation for a specified number of ticks"""
        if not self.simulation_id:
            raise RuntimeError(
                "Simulation not initialized. Call initialize_simulation() first."
            )

        self.running = True
        target_tick = None

        if num_ticks:
            target_tick = self.time_manager.current_tick + num_ticks

        logger.info(f"Starting simulation run for {num_ticks or 'unlimited'} ticks")

        try:
            while self.running:
                if target_tick and self.time_manager.current_tick >= target_tick:
                    break

                if self.time_manager.current_tick >= self.config.max_ticks:
                    logger.info(f"Reached maximum ticks ({self.config.max_ticks})")
                    break

                self.step()

                # Optional tick rate limiting
                if self.config.tick_rate > 0:
                    time.sleep(1.0 / self.config.tick_rate)

        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        finally:
            self.stop_simulation()

    def run_until(self, condition: Callable[[Simulation], bool]) -> None:
        """Run the simulation until a condition is met"""
        if not self.simulation_id:
            raise RuntimeError(
                "Simulation not initialized. Call initialize_simulation() first."
            )

        self.running = True
        logger.info("Starting simulation with custom condition")

        try:
            while self.running and not condition(self):
                if self.time_manager.current_tick >= self.config.max_ticks:
                    logger.info(f"Reached maximum ticks ({self.config.max_ticks})")
                    break

                self.step()

                if self.config.tick_rate > 0:
                    time.sleep(1.0 / self.config.tick_rate)

        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        finally:
            self.stop_simulation()

    def run_with_visualizer(self, num_ticks: Optional[int] = None) -> None:
        """Run the simulation with pygame visualization"""
        if not self.simulation_id:
            raise RuntimeError(
                "Simulation not initialized. Call initialize_simulation() first."
            )

        # Import visualizer here to avoid dependency issues if pygame is not available
        try:
            import os
            import sys

            # Add the root directory to the Python path for visualizer imports
            root_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../../..")
            )
            if root_dir not in sys.path:
                sys.path.insert(0, root_dir)

            from visualizer.pygame_visualizer import GameVisualizer
            from visualizer.ui import UIManager
        except ImportError as e:
            logger.error(f"Failed to import visualizer: {e}")
            logger.error("Make sure pygame is installed: pip install pygame>=2.0.0")
            return

        # Initialize visualizer
        visualizer = GameVisualizer(
            width=self.config.visualizer_width,
            height=self.config.visualizer_height,
            tile_size=self.config.visualizer_tile_size,
        )

        ui_manager = UIManager(
            self.config.visualizer_width, self.config.visualizer_height
        )

        self.running = True
        target_tick = None

        if num_ticks:
            target_tick = self.time_manager.current_tick + num_ticks

        logger.info(
            f"Starting visual simulation run for {num_ticks or 'unlimited'} ticks"
        )

        try:
            clock = None
            try:
                import pygame

                clock = pygame.time.Clock()
            except ImportError:
                pass

            while self.running and visualizer.running:
                # Handle visualizer events
                if not visualizer.handle_events(self):
                    break

                # Check tick limit
                if target_tick and self.time_manager.current_tick >= target_tick:
                    break

                if self.time_manager.current_tick >= self.config.max_ticks:
                    logger.info(f"Reached maximum ticks ({self.config.max_ticks})")
                    break

                # Update UI manager
                ui_manager.update()

                # Handle agent selection from visualizer
                if visualizer.selected_agent != ui_manager.selected_entity:
                    ui_manager.show_entity_info(visualizer.selected_agent)

                # Step simulation
                if not self.paused:
                    self.step()

                # Render visualization
                visualizer.render(self)

                # Prepare simulation data for UI
                simulation_data = {
                    "current_tick": self.time_manager.current_tick,
                    "total_agents": len(self.agents),
                    "alive_agents": len([a for a in self.agents if a.stats.is_alive]),
                    "total_npcs": len(self.npcs),
                    "alive_npcs": len([n for n in self.npcs if n.stats.is_alive]),
                    "zoom": visualizer.camera.zoom,
                }

                # Render UI
                ui_manager.render(visualizer.screen, simulation_data)

                # Update display
                try:
                    import pygame

                    pygame.display.flip()
                except ImportError:
                    pass

                # Frame rate limiting for smooth visualization
                if clock and self.config.tick_rate > 0:
                    clock.tick(min(60, self.config.tick_rate))
                elif clock:
                    clock.tick(60)  # Default to 60 FPS

        except KeyboardInterrupt:
            logger.info("Visual simulation interrupted by user")
        finally:
            visualizer.quit()
            self.stop_simulation()

    def pause_simulation(self) -> None:
        """Pause the simulation"""
        self.paused = True
        logger.info("Simulation paused")

    def resume_simulation(self) -> None:
        """Resume the simulation"""
        self.paused = False
        logger.info("Simulation resumed")

    def stop_simulation(self) -> None:
        """Stop the simulation and finalize"""
        self.running = False

        if self.simulation_run and self.simulation_id:
            # Update simulation end time
            self.simulation_run.end_time = datetime.now()
            self.simulation_run.current_tick = self.time_manager.current_tick
            self.db.update_simulation_run(self.simulation_run)

            # Final save
            self._save_snapshots()

            # Final analytics calculation
            self.analytics.calculate_all_metrics(
                self.simulation_id, self.time_manager.current_tick
            )

        # Call completion handler
        if self.on_simulation_complete:
            self.on_simulation_complete(self)

        logger.info(f"Simulation stopped at tick {self.time_manager.current_tick}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get current simulation statistics"""
        return {
            "current_tick": self.time_manager.current_tick,
            "total_agents": len(self.agents),
            "active_agents": len([a for a in self.agents if a.stats.is_alive()]),
            "total_npcs": len(self.npcs),
            "active_npcs": len([n for n in self.npcs if n.stats.is_alive()]),
            "average_tick_time": (
                sum(self.tick_times) / len(self.tick_times) if self.tick_times else 0
            ),
            "simulation_id": self.simulation_id,
            "running": self.running,
            "paused": self.paused,
        }

    def get_analytics_report(self) -> Optional[Dict[str, Any]]:
        """Get comprehensive analytics report"""
        if not self.simulation_id:
            return None

        return self.analytics.generate_simulation_report(self.simulation_id)
