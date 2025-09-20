from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum
import random
import logging
import math

from src.agents.agent import Agent, AgentState
from src.world.world import Vector2

logger = logging.getLogger(__name__)


class EnemyType(Enum):
    NORMAL = "normal"
    ELITE = "elite"
    BOSS = "boss"
    MINIBOSS = "miniboss"
    SWARM = "swarm"
    RAID_BOSS = "raid_boss"


class EnemyBehavior(Enum):
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    PASSIVE = "passive"
    TERRITORIAL = "territorial"
    PATROL = "patrol"
    AMBUSH = "ambush"


@dataclass
class CombatMechanic:
    """Special combat mechanics for enemies"""
    name: str
    description: str
    trigger_condition: str
    effect: Dict[str, Any]
    cooldown: float = 10.0
    last_used: float = 0.0


class Enemy(Agent):
    """Enemy entity with combat AI and special mechanics"""

    def __init__(self, name: str, enemy_type: EnemyType = EnemyType.NORMAL,
                 level: int = 1, position: Vector2 = None):
        super().__init__(name)
        self.enemy_type = enemy_type
        self.level = level
        self.character_class = "Enemy"

        if position:
            self.position = position

        # Enemy-specific attributes
        self.behavior = self._determine_behavior()
        self.aggro_range = self._calculate_aggro_range()
        self.leash_range = 100.0  # Max distance from spawn point
        self.spawn_position = Vector2(self.position.x, self.position.y)

        # Combat attributes
        self.damage_multiplier = self._calculate_damage_multiplier()
        self.health_multiplier = self._calculate_health_multiplier()
        self.experience_reward = self._calculate_experience_reward()
        self.loot_table: List[Dict[str, Any]] = []

        # Enemy mechanics (for bosses and elites)
        self.combat_mechanics: List[CombatMechanic] = []
        self.phase_thresholds: List[float] = []  # Health percentages for phase changes
        self.current_phase = 0

        # Combat state
        self.threat_table: Dict[str, float] = {}  # agent_id -> threat value
        self.current_target: Optional[str] = None

        # Weaknesses and resistances
        self.weaknesses: List[str] = []
        self.resistances: List[str] = []

        # Initialize based on type
        self._initialize_by_type()
        self._initialize_stats()

        logger.info(f"Enemy {self.name} ({enemy_type.value}) created at level {level}")

    def _determine_behavior(self) -> EnemyBehavior:
        """Determine enemy behavior based on type"""
        if self.enemy_type == EnemyType.NORMAL:
            return random.choice([EnemyBehavior.AGGRESSIVE, EnemyBehavior.TERRITORIAL])
        elif self.enemy_type == EnemyType.ELITE:
            return EnemyBehavior.AGGRESSIVE
        elif self.enemy_type in [EnemyType.BOSS, EnemyType.RAID_BOSS]:
            return EnemyBehavior.AGGRESSIVE
        elif self.enemy_type == EnemyType.SWARM:
            return EnemyBehavior.AGGRESSIVE
        else:
            return EnemyBehavior.TERRITORIAL

    def _calculate_aggro_range(self) -> float:
        """Calculate aggro range based on enemy type"""
        base_range = 30.0
        if self.enemy_type == EnemyType.BOSS:
            return base_range * 2
        elif self.enemy_type == EnemyType.ELITE:
            return base_range * 1.5
        elif self.enemy_type == EnemyType.SWARM:
            return base_range * 0.7
        return base_range

    def _calculate_damage_multiplier(self) -> float:
        """Calculate damage multiplier based on enemy type"""
        multipliers = {
            EnemyType.NORMAL: 1.0,
            EnemyType.ELITE: 1.5,
            EnemyType.MINIBOSS: 2.0,
            EnemyType.BOSS: 3.0,
            EnemyType.RAID_BOSS: 5.0,
            EnemyType.SWARM: 0.5
        }
        return multipliers.get(self.enemy_type, 1.0)

    def _calculate_health_multiplier(self) -> float:
        """Calculate health multiplier based on enemy type"""
        multipliers = {
            EnemyType.NORMAL: 1.0,
            EnemyType.ELITE: 3.0,
            EnemyType.MINIBOSS: 10.0,
            EnemyType.BOSS: 50.0,
            EnemyType.RAID_BOSS: 200.0,
            EnemyType.SWARM: 0.3
        }
        return multipliers.get(self.enemy_type, 1.0)

    def _calculate_experience_reward(self) -> int:
        """Calculate experience reward for defeating this enemy"""
        base_exp = 10 * self.level
        multipliers = {
            EnemyType.NORMAL: 1.0,
            EnemyType.ELITE: 3.0,
            EnemyType.MINIBOSS: 10.0,
            EnemyType.BOSS: 25.0,
            EnemyType.RAID_BOSS: 100.0,
            EnemyType.SWARM: 0.5
        }
        return int(base_exp * multipliers.get(self.enemy_type, 1.0))

    def _initialize_by_type(self):
        """Initialize enemy based on type"""
        if self.enemy_type == EnemyType.BOSS:
            self._setup_boss()
        elif self.enemy_type == EnemyType.RAID_BOSS:
            self._setup_raid_boss()
        elif self.enemy_type == EnemyType.ELITE:
            self._setup_elite()
        elif self.enemy_type == EnemyType.SWARM:
            self._setup_swarm()

    def _setup_boss(self):
        """Setup boss-specific attributes"""
        # Add phase thresholds
        self.phase_thresholds = [0.75, 0.50, 0.25]

        # Add boss mechanics
        self.combat_mechanics.append(CombatMechanic(
            name="Enrage",
            description="Boss damage increases when health is low",
            trigger_condition="health_below_25",
            effect={'damage_increase': 2.0, 'speed_increase': 1.5}
        ))

        self.combat_mechanics.append(CombatMechanic(
            name="Area Attack",
            description="Damages all nearby enemies",
            trigger_condition="timer",
            effect={'radius': 50, 'damage': self.level * 10},
            cooldown=15.0
        ))

        # Random weaknesses and resistances
        damage_types = ['fire', 'ice', 'lightning', 'physical', 'poison']
        self.weaknesses = random.sample(damage_types, k=1)
        self.resistances = random.sample([d for d in damage_types if d not in self.weaknesses], k=2)

    def _setup_raid_boss(self):
        """Setup raid boss with complex mechanics"""
        self._setup_boss()  # Start with boss setup

        # Additional raid mechanics
        self.combat_mechanics.append(CombatMechanic(
            name="Raid Wipe",
            description="Massive damage to all players if not interrupted",
            trigger_condition="phase_change",
            effect={'damage': self.level * 100, 'interruptible': True},
            cooldown=60.0
        ))

        self.combat_mechanics.append(CombatMechanic(
            name="Summon Adds",
            description="Summons additional enemies",
            trigger_condition="health_threshold",
            effect={'summon_count': 5, 'summon_type': 'minion'},
            cooldown=30.0
        ))

    def _setup_elite(self):
        """Setup elite enemy attributes"""
        # Elite enemies have one special ability
        self.combat_mechanics.append(CombatMechanic(
            name="Power Strike",
            description="Powerful attack with knockback",
            trigger_condition="timer",
            effect={'damage_multiplier': 2.0, 'knockback': 10},
            cooldown=8.0
        ))

        # Single weakness, single resistance
        damage_types = ['fire', 'ice', 'lightning', 'physical', 'poison']
        self.weaknesses = [random.choice(damage_types)]
        self.resistances = [random.choice([d for d in damage_types if d != self.weaknesses[0]])]

    def _setup_swarm(self):
        """Setup swarm enemy attributes"""
        # Swarm enemies are weak but attack in groups
        self.personality.social = 0.9  # High social for group behavior
        self.aggro_range *= 1.5  # Larger aggro range to coordinate attacks

    def _initialize_stats(self):
        """Initialize enemy stats based on level and type"""
        # Scale stats with level
        self.stats.max_health = int(100 * self.level * self.health_multiplier)
        self.stats.health = self.stats.max_health
        self.stats.strength = int(10 + self.level * 2 * self.damage_multiplier)
        self.stats.constitution = int(10 + self.level * 1.5)
        self.stats.dexterity = int(10 + self.level)

        # Bosses have mana for special abilities
        if self.enemy_type in [EnemyType.BOSS, EnemyType.RAID_BOSS]:
            self.stats.max_mana = 100 * self.level
            self.stats.mana = self.stats.max_mana
            self.stats.intelligence = 10 + self.level * 2

    def update(self, delta_time: float, world, request_manager):
        """Update enemy behavior"""
        # Base agent update
        super().update(delta_time, world, request_manager)

        # Combat AI
        if self.state == AgentState.COMBAT:
            self._combat_update(delta_time, world, request_manager)
        else:
            self._patrol_update(delta_time, world, request_manager)

        # Check for phase transitions (bosses)
        if self.phase_thresholds:
            self._check_phase_transition()

        # Leash check (return to spawn if too far)
        if self.position.distance_to(self.spawn_position) > self.leash_range:
            self._return_to_spawn()

    def _combat_update(self, delta_time: float, world, request_manager):
        """Update combat behavior"""
        if not self.current_target:
            self._select_target(world)

        if self.current_target:
            target_agent = world.agents.get(self.current_target)
            if target_agent:
                distance = self.position.distance_to(target_agent.position)

                if distance > self.aggro_range * 1.5:
                    # Target out of range, drop aggro
                    self.drop_target(self.current_target)
                elif distance > 5.0:
                    # Move towards target
                    self._move_towards_target(target_agent)
                else:
                    # In attack range, execute attack
                    self._execute_attack(target_agent, request_manager)

                # Check and execute combat mechanics
                self._execute_combat_mechanics(delta_time, world, request_manager)

    def _patrol_update(self, delta_time: float, world, request_manager):
        """Update patrol/idle behavior"""
        # Check for nearby agents to aggro
        nearby_agents = world.get_nearby_agents(self.position, self.aggro_range)

        for agent in nearby_agents:
            if self._should_aggro(agent):
                self.enter_combat(agent.id)
                break

        # Patrol or wander behavior
        if self.behavior == EnemyBehavior.PATROL:
            self._patrol_behavior(delta_time)

    def _should_aggro(self, agent: Agent) -> bool:
        """Determine if should aggro on an agent"""
        if agent.id == self.id:
            return False

        if self.behavior == EnemyBehavior.PASSIVE:
            return False

        if self.behavior == EnemyBehavior.AGGRESSIVE:
            return True

        if self.behavior == EnemyBehavior.TERRITORIAL:
            # Aggro if agent is too close to spawn
            return agent.position.distance_to(self.spawn_position) < self.aggro_range

        return False

    def _select_target(self, world):
        """Select target based on threat table"""
        if not self.threat_table:
            return

        # Target with highest threat
        self.current_target = max(self.threat_table.items(), key=lambda x: x[1])[0]

    def _move_towards_target(self, target: Agent):
        """Move towards combat target"""
        direction_x = target.position.x - self.position.x
        direction_y = target.position.y - self.position.y
        distance = math.sqrt(direction_x ** 2 + direction_y ** 2)

        if distance > 0:
            self.velocity = Vector2(direction_x / distance, direction_y / distance)
            self.state = AgentState.MOVING

    def _execute_attack(self, target: Agent, request_manager):
        """Execute attack on target"""
        damage = self.stats.strength * random.uniform(0.8, 1.2)

        request = {
            'type': 'damage',
            'source': self.id,
            'target': target.id,
            'amount': damage,
            'damage_type': 'physical'
        }
        request_manager.add_request(request)

    def _execute_combat_mechanics(self, delta_time: float, world, request_manager):
        """Execute special combat mechanics"""
        import time
        current_time = time.time()

        for mechanic in self.combat_mechanics:
            if current_time - mechanic.last_used < mechanic.cooldown:
                continue

            if self._check_mechanic_trigger(mechanic):
                self._execute_mechanic(mechanic, world, request_manager)
                mechanic.last_used = current_time

    def _check_mechanic_trigger(self, mechanic: CombatMechanic) -> bool:
        """Check if a combat mechanic should trigger"""
        if mechanic.trigger_condition == "timer":
            return True  # Cooldown already checked

        if mechanic.trigger_condition == "health_below_25":
            return (self.stats.health / self.stats.max_health) < 0.25

        if mechanic.trigger_condition == "phase_change":
            return hasattr(self, '_phase_changed') and self._phase_changed

        return False

    def _execute_mechanic(self, mechanic: CombatMechanic, world, request_manager):
        """Execute a combat mechanic"""
        logger.info(f"{self.name} executing mechanic: {mechanic.name}")

        effect = mechanic.effect
        if 'damage' in effect:
            # Area damage mechanic
            nearby_agents = world.get_nearby_agents(self.position, effect.get('radius', 50))
            for agent in nearby_agents:
                if agent.id != self.id:
                    request = {
                        'type': 'damage',
                        'source': self.id,
                        'target': agent.id,
                        'amount': effect['damage'],
                        'damage_type': 'magical'
                    }
                    request_manager.add_request(request)

    def _check_phase_transition(self):
        """Check for boss phase transitions"""
        if not self.phase_thresholds:
            return

        health_percent = self.stats.health / self.stats.max_health
        new_phase = len(self.phase_thresholds)

        for i, threshold in enumerate(self.phase_thresholds):
            if health_percent > threshold:
                new_phase = i
                break

        if new_phase != self.current_phase:
            self.current_phase = new_phase
            self._phase_changed = True
            logger.info(f"{self.name} entering phase {self.current_phase}")

    def _return_to_spawn(self):
        """Return to spawn position and reset"""
        self.position = Vector2(self.spawn_position.x, self.spawn_position.y)
        self.state = AgentState.IDLE
        self.current_target = None
        self.threat_table.clear()
        self.stats.health = self.stats.max_health
        logger.debug(f"{self.name} returning to spawn (leashed)")

    def _patrol_behavior(self, delta_time: float):
        """Basic patrol behavior"""
        if random.random() < 0.01:  # 1% chance to change direction
            angle = random.uniform(0, 2 * math.pi)
            self.velocity = Vector2(math.cos(angle), math.sin(angle))
            self.state = AgentState.MOVING

    def enter_combat(self, agent_id: str):
        """Enter combat with an agent"""
        self.state = AgentState.COMBAT
        self.current_target = agent_id
        self.add_threat(agent_id, 100)
        logger.debug(f"{self.name} entering combat with {agent_id}")

    def add_threat(self, agent_id: str, amount: float):
        """Add threat for an agent"""
        current_threat = self.threat_table.get(agent_id, 0)
        self.threat_table[agent_id] = current_threat + amount

    def drop_target(self, agent_id: str):
        """Drop a target from threat table"""
        if agent_id in self.threat_table:
            del self.threat_table[agent_id]

        if self.current_target == agent_id:
            self.current_target = None
            if not self.threat_table:
                self.state = AgentState.IDLE

    def take_damage(self, amount: float, source_id: str, damage_type: str = 'physical'):
        """Take damage and update threat"""
        # Apply resistances/weaknesses
        if damage_type in self.weaknesses:
            amount *= 1.5
        elif damage_type in self.resistances:
            amount *= 0.5

        self.stats.health -= amount
        self.add_threat(source_id, amount * 1.5)

        if self.stats.health <= 0:
            self._handle_death()

    def _handle_death(self):
        """Handle enemy death"""
        logger.info(f"{self.name} has been defeated!")
        # Death handling would trigger loot drops, experience rewards, etc.