from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from queue import PriorityQueue, Queue
from enum import Enum
import time
import uuid
import logging
from threading import Lock

logger = logging.getLogger(__name__)


class RequestType(Enum):
    MOVEMENT = "movement"
    COMBAT = "combat"
    INTERACTION = "interaction"
    SOCIAL_INTERACTION = "social_interaction"
    TRADE = "trade"
    EXPLORATION = "exploration"
    DAMAGE = "damage"
    HEAL = "heal"
    BUFF = "buff"
    DEBUFF = "debuff"
    TELEPORT = "teleport"
    ITEM_PICKUP = "item_pickup"
    ITEM_DROP = "item_drop"
    SKILL_USE = "skill_use"


class RequestStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Request:
    """Represents an agent request"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: RequestType = RequestType.MOVEMENT
    agent_id: str = ""
    priority: float = 0.5
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    status: RequestStatus = RequestStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def __lt__(self, other):
        """For priority queue ordering (higher priority first)"""
        return self.priority > other.priority


class RequestResolver:
    """Base class for request resolvers"""

    def can_resolve(self, request: Request) -> bool:
        """Check if this resolver can handle the request"""
        raise NotImplementedError

    def resolve(self, request: Request, world, request_manager) -> Dict[str, Any]:
        """Resolve the request"""
        raise NotImplementedError


class CombatResolver(RequestResolver):
    """Resolves combat-related requests"""

    def can_resolve(self, request: Request) -> bool:
        return request.type in [RequestType.COMBAT, RequestType.DAMAGE,
                               RequestType.HEAL, RequestType.BUFF, RequestType.DEBUFF]

    def resolve(self, request: Request, world, request_manager) -> Dict[str, Any]:
        """Resolve combat request"""
        if request.type == RequestType.DAMAGE:
            return self._resolve_damage(request, world)
        elif request.type == RequestType.HEAL:
            return self._resolve_heal(request, world)
        elif request.type == RequestType.COMBAT:
            return self._resolve_combat_initiation(request, world)
        elif request.type == RequestType.BUFF:
            return self._resolve_buff(request, world)
        elif request.type == RequestType.DEBUFF:
            return self._resolve_debuff(request, world)

        return {'success': False, 'message': 'Unknown combat request type'}

    def _resolve_damage(self, request: Request, world) -> Dict[str, Any]:
        """Apply damage to target"""
        target_id = request.data.get('target')
        amount = request.data.get('amount', 0)
        damage_type = request.data.get('damage_type', 'physical')

        # Find target
        target = None
        if target_id in world.agents:
            target = world.agents[target_id]
        elif target_id in world.enemies:
            target = world.enemies[target_id]
        elif target_id in world.npcs:
            target = world.npcs[target_id]

        if not target:
            return {'success': False, 'message': 'Target not found'}

        # Apply damage
        if hasattr(target, 'take_damage'):
            target.take_damage(amount, request.agent_id, damage_type)
        else:
            target.stats.health -= amount

        logger.debug(f"Applied {amount} {damage_type} damage to {target_id}")

        return {
            'success': True,
            'damage': amount,
            'target_health': target.stats.health,
            'message': f'Dealt {amount} damage'
        }

    def _resolve_heal(self, request: Request, world) -> Dict[str, Any]:
        """Apply healing to target"""
        target_id = request.data.get('target', request.agent_id)
        amount = request.data.get('amount', 0)

        # Find target
        target = world.agents.get(target_id)
        if not target:
            return {'success': False, 'message': 'Target not found'}

        # Apply healing
        old_health = target.stats.health
        target.stats.health = min(target.stats.max_health, target.stats.health + amount)
        actual_heal = target.stats.health - old_health

        return {
            'success': True,
            'healed': actual_heal,
            'target_health': target.stats.health,
            'message': f'Healed for {actual_heal}'
        }

    def _resolve_combat_initiation(self, request: Request, world) -> Dict[str, Any]:
        """Initiate combat between agent and target"""
        target_id = request.data.get('target_enemy')

        if target_id not in world.enemies:
            return {'success': False, 'message': 'Enemy not found'}

        enemy = world.enemies[target_id]
        agent = world.agents.get(request.agent_id)

        if not agent:
            return {'success': False, 'message': 'Agent not found'}

        # Check distance
        distance = agent.position.distance_to(enemy.position)
        if distance > 100:
            return {'success': False, 'message': 'Target too far away'}

        # Initiate combat
        enemy.enter_combat(agent.id)
        agent.state = agent.AgentState.COMBAT

        return {
            'success': True,
            'message': f'Engaged in combat with {enemy.name}'
        }

    def _resolve_buff(self, request: Request, world) -> Dict[str, Any]:
        """Apply buff to target"""
        # Buff system would be implemented here
        return {'success': True, 'message': 'Buff applied'}

    def _resolve_debuff(self, request: Request, world) -> Dict[str, Any]:
        """Apply debuff to target"""
        # Debuff system would be implemented here
        return {'success': True, 'message': 'Debuff applied'}


class MovementResolver(RequestResolver):
    """Resolves movement requests"""

    def can_resolve(self, request: Request) -> bool:
        return request.type in [RequestType.MOVEMENT, RequestType.EXPLORATION]

    def resolve(self, request: Request, world, request_manager) -> Dict[str, Any]:
        """Resolve movement request"""
        agent = world.agents.get(request.agent_id)
        if not agent:
            return {'success': False, 'message': 'Agent not found'}

        if request.type == RequestType.MOVEMENT:
            return self._resolve_movement(request, agent, world)
        elif request.type == RequestType.EXPLORATION:
            return self._resolve_exploration(request, agent, world)

        return {'success': False, 'message': 'Unknown movement request type'}

    def _resolve_movement(self, request: Request, agent, world) -> Dict[str, Any]:
        """Process movement to target position"""
        target_pos = request.data.get('target_position')
        if not target_pos:
            return {'success': False, 'message': 'No target position specified'}

        # Set agent velocity towards target
        dx = target_pos[0] - agent.position.x
        dy = target_pos[1] - agent.position.y
        distance = (dx * dx + dy * dy) ** 0.5

        if distance < 1.0:
            return {'success': True, 'message': 'Already at destination'}

        agent.velocity.x = dx / distance
        agent.velocity.y = dy / distance
        agent.state = agent.AgentState.MOVING

        return {'success': True, 'message': 'Movement initiated'}

    def _resolve_exploration(self, request: Request, agent, world) -> Dict[str, Any]:
        """Process exploration request"""
        target_area = request.data.get('target_area', 'unknown_area')

        # Find appropriate area to explore
        areas = list(world.areas.values())
        suitable_areas = []

        for area in areas:
            if target_area == 'safe_area' and area.danger_level < 0.3:
                suitable_areas.append(area)
            elif target_area == 'dangerous_area' and area.danger_level > 0.7:
                suitable_areas.append(area)
            elif target_area == 'unknown_area':
                # Areas the agent hasn't visited (would need visit tracking)
                suitable_areas.append(area)

        if not suitable_areas:
            return {'success': False, 'message': 'No suitable areas found'}

        # Pick closest suitable area
        import random
        target = random.choice(suitable_areas)

        # Set movement towards area
        agent.current_goal = {
            'type': 'exploration',
            'target': target.id,
            'position': (target.position.x + target.size.x / 2,
                        target.position.y + target.size.y / 2)
        }

        return {'success': True, 'message': f'Exploring {target.name}'}


class SocialResolver(RequestResolver):
    """Resolves social interaction requests"""

    def can_resolve(self, request: Request) -> bool:
        return request.type in [RequestType.SOCIAL_INTERACTION, RequestType.TRADE]

    def resolve(self, request: Request, world, request_manager) -> Dict[str, Any]:
        """Resolve social request"""
        if request.type == RequestType.SOCIAL_INTERACTION:
            return self._resolve_social_interaction(request, world)
        elif request.type == RequestType.TRADE:
            return self._resolve_trade(request, world)

        return {'success': False, 'message': 'Unknown social request type'}

    def _resolve_social_interaction(self, request: Request, world) -> Dict[str, Any]:
        """Process social interaction"""
        agent = world.agents.get(request.agent_id)
        target_id = request.data.get('target_agent')
        interaction_type = request.data.get('interaction_type', 'greet')

        if not agent:
            return {'success': False, 'message': 'Agent not found'}

        target = world.agents.get(target_id) or world.npcs.get(target_id)
        if not target:
            return {'success': False, 'message': 'Target not found'}

        # Check distance
        distance = agent.position.distance_to(target.position)
        if distance > 50:
            return {'success': False, 'message': 'Target too far away'}

        # Process interaction based on type
        if interaction_type == 'greet':
            # Update relationships
            agent.memory.update_relationship(target_id, 0.01)
            if hasattr(target, 'memory'):
                target.memory.update_relationship(agent.id, 0.01)

            return {'success': True, 'message': f'{agent.name} greeted {target.name}'}

        elif interaction_type == 'teach':
            # Share knowledge
            if agent.memory.knowledge_base:
                import random
                knowledge = random.choice(agent.memory.knowledge_base)
                agent.share_knowledge(knowledge, target)
                return {'success': True, 'message': f'{agent.name} shared knowledge with {target.name}'}

        elif interaction_type == 'chat':
            # Improve relationship
            agent.memory.update_relationship(target_id, 0.05)
            if hasattr(target, 'memory'):
                target.memory.update_relationship(agent.id, 0.05)

            return {'success': True, 'message': f'{agent.name} had a conversation with {target.name}'}

        return {'success': True, 'message': f'Interaction completed'}

    def _resolve_trade(self, request: Request, world) -> Dict[str, Any]:
        """Process trade request"""
        # Trade system would be implemented here
        return {'success': True, 'message': 'Trade completed'}


class RequestManager:
    """Manages and resolves agent requests"""

    def __init__(self, world):
        self.world = world
        self.pending_requests = PriorityQueue()
        self.processing_queue = Queue()
        self.resolved_requests: List[Request] = []
        self.failed_requests: List[Request] = []

        # Request resolvers
        self.resolvers: List[RequestResolver] = [
            CombatResolver(),
            MovementResolver(),
            SocialResolver()
        ]

        # Statistics
        self.total_requests_processed = 0
        self.requests_by_type: Dict[RequestType, int] = {}

        # Thread safety
        self.lock = Lock()

        logger.info("RequestManager initialized")

    def add_request(self, request_data: Dict[str, Any]):
        """Add a new request to the queue"""
        request = Request(
            type=RequestType(request_data.get('type', 'movement')),
            agent_id=request_data.get('agent_id', ''),
            priority=request_data.get('priority', 0.5),
            data=request_data
        )

        with self.lock:
            self.pending_requests.put(request)

        logger.debug(f"Request added: {request.type.value} from {request.agent_id}")

    def process_requests(self):
        """Process pending requests"""
        batch_size = 10  # Process up to 10 requests per update

        for _ in range(batch_size):
            if self.pending_requests.empty():
                break

            with self.lock:
                request = self.pending_requests.get()

            # Find appropriate resolver
            resolver = None
            for r in self.resolvers:
                if r.can_resolve(request):
                    resolver = r
                    break

            if not resolver:
                request.status = RequestStatus.FAILED
                request.error_message = "No resolver found"
                self.failed_requests.append(request)
                continue

            # Process request
            request.status = RequestStatus.PROCESSING
            try:
                result = resolver.resolve(request, self.world, self)
                request.result = result
                request.status = RequestStatus.RESOLVED
                self.resolved_requests.append(request)

                # Update statistics
                self.total_requests_processed += 1
                self.requests_by_type[request.type] = self.requests_by_type.get(request.type, 0) + 1

                logger.debug(f"Request resolved: {request.type.value} - {result.get('message', 'Success')}")

            except Exception as e:
                request.status = RequestStatus.FAILED
                request.error_message = str(e)
                self.failed_requests.append(request)
                logger.error(f"Error processing request: {e}")

        # Clean up old resolved requests
        if len(self.resolved_requests) > 1000:
            self.resolved_requests = self.resolved_requests[-500:]

    def get_pending_count(self) -> int:
        """Get number of pending requests"""
        with self.lock:
            return self.pending_requests.qsize()

    def get_statistics(self) -> Dict[str, Any]:
        """Get request processing statistics"""
        return {
            'total_processed': self.total_requests_processed,
            'pending': self.get_pending_count(),
            'resolved': len(self.resolved_requests),
            'failed': len(self.failed_requests),
            'by_type': dict(self.requests_by_type)
        }

    def cancel_agent_requests(self, agent_id: str):
        """Cancel all pending requests for a specific agent"""
        with self.lock:
            # This would need to be implemented with a different data structure
            # to efficiently remove specific agent requests
            pass