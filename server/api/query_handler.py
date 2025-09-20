"""
Handles query requests from clients
"""

import logging
from typing import Dict, Any

from server.core.game_state import GameState
from shared.messages import QueryMessage, QueryResultMessage, QueryType, EntityView
from shared.math_utils import Vector2

logger = logging.getLogger(__name__)


class QueryHandler:
    """Processes client queries for information"""

    def __init__(self, game_state: GameState):
        self.game_state = game_state

    async def handle_query(self, client_id: str, query_msg: QueryMessage) -> QueryResultMessage:
        """Process a query from a client"""
        # Get agent entity
        entity_id = self.game_state.agents.get(client_id)
        if not entity_id:
            return QueryResultMessage(
                query=query_msg.query,
                result={'error': 'Agent entity not found'}
            )

        entity = self.game_state.get_entity(entity_id)
        if not entity:
            return QueryResultMessage(
                query=query_msg.query,
                result={'error': 'Entity not found'}
            )

        # Route to specific handler
        if query_msg.query == QueryType.GET_STATS:
            return await self._query_stats(entity)
        elif query_msg.query == QueryType.GET_INVENTORY:
            return await self._query_inventory(entity)
        elif query_msg.query == QueryType.GET_SURROUNDINGS:
            return await self._query_surroundings(entity, query_msg.params)
        elif query_msg.query == QueryType.GET_ENTITY_INFO:
            return await self._query_entity_info(entity, query_msg.params)
        elif query_msg.query == QueryType.GET_MAP_INFO:
            return await self._query_map_info(entity, query_msg.params)
        else:
            return QueryResultMessage(
                query=query_msg.query,
                result={'error': f'Unknown query type: {query_msg.query}'}
            )

    async def _query_stats(self, entity) -> QueryResultMessage:
        """Get entity's own stats"""
        stats = {
            'health': entity.health,
            'max_health': entity.max_health,
            'level': entity.level,
            'position': entity.position.to_tuple(),
            'state': entity.state,
            'alive': entity.alive
        }

        # Add class-specific stats if available
        if 'class' in entity.data:
            stats['class'] = entity.data['class']

        return QueryResultMessage(
            query=QueryType.GET_STATS,
            result=stats
        )

    async def _query_inventory(self, entity) -> QueryResultMessage:
        """Get entity's inventory"""
        # Simplified - would have proper inventory system
        inventory = entity.data.get('inventory', [])

        return QueryResultMessage(
            query=QueryType.GET_INVENTORY,
            result={'items': inventory, 'capacity': 20}
        )

    async def _query_surroundings(self, entity, params: Dict[str, Any]) -> QueryResultMessage:
        """Get information about surroundings"""
        radius = params.get('radius', entity.vision_range)
        radius = min(radius, entity.vision_range * 1.5)  # Limit query range

        # Get nearby entities
        nearby_entities = self.game_state.get_entities_in_range(entity.position, radius)

        # Convert to client views
        surroundings = {
            'entities': [],
            'terrain': [],
            'objects': []
        }

        for e in nearby_entities:
            if e.id == entity.id:
                continue  # Skip self

            # Create limited view
            view = EntityView(
                id=e.id,
                name=e.name,
                entity_type=e.entity_type,
                position=e.position.to_tuple(),
                health_percentage=(e.health / e.max_health * 100) if e.max_health > 0 else 0,
                level=e.level,
                state=e.state,
                velocity=e.velocity.to_tuple() if e.velocity.magnitude() > 0 else None
            )

            # Categorize
            if e.entity_type in ['agent', 'npc', 'enemy']:
                surroundings['entities'].append(view.to_dict())
            else:
                surroundings['objects'].append(view.to_dict())

        return QueryResultMessage(
            query=QueryType.GET_SURROUNDINGS,
            result=surroundings
        )

    async def _query_entity_info(self, entity, params: Dict[str, Any]) -> QueryResultMessage:
        """Get detailed information about a specific entity"""
        target_id = params.get('entity_id')
        if not target_id:
            return QueryResultMessage(
                query=QueryType.GET_ENTITY_INFO,
                result={'error': 'Missing entity_id parameter'}
            )

        target = self.game_state.get_entity(target_id)
        if not target:
            return QueryResultMessage(
                query=QueryType.GET_ENTITY_INFO,
                result={'error': 'Entity not found'}
            )

        # Check if target is visible
        distance = entity.position.distance_to(target.position)
        if distance > entity.vision_range:
            return QueryResultMessage(
                query=QueryType.GET_ENTITY_INFO,
                result={'error': 'Entity not in range'}
            )

        # Create detailed view (but still limited)
        info = {
            'id': target.id,
            'name': target.name,
            'entity_type': target.entity_type,
            'position': target.position.to_tuple(),
            'health_percentage': (target.health / target.max_health * 100) if target.max_health > 0 else 0,
            'level': target.level,
            'state': target.state,
            'in_combat': target.in_combat,
            'distance': distance
        }

        # Add more info for NPCs
        if target.entity_type == 'npc':
            info['npc_role'] = target.data.get('role', 'generic')

        return QueryResultMessage(
            query=QueryType.GET_ENTITY_INFO,
            result=info
        )

    async def _query_map_info(self, entity, params: Dict[str, Any]) -> QueryResultMessage:
        """Get map/zone information"""
        # Get current zone info
        position = entity.position
        zone_info = {
            'current_position': position.to_tuple(),
            'world_size': (self.game_state.spatial_grid.width,
                          self.game_state.spatial_grid.height),
            'current_zone': 'starter_zone',  # Would determine from position
            'nearby_zones': ['forest', 'mountains'],
            'discovered_areas': entity.data.get('discovered_areas', [])
        }

        return QueryResultMessage(
            query=QueryType.GET_MAP_INFO,
            result=zone_info
        )