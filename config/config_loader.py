"""
Configuration loader and manager for MMO simulation
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

from shared.math_utils import Vector2

logger = logging.getLogger(__name__)


@dataclass
class TerrainConfig:
    """Terrain configuration"""
    type: str
    position: Vector2
    size: Vector2
    properties: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TerrainConfig':
        return cls(
            type=data['type'],
            position=Vector2.from_tuple(data['position']),
            size=Vector2.from_tuple(data['size']),
            properties=data.get('properties', {})
        )


@dataclass
class NPCConfig:
    """NPC configuration"""
    name: str
    type: str
    position: Vector2
    level: int
    health: int
    behavior: str
    services: List[str] = field(default_factory=list)
    dialogue: List[str] = field(default_factory=list)
    patrol_radius: Optional[float] = None
    specialization: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'NPCConfig':
        return cls(
            name=data['name'],
            type=data['type'],
            position=Vector2.from_tuple(data['position']),
            level=data['level'],
            health=data['health'],
            behavior=data['behavior'],
            services=data.get('services', []),
            dialogue=data.get('dialogue', []),
            patrol_radius=data.get('patrol_radius'),
            specialization=data.get('specialization')
        )


@dataclass
class EnemySpawnArea:
    """Enemy spawn area configuration"""
    center: Vector2
    radius: float
    count: int
    level_range: Tuple[int, int]
    respawn_time: float

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnemySpawnArea':
        return cls(
            center=Vector2.from_tuple(data['center']),
            radius=data['radius'],
            count=data['count'],
            level_range=tuple(data['level_range']),
            respawn_time=data['respawn_time']
        )


@dataclass
class EnemyTemplate:
    """Enemy template configuration"""
    name_prefix: str
    entity_type: str
    base_health: int
    base_damage: int
    move_speed: float
    aggro_range: float
    ai_behavior: str
    loot_table: List[str]

    @classmethod
    def from_dict(cls, data: Dict) -> 'EnemyTemplate':
        return cls(
            name_prefix=data['name_prefix'],
            entity_type=data['entity_type'],
            base_health=data['base_health'],
            base_damage=data['base_damage'],
            move_speed=data['move_speed'],
            aggro_range=data['aggro_range'],
            ai_behavior=data['ai_behavior'],
            loot_table=data['loot_table']
        )


@dataclass
class AgentTemplate:
    """Agent template configuration"""
    class_name: str
    personality: Dict[str, float]
    behavior_params: Dict[str, Any]
    starting_equipment: List[Dict[str, Any]]
    starting_stats: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentTemplate':
        return cls(
            class_name=data['class'],
            personality=data['personality'],
            behavior_params=data['behavior_params'],
            starting_equipment=data['starting_equipment'],
            starting_stats=data['starting_stats']
        )


@dataclass
class WorldConfig:
    """World configuration container"""
    world_settings: Dict[str, Any]
    terrain: List[TerrainConfig]
    npcs: List[NPCConfig]
    enemies: Dict[str, List[EnemySpawnArea]]
    enemy_templates: Dict[str, EnemyTemplate]
    objects: List[Dict[str, Any]]
    object_templates: Dict[str, Dict[str, Any]]

    @classmethod
    def from_dict(cls, data: Dict) -> 'WorldConfig':
        terrain = [TerrainConfig.from_dict(t) for t in data.get('terrain', [])]
        npcs = [NPCConfig.from_dict(n) for n in data.get('npcs', [])]

        # Process enemies
        enemies = {}
        for enemy in data.get('enemies', []):
            template = enemy['template']
            spawn_areas = [EnemySpawnArea.from_dict(area) for area in enemy['spawn_areas']]
            enemies[template] = spawn_areas

        # Process enemy templates
        enemy_templates = {}
        for name, template_data in data.get('enemy_templates', {}).items():
            enemy_templates[name] = EnemyTemplate.from_dict(template_data)

        return cls(
            world_settings=data.get('world', {}),
            terrain=terrain,
            npcs=npcs,
            enemies=enemies,
            enemy_templates=enemy_templates,
            objects=data.get('objects', []),
            object_templates=data.get('object_templates', {})
        )


@dataclass
class AgentConfig:
    """Agent configuration container"""
    agent_templates: Dict[str, AgentTemplate]
    default_spawn_config: Dict[str, Any]
    test_scenarios: Dict[str, Dict[str, Any]]
    global_settings: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentConfig':
        agent_templates = {}
        for name, template_data in data.get('agent_templates', {}).items():
            agent_templates[name] = AgentTemplate.from_dict(template_data)

        return cls(
            agent_templates=agent_templates,
            default_spawn_config=data.get('default_spawn_config', {}),
            test_scenarios=data.get('test_scenarios', {}),
            global_settings=data.get('global_settings', {})
        )


@dataclass
class ServerConfig:
    """Server configuration container"""
    server_settings: Dict[str, Any]
    game_settings: Dict[str, Any]
    world_rules: Dict[str, Any]
    validation: Dict[str, Any]
    persistence: Dict[str, Any]
    logging_config: Dict[str, Any]
    ai_settings: Dict[str, Any]
    experimental: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict) -> 'ServerConfig':
        return cls(
            server_settings=data.get('server', {}),
            game_settings=data.get('game_settings', {}),
            world_rules=data.get('world_rules', {}),
            validation=data.get('validation', {}),
            persistence=data.get('persistence', {}),
            logging_config=data.get('logging', {}),
            ai_settings=data.get('ai_settings', {}),
            experimental=data.get('experimental', {})
        )


class ConfigLoader:
    """Configuration loader and manager"""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.world_config: Optional[WorldConfig] = None
        self.agent_config: Optional[AgentConfig] = None
        self.server_config: Optional[ServerConfig] = None

    def load_all_configs(self) -> bool:
        """Load all configuration files"""
        try:
            self.world_config = self.load_world_config()
            self.agent_config = self.load_agent_config()
            self.server_config = self.load_server_config()

            logger.info("All configurations loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load configurations: {e}")
            return False

    def load_world_config(self) -> WorldConfig:
        """Load world configuration"""
        config_path = os.path.join(self.config_dir, "world_config.json")
        with open(config_path, 'r') as f:
            data = json.load(f)
        return WorldConfig.from_dict(data)

    def load_agent_config(self) -> AgentConfig:
        """Load agent configuration"""
        config_path = os.path.join(self.config_dir, "agent_config.json")
        with open(config_path, 'r') as f:
            data = json.load(f)
        return AgentConfig.from_dict(data)

    def load_server_config(self) -> ServerConfig:
        """Load server configuration"""
        config_path = os.path.join(self.config_dir, "server_config.json")
        with open(config_path, 'r') as f:
            data = json.load(f)
        return ServerConfig.from_dict(data)

    def get_spawn_position(self, template_name: Optional[str] = None) -> Vector2:
        """Get a spawn position for an agent"""
        if not self.agent_config:
            return Vector2(500, 500)  # Default spawn

        spawn_config = self.agent_config.default_spawn_config
        center = Vector2.from_tuple(spawn_config.get('spawn_area', {}).get('center', [500, 500]))
        radius = spawn_config.get('spawn_area', {}).get('radius', 100)

        if spawn_config.get('spawn_spread', True):
            import random
            import math
            angle = random.uniform(0, 6.28)  # 2π
            distance = random.uniform(0, radius)
            return Vector2(
                center.x + distance * math.cos(angle),
                center.y + distance * math.sin(angle)
            )

        return center

    def get_test_scenario(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """Get a test scenario configuration"""
        if not self.agent_config:
            return None
        return self.agent_config.test_scenarios.get(scenario_name)

    def validate_configs(self) -> List[str]:
        """Validate all configurations and return list of issues"""
        issues = []

        if not self.world_config:
            issues.append("World config not loaded")
        elif not self.world_config.npcs:
            issues.append("No NPCs configured")

        if not self.agent_config:
            issues.append("Agent config not loaded")
        elif not self.agent_config.agent_templates:
            issues.append("No agent templates configured")

        if not self.server_config:
            issues.append("Server config not loaded")

        return issues


# Global config loader instance
config_loader = ConfigLoader()