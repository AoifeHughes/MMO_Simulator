from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum
import random
import logging

from src.agents.agent import Agent, AgentState
from src.world.world import Vector2

logger = logging.getLogger(__name__)


class NPCRole(Enum):
    MERCHANT = "merchant"
    QUEST_GIVER = "quest_giver"
    TRAINER = "trainer"
    GUARD = "guard"
    INNKEEPER = "innkeeper"
    BLACKSMITH = "blacksmith"
    WANDERER = "wanderer"


@dataclass
class Quest:
    id: str
    name: str
    description: str
    requirements: Dict[str, Any]
    rewards: Dict[str, Any]
    level_requirement: int = 1
    completed: bool = False


class NPC(Agent):
    """Non-Player Character with specific roles and behaviors"""

    def __init__(self, name: str, role: NPCRole, position: Vector2 = None):
        super().__init__(name)
        self.role = role
        self.character_class = "NPC"

        if position:
            self.position = position

        # NPC-specific attributes
        self.dialogue_tree: Dict[str, List[str]] = self._initialize_dialogue()
        self.quests: List[Quest] = []
        self.shop_inventory: List[Any] = []
        self.patrol_route: List[Vector2] = []
        self.home_position = Vector2(self.position.x, self.position.y)
        self.max_wander_distance = 50.0

        # Initialize based on role
        self._initialize_by_role()

        logger.info(f"NPC {self.name} ({role.value}) created at position {position}")

    def _initialize_by_role(self):
        """Initialize NPC attributes based on role"""
        if self.role == NPCRole.MERCHANT:
            self._setup_merchant()
        elif self.role == NPCRole.QUEST_GIVER:
            self._setup_quest_giver()
        elif self.role == NPCRole.TRAINER:
            self._setup_trainer()
        elif self.role == NPCRole.GUARD:
            self._setup_guard()
        elif self.role == NPCRole.WANDERER:
            self._setup_wanderer()

    def _setup_merchant(self):
        """Setup merchant-specific attributes"""
        self.personality.social = random.uniform(0.6, 0.9)
        self.personality.trust = random.uniform(0.4, 0.7)
        self.shop_inventory = self._generate_shop_inventory()
        self.dialogue_tree['greeting'].append("Welcome to my shop! What can I get for you today?")
        self.dialogue_tree['farewell'].append("Come back soon! Best prices in town!")

    def _setup_quest_giver(self):
        """Setup quest giver attributes"""
        self.personality.social = random.uniform(0.5, 0.8)
        self.personality.teaching = random.uniform(0.6, 0.9)
        self.quests = self._generate_quests()
        self.dialogue_tree['greeting'].append("Ah, an adventurer! I have tasks that need doing.")
        self.dialogue_tree['quest_available'] = ["I have a quest that might interest you..."]

    def _setup_trainer(self):
        """Setup trainer attributes"""
        self.personality.teaching = random.uniform(0.7, 1.0)
        self.personality.social = random.uniform(0.4, 0.7)
        self.dialogue_tree['greeting'].append("Looking to improve your skills? You've come to the right place.")
        self.dialogue_tree['training'] = ["Let me show you a few techniques..."]

    def _setup_guard(self):
        """Setup guard attributes"""
        self.personality.risk_taking = random.uniform(0.1, 0.4)
        self.personality.trust = random.uniform(0.2, 0.5)
        self.patrol_route = self._generate_patrol_route()
        self.dialogue_tree['greeting'].append("Move along, citizen.")
        self.dialogue_tree['warning'] = ["No trouble here, understand?"]

    def _setup_wanderer(self):
        """Setup wandering NPC attributes"""
        self.personality.exploration = random.uniform(0.6, 1.0)
        self.personality.social = random.uniform(0.3, 0.8)
        self.max_wander_distance = 200.0
        self.dialogue_tree['greeting'].append("Oh, hello there! Lovely day for a walk, isn't it?")
        self.dialogue_tree['story'] = ["Let me tell you about my travels..."]

    def _initialize_dialogue(self) -> Dict[str, List[str]]:
        """Initialize basic dialogue options"""
        return {
            'greeting': ["Hello, traveler."],
            'farewell': ["Safe travels."],
            'busy': ["I'm a bit busy right now."],
            'unknown': ["I'm not sure what you mean."]
        }

    def _generate_shop_inventory(self) -> List[Dict[str, Any]]:
        """Generate shop inventory for merchants"""
        items = []
        item_count = random.randint(5, 15)
        for i in range(item_count):
            items.append({
                'id': f"item_{i}",
                'name': f"Item {i}",
                'type': random.choice(['weapon', 'armor', 'consumable', 'material']),
                'price': random.randint(10, 1000),
                'level_requirement': random.randint(1, 50)
            })
        return items

    def _generate_quests(self) -> List[Quest]:
        """Generate quests for quest givers"""
        quests = []
        quest_count = random.randint(1, 3)
        for i in range(quest_count):
            quests.append(Quest(
                id=f"quest_{self.id}_{i}",
                name=f"Quest {i}",
                description="Help needed with an important task.",
                requirements={'type': 'kill', 'target': 'enemy', 'count': random.randint(5, 20)},
                rewards={'experience': random.randint(100, 1000), 'gold': random.randint(50, 500)},
                level_requirement=random.randint(1, 30)
            ))
        return quests

    def _generate_patrol_route(self) -> List[Vector2]:
        """Generate patrol route for guards"""
        route = []
        points = random.randint(2, 5)
        for _ in range(points):
            offset_x = random.uniform(-30, 30)
            offset_y = random.uniform(-30, 30)
            route.append(Vector2(
                self.home_position.x + offset_x,
                self.home_position.y + offset_y
            ))
        return route

    def update(self, delta_time: float, world, request_manager):
        """Update NPC behavior"""
        # Base agent update
        super().update(delta_time, world, request_manager)

        # Role-specific behaviors
        if self.role == NPCRole.GUARD and self.patrol_route:
            self._patrol_behavior(delta_time, world)
        elif self.role == NPCRole.WANDERER:
            self._wander_behavior(delta_time, world)
        elif self.role == NPCRole.MERCHANT:
            self._merchant_behavior(delta_time, world)

    def _patrol_behavior(self, delta_time: float, world):
        """Guard patrol behavior"""
        if self.state == AgentState.IDLE and self.patrol_route:
            # Move to next patrol point
            if not hasattr(self, 'current_patrol_index'):
                self.current_patrol_index = 0

            target = self.patrol_route[self.current_patrol_index]
            distance = self.position.distance_to(target)

            if distance < 5.0:
                # Reached patrol point, move to next
                self.current_patrol_index = (self.current_patrol_index + 1) % len(self.patrol_route)
            else:
                # Move towards patrol point
                direction_x = (target.x - self.position.x) / distance
                direction_y = (target.y - self.position.y) / distance
                self.velocity = Vector2(direction_x, direction_y)
                self.state = AgentState.MOVING

    def _wander_behavior(self, delta_time: float, world):
        """Wandering NPC behavior"""
        if self.state == AgentState.IDLE:
            if random.random() < 0.01:  # 1% chance per update to start wandering
                # Pick random direction within wander distance
                angle = random.uniform(0, 2 * 3.14159)
                distance = random.uniform(0, self.max_wander_distance)
                target_x = self.home_position.x + distance * math.cos(angle)
                target_y = self.home_position.y + distance * math.sin(angle)

                # Set velocity towards target
                dx = target_x - self.position.x
                dy = target_y - self.position.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    self.velocity = Vector2(dx / dist, dy / dist)
                    self.state = AgentState.MOVING

    def _merchant_behavior(self, delta_time: float, world):
        """Merchant-specific behavior"""
        # Check for nearby agents to greet
        if self.state == AgentState.IDLE:
            nearby_agents = world.get_nearby_agents(self.position, 20.0)
            for agent in nearby_agents:
                if agent.id != self.id and random.random() < 0.05:
                    self.interact_with_agent(agent, 'greeting')

    def interact_with_agent(self, agent: Agent, interaction_type: str):
        """Handle interaction with another agent"""
        if interaction_type == 'greeting':
            dialogue = self.get_dialogue('greeting')
            logger.debug(f"{self.name} says to {agent.name}: {dialogue}")
            return {'type': 'dialogue', 'text': dialogue}

        elif interaction_type == 'trade' and self.role == NPCRole.MERCHANT:
            return {'type': 'shop', 'inventory': self.shop_inventory}

        elif interaction_type == 'quest' and self.role == NPCRole.QUEST_GIVER:
            available_quests = [q for q in self.quests if not q.completed and agent.level >= q.level_requirement]
            if available_quests:
                return {'type': 'quest_offer', 'quests': available_quests}

        return {'type': 'dialogue', 'text': self.get_dialogue('unknown')}

    def get_dialogue(self, context: str) -> str:
        """Get appropriate dialogue for context"""
        if context in self.dialogue_tree:
            return random.choice(self.dialogue_tree[context])
        return random.choice(self.dialogue_tree['unknown'])

    def complete_quest(self, quest_id: str):
        """Mark a quest as completed"""
        for quest in self.quests:
            if quest.id == quest_id:
                quest.completed = True
                logger.info(f"Quest {quest_id} completed for NPC {self.name}")
                break


import math  # Add this import at the top of the file