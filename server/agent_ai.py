"""
Server-Side Agent AI System

This module centralizes all agent decision-making on the server side, eliminating
the need for complex client-side behavior trees. It provides simple, configurable
behavior profiles and makes all movement, combat, and tactical decisions using
authoritative server data.

Key Benefits:
- Single source of truth for all agent behavior
- No client-server synchronization issues
- Simplified agent development
- Built-in anti-cheat protection
- Dynamic behavior modification during runtime
"""

import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.messages import AgentData

logger = logging.getLogger(__name__)


class AIState(Enum):
    """High-level AI states for agent behavior"""
    IDLE = "idle"
    PATROL = "patrol"
    CHASE = "chase"
    COMBAT = "combat"
    FLEE = "flee"
    DEAD = "dead"


class AgentPersonality(Enum):
    """Agent personality types that modify behavior"""
    AGGRESSIVE = "aggressive"  # Engages quickly, chases longer
    DEFENSIVE = "defensive"    # Cautious, retreats when hurt
    NEUTRAL = "neutral"        # Balanced behavior
    COWARD = "coward"         # Avoids combat, flees quickly


@dataclass
class BehaviorProfile:
    """Configuration for agent behavior patterns"""

    # Vision and detection
    vision_range: float = 10.0
    enemy_types: Set[str] = field(default_factory=set)

    # Combat behavior
    attack_range: float = 2.0
    chase_range: float = 15.0
    flee_health_threshold: float = 20.0
    attack_preference: str = "nearest"  # nearest, weakest, strongest

    # Movement behavior
    patrol_radius: float = 8.0
    movement_speed: float = 2.0
    chase_speed_multiplier: float = 1.2
    flee_speed_multiplier: float = 1.5

    # Timing and cooldowns
    decision_interval: float = 0.2  # How often to make new decisions
    patrol_change_interval: float = 5.0  # How often to change patrol target
    state_change_cooldown: float = 1.0  # Minimum time between state changes

    # Personality modifiers
    personality: AgentPersonality = AgentPersonality.NEUTRAL
    aggression_level: float = 1.0  # Multiplier for engagement ranges
    caution_level: float = 1.0     # Multiplier for retreat thresholds


@dataclass
class AIAgentState:
    """Runtime AI state for each agent"""

    agent_id: str
    current_state: AIState = AIState.IDLE
    target_id: Optional[str] = None
    target_position: Optional[Tuple[float, float]] = None

    # Timing
    last_decision_time: float = 0.0
    last_state_change: float = 0.0
    last_patrol_change: float = 0.0

    # Movement
    patrol_center: Tuple[float, float] = (0.0, 0.0)
    current_patrol_target: Optional[Tuple[float, float]] = None

    # Combat tracking
    last_seen_enemy_time: float = 0.0
    last_took_damage_time: float = 0.0

    # Statistics
    decisions_made: int = 0
    state_changes: int = 0


