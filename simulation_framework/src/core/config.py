from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
import os


@dataclass
class SimulationConfig:
    """Configuration for simulation parameters"""

    # World generation
    world_width: int = 50
    world_height: int = 50
    world_seed: int = 42

    # Simulation limits
    max_ticks: int = 10000
    tick_rate: float = 0.0  # 0 = unlimited speed, >0 = ticks per second

    # Database and persistence
    database_path: str = "simulation.db"
    save_interval: int = 100  # Save snapshots every N ticks
    analytics_interval: int = 50  # Calculate analytics every N ticks

    # Agent parameters
    max_agents: int = 100
    default_agent_vision_range: int = 5
    default_agent_stamina: int = 100
    default_agent_health: int = 100

    # NPC parameters
    max_npcs: int = 100
    npc_respawn_enabled: bool = True

    # Economic parameters
    starting_gold: int = 100
    trade_cooldown: int = 10  # Ticks between trades

    # Performance settings
    enable_pathfinding_cache: bool = True
    max_pathfinding_distance: int = 50
    fog_of_war_enabled: bool = True

    # Logging and debugging
    log_level: str = "INFO"
    debug_mode: bool = False
    log_actions: bool = True
    log_file: Optional[str] = None

    # Custom parameters
    custom_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, config_path: str) -> 'SimulationConfig':
        """Load configuration from JSON file"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as f:
            data = json.load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SimulationConfig':
        """Create configuration from dictionary"""
        # Extract known fields
        known_fields = {field.name for field in cls.__dataclass_fields__.values()}
        config_data = {}
        custom_params = {}

        for key, value in data.items():
            if key in known_fields:
                config_data[key] = value
            else:
                custom_params[key] = value

        config_data['custom_params'] = custom_params
        return cls(**config_data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        result = {}

        # Add all known fields except custom_params
        for field_name, field_def in self.__dataclass_fields__.items():
            if field_name != 'custom_params':
                result[field_name] = getattr(self, field_name)

        # Add custom parameters
        result.update(self.custom_params)

        return result

    def to_file(self, config_path: str) -> None:
        """Save configuration to JSON file"""
        with open(config_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports custom params)"""
        if hasattr(self, key):
            return getattr(self, key)
        return self.custom_params.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by key"""
        if hasattr(self, key):
            setattr(self, key, value)
        else:
            self.custom_params[key] = value

    def validate(self) -> None:
        """Validate configuration parameters"""
        errors = []

        # Validate world parameters
        if self.world_width <= 0:
            errors.append("world_width must be positive")
        if self.world_height <= 0:
            errors.append("world_height must be positive")

        # Validate simulation parameters
        if self.max_ticks <= 0:
            errors.append("max_ticks must be positive")
        if self.tick_rate < 0:
            errors.append("tick_rate must be non-negative")

        # Validate intervals
        if self.save_interval <= 0:
            errors.append("save_interval must be positive")
        if self.analytics_interval <= 0:
            errors.append("analytics_interval must be positive")

        # Validate entity limits
        if self.max_agents <= 0:
            errors.append("max_agents must be positive")
        if self.max_npcs < 0:
            errors.append("max_npcs must be non-negative")

        # Validate agent parameters
        if self.default_agent_vision_range <= 0:
            errors.append("default_agent_vision_range must be positive")
        if self.default_agent_stamina <= 0:
            errors.append("default_agent_stamina must be positive")
        if self.default_agent_health <= 0:
            errors.append("default_agent_health must be positive")

        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

    def copy(self) -> 'SimulationConfig':
        """Create a copy of this configuration"""
        return SimulationConfig.from_dict(self.to_dict())

    def __str__(self) -> str:
        return f"SimulationConfig(world={self.world_width}x{self.world_height}, max_ticks={self.max_ticks})"

    def __repr__(self) -> str:
        return (f"SimulationConfig(world_size=({self.world_width}, {self.world_height}), "
                f"seed={self.world_seed}, max_ticks={self.max_ticks})")