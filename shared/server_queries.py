"""
Server Query System for Action Validation

This system allows clients to query the server for authoritative
position and action validation before attempting actions.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, Tuple


class QueryType(Enum):
    """Types of queries clients can send to server"""
    CAN_PERFORM_ACTION = "can_perform_action"
    GET_AGENT_POSITION = "get_agent_position"
    GET_DISTANCE_TO_TARGET = "get_distance_to_target"
    VALIDATE_ACTION_DISTANCE = "validate_action_distance"


@dataclass
class ServerQuery:
    """A query from client to server"""
    query_id: str
    query_type: QueryType
    agent_id: str
    parameters: Dict[str, Any]


@dataclass
class ServerQueryResponse:
    """Server response to a client query"""
    query_id: str
    query_type: QueryType
    agent_id: str
    success: bool
    data: Dict[str, Any]
    message: str = ""


def create_action_validation_query(
    query_id: str,
    agent_id: str,
    action_name: str,
    target_x: float,
    target_y: float
) -> ServerQuery:
    """Create a query to validate if an action can be performed"""
    return ServerQuery(
        query_id=query_id,
        query_type=QueryType.VALIDATE_ACTION_DISTANCE,
        agent_id=agent_id,
        parameters={
            "action_name": action_name,
            "target_x": target_x,
            "target_y": target_y
        }
    )


def create_position_query(query_id: str, agent_id: str) -> ServerQuery:
    """Create a query to get agent's current position from server"""
    return ServerQuery(
        query_id=query_id,
        query_type=QueryType.GET_AGENT_POSITION,
        agent_id=agent_id,
        parameters={}
    )


def create_distance_query(
    query_id: str,
    agent_id: str,
    target_x: float,
    target_y: float
) -> ServerQuery:
    """Create a query to get distance from agent to target"""
    return ServerQuery(
        query_id=query_id,
        query_type=QueryType.GET_DISTANCE_TO_TARGET,
        agent_id=agent_id,
        parameters={
            "target_x": target_x,
            "target_y": target_y
        }
    )