from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Union
import json
import sqlite3
from datetime import datetime


@dataclass
class SimulationRun:
    """Model for simulation run metadata"""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    world_seed: int = 0
    world_width: int = 0
    world_height: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    current_tick: int = 0
    total_agents: int = 0
    config: Dict = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


@dataclass
class AgentSnapshot:
    """Model for agent state snapshots"""
    id: Optional[int] = None
    simulation_id: int = 0
    agent_id: int = 0
    tick: int = 0
    name: str = ""
    position_x: int = 0
    position_y: int = 0
    health: int = 0
    max_health: int = 0
    stamina: int = 0
    max_stamina: int = 0
    personality: Dict = None
    character_class: str = ""
    skills: Dict = None
    current_goals: List = None
    relationships: Dict = None
    inventory_items: int = 0
    gold: int = 0

    def __post_init__(self):
        if self.personality is None:
            self.personality = {}
        if self.skills is None:
            self.skills = {}
        if self.current_goals is None:
            self.current_goals = []
        if self.relationships is None:
            self.relationships = {}


@dataclass
class WorldSnapshot:
    """Model for world state snapshots"""
    id: Optional[int] = None
    simulation_id: int = 0
    tick: int = 0
    total_entities: int = 0
    active_agents: int = 0
    active_npcs: int = 0
    resource_nodes: int = 0
    world_events: List = None
    market_prices: Dict = None

    def __post_init__(self):
        if self.world_events is None:
            self.world_events = []
        if self.market_prices is None:
            self.market_prices = {}


@dataclass
class ActionLog:
    """Model for logging agent actions"""
    id: Optional[int] = None
    simulation_id: int = 0
    tick: int = 0
    agent_id: int = 0
    action_type: str = ""
    action_data: Dict = None
    success: bool = False
    result_message: str = ""
    duration: int = 1

    def __post_init__(self):
        if self.action_data is None:
            self.action_data = {}


@dataclass
class TradeLog:
    """Model for logging trade transactions"""
    id: Optional[int] = None
    simulation_id: int = 0
    tick: int = 0
    initiator_id: int = 0
    target_id: int = 0
    offered_items: Dict = None
    requested_items: Dict = None
    offered_gold: int = 0
    requested_gold: int = 0
    completed: bool = False

    def __post_init__(self):
        if self.offered_items is None:
            self.offered_items = {}
        if self.requested_items is None:
            self.requested_items = {}


@dataclass
class CombatLog:
    """Model for logging combat encounters"""
    id: Optional[int] = None
    simulation_id: int = 0
    tick: int = 0
    attacker_id: int = 0
    target_id: int = 0
    damage_dealt: int = 0
    damage_type: str = ""
    was_critical: bool = False
    weapon_used: str = ""
    target_died: bool = False


@dataclass
class Analytics:
    """Model for simulation analytics and metrics"""
    id: Optional[int] = None
    simulation_id: int = 0
    metric_name: str = ""
    metric_value: float = 0.0
    tick: int = 0
    category: str = ""  # economy, social, combat, exploration
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DatabaseHelper:
    """Helper functions for database operations"""

    @staticmethod
    def dict_to_json(data: Dict) -> str:
        """Convert dictionary to JSON string for database storage"""
        if data is None:
            return "{}"
        return json.dumps(data, default=str)

    @staticmethod
    def json_to_dict(data: str) -> Dict:
        """Convert JSON string from database to dictionary"""
        if not data:
            return {}
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {}

    @staticmethod
    def list_to_json(data: List) -> str:
        """Convert list to JSON string for database storage"""
        if data is None:
            return "[]"
        return json.dumps(data, default=str)

    @staticmethod
    def json_to_list(data: str) -> List:
        """Convert JSON string from database to list"""
        if not data:
            return []
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def row_to_dataclass(row: sqlite3.Row, model_class) -> Any:
        """Convert SQLite row to dataclass instance"""
        if row is None:
            return None

        data = dict(row)

        # Remove database-only fields that aren't in the dataclass
        database_only_fields = {'created_at', 'updated_at'}
        for field in database_only_fields:
            data.pop(field, None)

        # Handle JSON fields based on model type
        if model_class == AgentSnapshot:
            data['personality'] = DatabaseHelper.json_to_dict(data.get('personality', '{}'))
            data['skills'] = DatabaseHelper.json_to_dict(data.get('skills', '{}'))
            data['current_goals'] = DatabaseHelper.json_to_list(data.get('current_goals', '[]'))
            data['relationships'] = DatabaseHelper.json_to_dict(data.get('relationships', '{}'))

        elif model_class == WorldSnapshot:
            data['world_events'] = DatabaseHelper.json_to_list(data.get('world_events', '[]'))
            data['market_prices'] = DatabaseHelper.json_to_dict(data.get('market_prices', '{}'))

        elif model_class == ActionLog:
            data['action_data'] = DatabaseHelper.json_to_dict(data.get('action_data', '{}'))

        elif model_class == TradeLog:
            data['offered_items'] = DatabaseHelper.json_to_dict(data.get('offered_items', '{}'))
            data['requested_items'] = DatabaseHelper.json_to_dict(data.get('requested_items', '{}'))

        elif model_class == SimulationRun:
            data['config'] = DatabaseHelper.json_to_dict(data.get('config', '{}'))
            # Handle datetime conversion
            if data.get('start_time'):
                try:
                    data['start_time'] = datetime.fromisoformat(data['start_time'])
                except (ValueError, TypeError):
                    data['start_time'] = None
            if data.get('end_time'):
                try:
                    data['end_time'] = datetime.fromisoformat(data['end_time'])
                except (ValueError, TypeError):
                    data['end_time'] = None

        elif model_class == Analytics:
            data['metadata'] = DatabaseHelper.json_to_dict(data.get('metadata', '{}'))

        return model_class(**data)

    @staticmethod
    def dataclass_to_dict(obj: Any, for_insert: bool = False) -> Dict:
        """Convert dataclass to dictionary for database operations"""
        data = asdict(obj)

        # Remove None id for inserts
        if for_insert and data.get('id') is None:
            data.pop('id', None)

        # Convert complex types to JSON strings
        if isinstance(obj, AgentSnapshot):
            data['personality'] = DatabaseHelper.dict_to_json(data.get('personality'))
            data['skills'] = DatabaseHelper.dict_to_json(data.get('skills'))
            data['current_goals'] = DatabaseHelper.list_to_json(data.get('current_goals'))
            data['relationships'] = DatabaseHelper.dict_to_json(data.get('relationships'))

        elif isinstance(obj, WorldSnapshot):
            data['world_events'] = DatabaseHelper.list_to_json(data.get('world_events'))
            data['market_prices'] = DatabaseHelper.dict_to_json(data.get('market_prices'))

        elif isinstance(obj, ActionLog):
            data['action_data'] = DatabaseHelper.dict_to_json(data.get('action_data'))

        elif isinstance(obj, TradeLog):
            data['offered_items'] = DatabaseHelper.dict_to_json(data.get('offered_items'))
            data['requested_items'] = DatabaseHelper.dict_to_json(data.get('requested_items'))

        elif isinstance(obj, SimulationRun):
            data['config'] = DatabaseHelper.dict_to_json(data.get('config'))
            # Handle datetime conversion
            if data.get('start_time'):
                data['start_time'] = data['start_time'].isoformat()
            if data.get('end_time'):
                data['end_time'] = data['end_time'].isoformat()

        elif isinstance(obj, Analytics):
            data['metadata'] = DatabaseHelper.dict_to_json(data.get('metadata'))

        return data