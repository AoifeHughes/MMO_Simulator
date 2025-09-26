import logging
import math
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from client.agent_map import AgentMap
from shared.collision import CollisionDetector
from shared.constants import (
    DEFAULT_AGENT_SPEED,
    DEFAULT_VISION_ANGLE,
    DEFAULT_VISION_RANGE,
)
from shared.math_utils import normalize_angle
from shared.pathfinding import Pathfinder
from world.tiles import TileType

if TYPE_CHECKING:
    from shared.personality import Personality

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, agent_id: str, x: float, y: float, agent_type: str, personality: Optional["Personality"] = None):
        self.id = agent_id
        self.x = x
        self.y = y
        self.rotation = 0.0
        self.agent_type = agent_type  # Kept for server compatibility during transition
        self.personality = personality  # New personality system

        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.speed = DEFAULT_AGENT_SPEED

        self.vision_range = DEFAULT_VISION_RANGE
        self.vision_angle = DEFAULT_VISION_ANGLE

        self.health = 100.0
        self.max_health = 100.0
        self.is_alive = True

        self.visible_entities: List[Dict[str, Any]] = []
        self.last_update = time.time()

        # Intention change cooldown system
        self.current_intention: Optional[str] = None
        self.last_intention_change: float = (
            time.time() - 3.0
        )  # Allow immediate first intention change
        self.intention_cooldown: float = 2.0  # Increased to 2 seconds for better commitment
        self.base_intention_cooldown: float = 2.0  # Base cooldown for normal situations
        self.combat_intention_cooldown: float = 1.5  # Shorter cooldown in combat for responsiveness
        self.emergency_intention_cooldown: float = 0.8  # Even shorter for emergencies

        # Collision detection (will be set when world bounds are known)
        self.collision_detector: Optional[CollisionDetector] = None
        self.world_bounds: Optional[Tuple[int, int]] = None

        # Pathfinding and mapping
        self.agent_map: Optional[AgentMap] = None
        self.pathfinder = Pathfinder()
        self.current_path: Optional[List[Tuple[float, float]]] = None
        self.current_waypoint: Optional[Tuple[float, float]] = None
        self.waypoint_threshold = 0.5

        # Behavior tree system
        self.behavior_tree = None
        self.use_behavior_tree = False
        self.has_initial_map_data = False  # Flag to ensure map data before behavior tree execution
        self.last_position = (x, y)
        self.last_position_time = time.time()

        # Action tracking for conditions
        self.current_target: Optional[Tuple[float, float]] = None

        # Server game data (received from server)
        self.server_game_data: Optional[Dict[str, Any]] = None

        # Action manager for new request-response system (will be set by client)
        self.action_manager: Optional["ActionManager"] = None

        # Behavior tree provider for dependency injection (will be set by client/scenario)
        self.behavior_tree_provider: Optional["BehaviorTreeProvider"] = None

        # Target management system for consistent target selection
        self.target_manager: Optional["TargetManager"] = None

        # Movement management system for smooth movement
        self.movement_manager: Optional["MovementManager"] = None

        # Position reconciliation system to fix sync issues
        self.position_reconciler: Optional["PositionReconciler"] = None

        # Movement validation system to prevent server conflicts
        self.movement_validator: Optional["MovementValidator"] = None

    @abstractmethod
    def update(self, delta_time: float):
        pass

    @abstractmethod
    def perceive(self, visible_entities: List[Dict[str, Any]]):
        pass

    @abstractmethod
    def decide(self) -> Optional[Dict[str, Any]]:
        pass

    def move(self, delta_time: float):
        # Calculate intended new position
        new_x = self.x + self.velocity_x * delta_time
        new_y = self.y + self.velocity_y * delta_time

        # Apply collision detection if available
        if self.collision_detector:
            new_x, new_y = self.collision_detector.resolve_movement_collision(
                (self.x, self.y), (new_x, new_y)
            )

        # Update position reconciler with prediction
        if self.position_reconciler:
            self.position_reconciler.update_prediction(
                new_x, new_y, self.rotation, self.velocity_x, self.velocity_y
            )
            # Get reconciled display position
            display_x, display_y, display_rotation = self.position_reconciler.update(delta_time)
            self.x = display_x
            self.y = display_y
            self.rotation = display_rotation
        else:
            # Fallback to direct position update
            self.x = new_x
            self.y = new_y

    def set_velocity(self, vx: float, vy: float):
        self.velocity_x = vx
        self.velocity_y = vy

    def set_position(self, x: float, y: float):
        # Apply boundary clamping if collision detector is available
        if self.collision_detector:
            x, y = self.collision_detector.clamp_to_bounds(x, y)
        self.x = x
        self.y = y

    def set_world_bounds(self, width: int, height: int):
        """Set the world bounds and initialize collision detector and agent map"""
        self.world_bounds = (width, height)
        self.collision_detector = CollisionDetector(width, height)
        self.agent_map = AgentMap(width, height)

        # Update movement validator bounds
        if self.movement_validator:
            self.movement_validator.set_world_bounds(width, height)

    def set_server_game_data(self, game_data: Dict[str, Any]):
        """Set server game data for agent decision-making"""
        self.server_game_data = game_data
        logger.info(f"[AGENT] Agent {self.id[:8]} received server game data with {len(game_data.get('attacks', {}))} attacks")

    def get_attack_data(self, attack_name: str) -> Optional[Dict[str, Any]]:
        """Get attack data from server for decision-making"""
        if not self.server_game_data or 'attacks' not in self.server_game_data:
            return None
        return self.server_game_data['attacks'].get(attack_name)

    def get_available_attacks(self) -> List[str]:
        """Get list of attacks available to this agent type"""
        if not self.server_game_data or 'character_attacks' not in self.server_game_data:
            return []
        return self.server_game_data['character_attacks'].get(self.agent_type, [])

    def can_change_intention(self) -> bool:
        """Check if enough time has passed to allow intention change"""
        current_time = time.time()
        return (current_time - self.last_intention_change) >= self.intention_cooldown

    def set_intention(self, new_intention: str, force: bool = False) -> bool:
        """Set a new intention with cooldown protection"""
        current_time = time.time()

        # Allow setting intention if it's the same as current (no change needed)
        if self.current_intention == new_intention:
            return True

        # Check cooldown unless forced
        if not force and not self.can_change_intention():
            # Still on cooldown, keep current intention
            remaining = self.intention_cooldown - (
                current_time - self.last_intention_change
            )
            logger.debug(
                f"Agent {self.id[:8]} intention change blocked - "
                f"{remaining:.1f}s remaining on cooldown"
            )
            return False

        # Allow intention change
        old_intention = self.current_intention
        self.current_intention = new_intention
        self.last_intention_change = current_time

        if old_intention != new_intention:
            logger.debug(
                f"Agent {self.id[:8]} intention changed: "
                f"{old_intention} → {new_intention}"
            )

        return True

    def get_intention(self) -> Optional[str]:
        """Get current intention"""
        return self.current_intention

    def force_intention(self, new_intention: str):
        """Force an intention change bypassing cooldown (for emergencies)"""
        self.set_intention(new_intention, force=True)

    def adjust_intention_cooldown(self, context: str = "normal"):
        """
        Adjust intention cooldown based on current context.

        Args:
            context: "normal", "combat", "emergency", or "patrol"
        """
        if context == "emergency":
            self.intention_cooldown = self.emergency_intention_cooldown
        elif context == "combat":
            self.intention_cooldown = self.combat_intention_cooldown
        elif context == "patrol":
            self.intention_cooldown = self.base_intention_cooldown * 1.5  # Longer for stable patrolling
        else:
            self.intention_cooldown = self.base_intention_cooldown

        logger.debug(f"Agent {self.id[:8]} intention cooldown adjusted to {self.intention_cooldown}s for context: {context}")

    def check_health_recovery(self):
        """Check if health has recovered and restore normal intention cooldown"""
        # If health is above 40% (healthy), restore normal intention cooldown
        # This provides hysteresis - low health at 20%, recovery at 40%
        if hasattr(self, "max_health") and self.health > (self.max_health * 0.4):
            if self.intention_cooldown > self.base_intention_cooldown:
                self.intention_cooldown = self.base_intention_cooldown

    def set_rotation(self, rotation: float):
        self.rotation = normalize_angle(rotation)

    def take_damage(self, damage: float):
        self.health = max(0, self.health - damage)

    def heal(self, amount: float):
        self.health = min(self.max_health, self.health + amount)

    def is_alive(self) -> bool:
        return self.health > 0

    def get_position(self) -> Tuple[float, float]:
        return self.x, self.y

    # Pathfinding methods
    def find_path_to(self, target_x: float, target_y: float) -> bool:
        """Find path to target position using agent's known map.
        Returns True if path found."""
        if not self.agent_map:
            return False

        path = self.pathfinder.find_path(
            self.agent_map, (self.x, self.y), (target_x, target_y)
        )

        if path:
            self.current_path = self.pathfinder.simplify_path(path, max_waypoints=8)
            self.current_waypoint = self.pathfinder.get_next_waypoint(
                self.current_path, (self.x, self.y), self.waypoint_threshold
            )
            return True

        return False

    def find_path_to_exploration_frontier(self) -> bool:
        """Find path to nearest exploration frontier. Returns True if path found."""
        if not self.agent_map:
            return False

        path = self.pathfinder.find_path_to_nearest_frontier(
            self.agent_map, (self.x, self.y)
        )

        if path:
            self.current_path = self.pathfinder.simplify_path(path, max_waypoints=8)
            self.current_waypoint = self.pathfinder.get_next_waypoint(
                self.current_path, (self.x, self.y), self.waypoint_threshold
            )
            return True

        return False

    def update_pathfinding(self, delta_time: float):
        """Update pathfinding state - call this in agent update loops"""
        if not self.current_path or not self.current_waypoint:
            return

        # Check if we've reached the current waypoint
        current_pos = (self.x, self.y)
        distance_to_waypoint = math.sqrt(
            (self.current_waypoint[0] - current_pos[0]) ** 2
            + (self.current_waypoint[1] - current_pos[1]) ** 2
        )

        if distance_to_waypoint <= self.waypoint_threshold:
            # Move to next waypoint
            self.current_waypoint = self.pathfinder.get_next_waypoint(
                self.current_path, current_pos, self.waypoint_threshold
            )

            if not self.current_waypoint:
                # Path complete
                self.current_path = None
                self.velocity_x = 0
                self.velocity_y = 0
                return

        # Set velocity toward current waypoint
        if self.current_waypoint:
            dx = self.current_waypoint[0] - self.x
            dy = self.current_waypoint[1] - self.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance > 0:
                self.velocity_x = (dx / distance) * self.speed
                self.velocity_y = (dy / distance) * self.speed
                self.rotation = math.degrees(math.atan2(dy, dx))

    def move_direct(self, target_x: float, target_y: float):
        """Direct movement without pathfinding (fallback behavior)"""
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 0:
            self.velocity_x = (dx / distance) * self.speed
            self.velocity_y = (dy / distance) * self.speed
            self.rotation = math.degrees(math.atan2(dy, dx))

    def stop_movement(self):
        """Stop all movement and clear current path"""
        self.velocity_x = 0
        self.velocity_y = 0
        self.current_path = None
        self.current_waypoint = None

    def discover_terrain_from_vision(
        self, terrain_data: Dict[Tuple[int, int], TileType]
    ):
        """Update agent map with terrain discovered through vision"""
        if not self.agent_map:
            return

        # Discover terrain within vision range
        self.agent_map.discover_area(self.x, self.y, self.vision_range, terrain_data)

        # Update movement validator terrain cache
        if self.movement_validator and terrain_data:
            self.movement_validator.update_terrain_cache(terrain_data)

        # Mark that we've received initial map data
        if not self.has_initial_map_data and terrain_data:
            self.has_initial_map_data = True
            logger.debug(f"Agent {self.id[:8]} received initial map data")

    def _has_sufficient_terrain_coverage(self, required_coverage: float = 0.3) -> bool:
        """Check if agent has sufficient terrain coverage around their position for safe behavior tree execution"""
        if not self.agent_map:
            return False

        # Check coverage in a small radius around agent (fishing range)
        search_radius = 2  # 2-tile radius around agent
        known_tiles_count = 0
        total_tiles = 0

        for dy in range(-search_radius, search_radius + 1):
            for dx in range(-search_radius, search_radius + 1):
                check_x = int(self.x) + dx
                check_y = int(self.y) + dy

                if self.agent_map.is_valid_position(check_x, check_y):
                    total_tiles += 1
                    if self.agent_map.is_tile_known(check_x, check_y):
                        known_tiles_count += 1

        if total_tiles == 0:
            return False

        coverage = known_tiles_count / total_tiles
        return coverage >= required_coverage

    def get_state(self) -> Dict[str, Any]:
        state = {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "rotation": self.rotation,
            "type": self.agent_type,
            "agent_type": self.agent_type,  # Add for behavior tree compatibility
            "health": self.health,
            "velocity_x": self.velocity_x,
            "velocity_y": self.velocity_y,
        }

        # Add pathfinding information if available
        if self.agent_map:
            state.update(
                {
                    "map_completion": self.agent_map.get_map_completion_percentage(),
                    "has_path": self.current_path is not None,
                    "current_waypoint": self.current_waypoint,
                }
            )

        return state

    def update_from_state(self, state: Dict[str, Any]):
        x = state.get("x", self.x)
        y = state.get("y", self.y)
        rotation = state.get("rotation", self.rotation)

        # Update through position reconciler if available
        if self.position_reconciler:
            import time
            self.position_reconciler.set_server_position(x, y, rotation, time.time())
        else:
            # Direct update for fallback
            self.x = x
            self.y = y
            self.rotation = rotation

        self.health = state.get("health", self.health)
        self.velocity_x = state.get("velocity_x", 0)
        self.velocity_y = state.get("velocity_y", 0)

    # Behavior Tree Support Methods
    def set_behavior_tree(self, behavior_tree):
        """Set the behavior tree for this agent and enable behavior tree mode"""
        self.behavior_tree = behavior_tree
        self.use_behavior_tree = True

        # Initialize target manager when behavior tree is set
        self._initialize_target_manager()

        # Initialize movement manager when behavior tree is set
        self._initialize_movement_manager()

        logger.debug(
            f"Agent {self.id[:8]} set to use behavior tree: {behavior_tree.name}"
        )

    def set_behavior_tree_provider(self, provider: Optional["BehaviorTreeProvider"]):
        """
        Set the behavior tree provider for this agent.

        Args:
            provider: Provider that can create behavior trees for this agent
        """
        from client.behavior_tree.provider import BehaviorTreeProvider
        self.behavior_tree_provider = provider
        logger.debug(f"Agent {self.id[:8]} behavior tree provider set: {provider is not None}")

    def initialize_behavior_tree_from_provider(self, **kwargs) -> bool:
        """
        Initialize behavior tree using the current provider.

        Args:
            **kwargs: Additional parameters for tree creation

        Returns:
            True if tree was successfully initialized, False otherwise
        """
        if not self.behavior_tree_provider:
            logger.warning(f"Agent {self.id[:8]} has no behavior tree provider")
            return False

        try:
            tree = self.behavior_tree_provider.get_behavior_tree(
                self.agent_type, self.x, self.y, **kwargs
            )
            if tree:
                self.set_behavior_tree(tree)
                return True
            else:
                logger.warning(f"Provider returned no behavior tree for {self.agent_type}")
                return False
        except Exception as e:
            logger.error(f"Error initializing behavior tree from provider for agent {self.id[:8]}: {e}")
            return False

    def disable_behavior_tree(self):
        """Disable behavior tree mode and revert to legacy behavior"""
        self.use_behavior_tree = False
        if self.behavior_tree:
            self.behavior_tree.reset()
        logger.debug(f"Agent {self.id[:8]} disabled behavior tree mode")

    def update_behavior_tree(self, delta_time: float):
        """Update the agent using the behavior tree system"""
        if not self.behavior_tree or not self.use_behavior_tree:
            return

        # Wait for initial map data before executing behavior tree
        if not self.has_initial_map_data:
            logger.debug(f"Agent {self.id[:8]} waiting for initial map data before behavior tree execution")
            return

        # Ensure sufficient terrain coverage around agent before allowing behavior tree execution
        if self.agent_map and not self._has_sufficient_terrain_coverage():
            logger.debug(f"Agent {self.id[:8]} waiting for sufficient terrain coverage before behavior tree execution")
            return

        # Update position tracking for stuck detection
        current_time = time.time()
        if current_time - self.last_position_time > 2.0:
            self.last_position = (self.x, self.y)
            self.last_position_time = current_time

        # Update pathfinding (still needed for path-based movement)
        self.update_pathfinding(delta_time)

        # Check for health recovery to restore normal intention cooldown
        self.check_health_recovery()

        # Execute behavior tree
        try:
            status = self.behavior_tree.update(self, delta_time)
            logger.debug(f"Agent {self.id[:8]} behavior tree status: {status.value}")
        except Exception as e:
            logger.error(f"Error updating behavior tree for agent {self.id[:8]}: {e}")

        # Apply movement using velocity system
        self.move(delta_time)

    def get_behavior_tree_debug_info(self) -> Optional[Dict[str, Any]]:
        """Get debug information about the current behavior tree state"""
        if not self.behavior_tree:
            return None

        return self.behavior_tree.get_debug_info(self)

    # Utility methods for behavior tree nodes
    def set_target(self, target_x: float, target_y: float):
        """Set the current target position"""
        self.current_target = (target_x, target_y)

    def clear_target(self):
        """Clear the current target"""
        self.current_target = None

    def get_distance_to_target(self) -> Optional[float]:
        """Get distance to current target, or None if no target"""
        if not self.current_target:
            return None

        dx = self.current_target[0] - self.x
        dy = self.current_target[1] - self.y
        return math.sqrt(dx * dx + dy * dy)

    def move_towards_target(
        self, target_x: float, target_y: float, speed_multiplier: float = 1.0
    ):
        """Move towards a target position with optional speed multiplier"""
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance > 0:
            speed = self.speed * speed_multiplier
            self.velocity_x = (dx / distance) * speed
            self.velocity_y = (dy / distance) * speed
            self.rotation = math.degrees(math.atan2(dy, dx))

    def find_entity_by_id(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Find an entity by ID in the visible entities list"""
        for entity in self.visible_entities:
            if entity.get("id") == entity_id:
                return entity
        return None

    def find_entities_by_type(self, entity_types: List[str]) -> List[Dict[str, Any]]:
        """Find all entities of specified types in the visible entities list"""
        matching_entities = []
        for entity in self.visible_entities:
            if (
                entity.get("type") in entity_types
                or entity.get("agent_type") in entity_types
            ):
                matching_entities.append(entity)
        return matching_entities

    def get_nearest_entity_of_type(
        self, entity_types: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get the nearest entity of the specified types"""
        nearest_entity = None
        nearest_distance = float("inf")

        for entity in self.find_entities_by_type(entity_types):
            dx = entity["x"] - self.x
            dy = entity["y"] - self.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance < nearest_distance:
                nearest_distance = distance
                nearest_entity = entity

        return nearest_entity

    def _initialize_target_manager(self):
        """Initialize the target management system for this agent"""
        if not self.target_manager:
            from client.behavior_tree.target_manager import TargetManager
            self.target_manager = TargetManager(self.id)
            logger.debug(f"Agent {self.id[:8]} initialized target manager")

    def get_target_manager(self):
        """Get the target manager, initializing if needed"""
        if not self.target_manager:
            self._initialize_target_manager()
        return self.target_manager

    def _initialize_movement_manager(self):
        """Initialize the movement management system for this agent"""
        if not self.movement_manager:
            from client.behavior_tree.movement_manager import MovementManager
            self.movement_manager = MovementManager(self.id)
            logger.debug(f"Agent {self.id[:8]} initialized movement manager")

    def get_movement_manager(self):
        """Get the movement manager, initializing if needed"""
        if not self.movement_manager:
            self._initialize_movement_manager()
        return self.movement_manager

    def _initialize_position_reconciler(self):
        """Initialize the position reconciliation system for this agent"""
        if not self.position_reconciler:
            from client.position_reconciliation import PositionReconciler
            self.position_reconciler = PositionReconciler(self.id)
            logger.debug(f"Agent {self.id[:8]} initialized position reconciler")

    def get_position_reconciler(self):
        """Get the position reconciler, initializing if needed"""
        if not self.position_reconciler:
            self._initialize_position_reconciler()
        return self.position_reconciler

    def set_position_reconciler_enabled(self, enabled: bool):
        """Enable or disable position reconciliation"""
        if enabled and not self.position_reconciler:
            self._initialize_position_reconciler()
        elif not enabled:
            self.position_reconciler = None

    def _initialize_movement_validator(self):
        """Initialize the movement validation system for this agent"""
        if not self.movement_validator:
            from client.movement_validator import MovementValidator
            self.movement_validator = MovementValidator(self.id)
            # Set world bounds if we have them
            if self.world_bounds:
                self.movement_validator.set_world_bounds(*self.world_bounds)
            logger.debug(f"Agent {self.id[:8]} initialized movement validator")

    def get_movement_validator(self):
        """Get the movement validator, initializing if needed"""
        if not self.movement_validator:
            self._initialize_movement_validator()
        return self.movement_validator

    def validate_movement_to(self, target_x: float, target_y: float) -> Tuple[bool, str]:
        """Validate movement to target position"""
        if not self.movement_validator:
            self._initialize_movement_validator()

        return self.movement_validator.validate_behavior_tree_movement(self, target_x, target_y)