class ServerAI:
    """
    Centralized server-side AI system that makes decisions for all agents.

    This system:
    1. Receives authoritative world state each tick
    2. Makes decisions for each AI agent based on server-side logic
    3. Generates actions that are processed internally (no network overhead)
    4. Maintains consistent behavior across all agents
    """

    def __init__(self):
        # Behavior profiles for different agent types
        self.behavior_profiles: Dict[str, BehaviorProfile] = {}

        # Runtime AI state for each agent
        self.agent_states: Dict[str, AIAgentState] = {}

        # System state
        self.last_update_time = 0.0
        self.total_decisions = 0
        self.performance_stats = {
            "decisions_per_second": 0.0,
            "avg_decision_time": 0.0,
            "agents_processed": 0
        }

        # Initialize default behavior profiles
        self._initialize_default_profiles()

    def _initialize_default_profiles(self):
        """Initialize default behavior profiles for standard agent types"""

        # Player AI profile - balanced combat and exploration
        self.behavior_profiles["player"] = BehaviorProfile(
            vision_range=12.0,
            enemy_types={"enemy"},
            attack_range=2.5,  # Match sword_slash server range
            chase_range=20.0,
            flee_health_threshold=25.0,
            patrol_radius=8.0,
            movement_speed=2.0,
            personality=AgentPersonality.NEUTRAL,
            aggression_level=1.0
        )

        # Enemy AI profile - aggressive hunter behavior
        self.behavior_profiles["enemy"] = BehaviorProfile(
            vision_range=10.0,
            enemy_types={"player"},
            attack_range=1.8,  # Match claw server range
            chase_range=15.0,
            flee_health_threshold=15.0,
            patrol_radius=10.0,
            movement_speed=1.8,
            chase_speed_multiplier=1.3,
            personality=AgentPersonality.AGGRESSIVE,
            aggression_level=1.2
        )

        # NPC profile - passive behavior
        self.behavior_profiles["npc"] = BehaviorProfile(
            vision_range=8.0,
            enemy_types=set(),  # NPCs don't attack
            attack_range=0.0,
            chase_range=0.0,
            flee_health_threshold=50.0,
            patrol_radius=5.0,
            movement_speed=1.0,
            personality=AgentPersonality.DEFENSIVE,
            caution_level=1.5
        )

    def register_agent(self, agent_id: str, agent_type: str, x: float, y: float):
        """Register a new agent with the AI system"""
        if agent_id not in self.agent_states:
            self.agent_states[agent_id] = AIAgentState(
                agent_id=agent_id,
                patrol_center=(x, y),
                current_patrol_target=(x, y)
            )
            logger.info(f"[SERVER AI] Registered agent {agent_id[:8]} ({agent_type}) for AI control")

    def unregister_agent(self, agent_id: str):
        """Remove an agent from AI control"""
        if agent_id in self.agent_states:
            del self.agent_states[agent_id]
            logger.info(f"[SERVER AI] Unregistered agent {agent_id[:8]} from AI control")

    def get_behavior_profile(self, agent_type: str) -> BehaviorProfile:
        """Get behavior profile for agent type, with fallback to default"""
        return self.behavior_profiles.get(agent_type, self.behavior_profiles["npc"])

    def update_ai_tick(self, world_state: Dict[str, AgentData],
                       vision_data: Dict[str, List[AgentData]],
                       delta_time: float) -> List[Dict[str, Any]]:
        """
        Main AI update method called each game tick.

        Args:
            world_state: Current state of all agents {agent_id: AgentData}
            vision_data: What each agent can see {agent_id: [visible_agents]}
            delta_time: Time since last update

        Returns:
            List of actions to be processed by the server
        """
        current_time = time.time()
        start_time = current_time
        actions = []
        agents_processed = 0

        # Process each agent that needs AI control
        for agent_id, agent_data in world_state.items():
            if not agent_data.is_alive:
                continue

            # Skip if agent is player-controlled (in future we might check this differently)
            # For now, process all agents with AI
            if agent_id not in self.agent_states:
                self.register_agent(agent_id, agent_data.agent_type, agent_data.x, agent_data.y)

            ai_state = self.agent_states[agent_id]
            behavior = self.get_behavior_profile(agent_data.agent_type)
            visible_entities = vision_data.get(agent_id, [])

            # Check if it's time to make a new decision
            if current_time - ai_state.last_decision_time >= behavior.decision_interval:
                agent_actions = self._process_agent_ai(
                    agent_data, ai_state, behavior, visible_entities, current_time
                )
                actions.extend(agent_actions)
                ai_state.last_decision_time = current_time
                ai_state.decisions_made += 1
                agents_processed += 1

        # Update performance statistics
        processing_time = time.time() - start_time
        self.total_decisions += agents_processed
        self.performance_stats.update({
            "decisions_per_second": agents_processed / max(processing_time, 0.001),
            "avg_decision_time": processing_time / max(agents_processed, 1),
            "agents_processed": agents_processed
        })

        self.last_update_time = current_time
        return actions

    def _process_agent_ai(self, agent: AgentData, ai_state: AIAgentState,
                         behavior: BehaviorProfile, visible_entities: List[AgentData],
                         current_time: float) -> List[Dict[str, Any]]:
        """Process AI logic for a single agent"""
        actions = []

        # Analyze current situation
        enemies_in_sight = self._find_enemies_in_range(agent, visible_entities, behavior)
        nearest_enemy = self._find_nearest_enemy(agent, enemies_in_sight) if enemies_in_sight else None

        # Determine new AI state based on current situation
        new_state = self._determine_ai_state(agent, ai_state, behavior, nearest_enemy, current_time)

        # Change state if needed
        if new_state != ai_state.current_state and self._can_change_state(ai_state, behavior, current_time):
            logger.debug(f"[SERVER AI] Agent {agent.id[:8]} state change: {ai_state.current_state} -> {new_state}")
            ai_state.current_state = new_state
            ai_state.last_state_change = current_time
            ai_state.state_changes += 1

        # Generate actions based on current state
        state_actions = self._execute_ai_state(agent, ai_state, behavior, nearest_enemy, current_time)
        actions.extend(state_actions)

        return actions

    def _find_enemies_in_range(self, agent: AgentData, visible_entities: List[AgentData],
                              behavior: BehaviorProfile) -> List[AgentData]:
        """Find all enemy agents within vision range"""
        enemies = []

        for entity in visible_entities:
            if (entity.agent_type in behavior.enemy_types and
                entity.is_alive and
                entity.id != agent.id):

                distance = self._calculate_distance(agent, entity)
                if distance <= behavior.vision_range:
                    enemies.append(entity)

        return enemies

    def _find_nearest_enemy(self, agent: AgentData, enemies: List[AgentData]) -> Optional[AgentData]:
        """Find the nearest enemy from a list of enemies"""
        if not enemies:
            return None

        nearest = None
        nearest_distance = float('inf')

        for enemy in enemies:
            distance = self._calculate_distance(agent, enemy)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest = enemy

        return nearest

    def _calculate_distance(self, agent1: AgentData, agent2: AgentData) -> float:
        """Calculate distance between two agents"""
        dx = agent2.x - agent1.x
        dy = agent2.y - agent1.y
        return math.sqrt(dx * dx + dy * dy)

    def _determine_ai_state(self, agent: AgentData, ai_state: AIAgentState,
                           behavior: BehaviorProfile, nearest_enemy: Optional[AgentData],
                           current_time: float) -> AIState:
        """Determine what AI state the agent should be in"""

        # Dead agents should be dead
        if not agent.is_alive:
            return AIState.DEAD

        # Low health and took recent damage -> flee
        if (agent.health <= behavior.flee_health_threshold and
            current_time - agent.last_damage_time < 3.0):
            return AIState.FLEE

        # Enemy in range
        if nearest_enemy:
            distance_to_enemy = self._calculate_distance(agent, nearest_enemy)

            # Close enough to attack -> combat
            if distance_to_enemy <= behavior.attack_range:
                return AIState.COMBAT

            # Close enough to chase -> chase
            elif distance_to_enemy <= behavior.chase_range * behavior.aggression_level:
                return AIState.CHASE

        # No immediate threats -> patrol or idle
        if behavior.patrol_radius > 0:
            return AIState.PATROL
        else:
            return AIState.IDLE

    def _can_change_state(self, ai_state: AIAgentState, behavior: BehaviorProfile,
                         current_time: float) -> bool:
        """Check if enough time has passed to allow state change"""
        return current_time - ai_state.last_state_change >= behavior.state_change_cooldown

    def _execute_ai_state(self, agent: AgentData, ai_state: AIAgentState,
                         behavior: BehaviorProfile, nearest_enemy: Optional[AgentData],
                         current_time: float) -> List[Dict[str, Any]]:
        """Execute actions based on current AI state"""
        actions = []

        if ai_state.current_state == AIState.COMBAT:
            actions.extend(self._execute_combat(agent, ai_state, behavior, nearest_enemy))

        elif ai_state.current_state == AIState.CHASE:
            actions.extend(self._execute_chase(agent, ai_state, behavior, nearest_enemy))

        elif ai_state.current_state == AIState.FLEE:
            actions.extend(self._execute_flee(agent, ai_state, behavior, nearest_enemy))

        elif ai_state.current_state == AIState.PATROL:
            actions.extend(self._execute_patrol(agent, ai_state, behavior, current_time))

        # IDLE and DEAD states don't generate actions

        return actions

    def _execute_combat(self, agent: AgentData, ai_state: AIAgentState,
                       behavior: BehaviorProfile, enemy: Optional[AgentData]) -> List[Dict[str, Any]]:
        """Execute combat behavior - attack the enemy"""
        actions = []

        if enemy and self._calculate_distance(agent, enemy) <= behavior.attack_range:
            # Determine attack type based on agent type
            attack_name = self._get_attack_for_agent_type(agent.agent_type)

            actions.append({
                "type": "damage",
                "attacker_id": agent.id,
                "target_id": enemy.id,
                "attack_name": attack_name,
                "position": {"x": agent.x, "y": agent.y}
            })

            ai_state.target_id = enemy.id
            logger.debug(f"[SERVER AI] Agent {agent.id[:8]} attacking {enemy.id[:8]} with {attack_name}")

        return actions

    def _execute_chase(self, agent: AgentData, ai_state: AIAgentState,
                      behavior: BehaviorProfile, enemy: Optional[AgentData]) -> List[Dict[str, Any]]:
        """Execute chase behavior - move toward the enemy"""
        actions = []

        if enemy:
            # Calculate movement toward enemy
            dx = enemy.x - agent.x
            dy = enemy.y - agent.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 0:
                # Normalize and apply chase speed
                speed = behavior.movement_speed * behavior.chase_speed_multiplier
                move_x = (dx / distance) * speed
                move_y = (dy / distance) * speed

                actions.append({
                    "type": "move",
                    "agent_id": agent.id,
                    "velocity_x": move_x,
                    "velocity_y": move_y,
                    "rotation": math.degrees(math.atan2(dy, dx))
                })

                ai_state.target_id = enemy.id
                ai_state.target_position = (enemy.x, enemy.y)

                logger.debug(f"[SERVER AI] Agent {agent.id[:8]} chasing {enemy.id[:8]} at distance {distance:.1f}")

        return actions

    def _execute_flee(self, agent: AgentData, ai_state: AIAgentState,
                     behavior: BehaviorProfile, enemy: Optional[AgentData]) -> List[Dict[str, Any]]:
        """Execute flee behavior - move away from threats"""
        actions = []

        # Move away from enemy or toward patrol center
        if enemy:
            # Move away from enemy
            dx = agent.x - enemy.x
            dy = agent.y - enemy.y
        else:
            # Move toward safety (patrol center)
            dx = ai_state.patrol_center[0] - agent.x
            dy = ai_state.patrol_center[1] - agent.y

        distance = math.sqrt(dx * dx + dy * dy)
        if distance > 0:
            speed = behavior.movement_speed * behavior.flee_speed_multiplier
            move_x = (dx / distance) * speed
            move_y = (dy / distance) * speed

            actions.append({
                "type": "move",
                "agent_id": agent.id,
                "velocity_x": move_x,
                "velocity_y": move_y,
                "rotation": math.degrees(math.atan2(dy, dx))
            })

            logger.debug(f"[SERVER AI] Agent {agent.id[:8]} fleeing with {agent.health:.1f} health")

        return actions

    def _execute_patrol(self, agent: AgentData, ai_state: AIAgentState,
                       behavior: BehaviorProfile, current_time: float) -> List[Dict[str, Any]]:
        """Execute patrol behavior - move around patrol area"""
        actions = []

        # Check if we need a new patrol target
        if (ai_state.current_patrol_target is None or
            current_time - ai_state.last_patrol_change >= behavior.patrol_change_interval or
            self._calculate_distance_to_point(agent, ai_state.current_patrol_target) < 1.0):

            # Generate new random patrol target around patrol center
            angle = random.random() * 2 * math.pi
            distance = random.random() * behavior.patrol_radius

            target_x = ai_state.patrol_center[0] + math.cos(angle) * distance
            target_y = ai_state.patrol_center[1] + math.sin(angle) * distance

            ai_state.current_patrol_target = (target_x, target_y)
            ai_state.last_patrol_change = current_time

        # Move toward patrol target
        if ai_state.current_patrol_target:
            dx = ai_state.current_patrol_target[0] - agent.x
            dy = ai_state.current_patrol_target[1] - agent.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 0.5:  # Don't move if very close
                move_x = (dx / distance) * behavior.movement_speed
                move_y = (dy / distance) * behavior.movement_speed

                actions.append({
                    "type": "move",
                    "agent_id": agent.id,
                    "velocity_x": move_x,
                    "velocity_y": move_y,
                    "rotation": math.degrees(math.atan2(dy, dx))
                })

        return actions

    def _calculate_distance_to_point(self, agent: AgentData, point: Tuple[float, float]) -> float:
        """Calculate distance from agent to a point"""
        dx = point[0] - agent.x
        dy = point[1] - agent.y
        return math.sqrt(dx * dx + dy * dy)

    def _get_attack_for_agent_type(self, agent_type: str) -> str:
        """Get the appropriate attack name for an agent type"""
        attack_mapping = {
            "player": "sword_slash",
            "enemy": "claw",
            "npc": "punch"
        }
        return attack_mapping.get(agent_type, "punch")

    def get_statistics(self) -> Dict[str, Any]:
        """Get AI system performance statistics"""
        return {
            "total_agents": len(self.agent_states),
            "total_decisions": self.total_decisions,
            "performance": self.performance_stats,
            "agent_state_distribution": self._get_state_distribution(),
            "last_update": self.last_update_time
        }

    def _get_state_distribution(self) -> Dict[str, int]:
        """Get distribution of agents across different AI states"""
        distribution = {}
        for state in AIState:
            distribution[state.value] = 0

        for ai_state in self.agent_states.values():
            distribution[ai_state.current_state.value] += 1

        return distribution