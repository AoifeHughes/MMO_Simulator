from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid
import random
import logging

from src.world.world import Vector2

logger = logging.getLogger(__name__)


class ObjectType(Enum):
    STATIC = "static"
    INTERACTIVE = "interactive"
    CONTAINER = "container"
    RESOURCE_NODE = "resource_node"
    TRIGGER = "trigger"
    PORTAL = "portal"


class ItemRarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"
    ARTIFACT = "artifact"


class ItemType(Enum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    MATERIAL = "material"
    QUEST = "quest"
    CURRENCY = "currency"
    TOOL = "tool"
    ACCESSORY = "accessory"


class TerrainType(Enum):
    GRASSLAND = "grassland"
    FOREST = "forest"
    DESERT = "desert"
    MOUNTAIN = "mountain"
    SWAMP = "swamp"
    TUNDRA = "tundra"
    VOLCANIC = "volcanic"
    UNDERWATER = "underwater"
    DUNGEON = "dungeon"
    CITY = "city"


@dataclass
class GameObject:
    """Base class for all game objects in the world"""

    def __init__(self, name: str, position: Vector2, object_type: ObjectType = ObjectType.STATIC):
        self.id = str(uuid.uuid4())
        self.name = name
        self.position = position
        self.object_type = object_type

        # Physical properties
        self.solid = True  # Can agents pass through?
        self.visible = True
        self.size = Vector2(1, 1)
        self.rotation = 0.0

        # State
        self.active = True
        self.health = 100  # For destructible objects
        self.max_health = 100

        # Interaction properties
        self.interactable = object_type != ObjectType.STATIC
        self.interaction_range = 5.0
        self.required_level = 0
        self.required_items: List[str] = []

        # Events
        self.on_interact_callbacks: List[Any] = []
        self.on_destroy_callbacks: List[Any] = []

        logger.debug(f"GameObject {self.name} created at {position}")

    def fixed_update(self, delta_time: float):
        """Fixed timestep update for physics"""
        pass

    def interact(self, agent) -> Dict[str, Any]:
        """Handle interaction with an agent"""
        if not self.interactable:
            return {'success': False, 'message': 'Object is not interactable'}

        if not self._check_requirements(agent):
            return {'success': False, 'message': 'Requirements not met'}

        # Execute interaction callbacks
        for callback in self.on_interact_callbacks:
            callback(agent)

        return {'success': True, 'message': f'Interacted with {self.name}'}

    def _check_requirements(self, agent) -> bool:
        """Check if agent meets requirements to interact"""
        if agent.level < self.required_level:
            return False

        for item_id in self.required_items:
            if not self._has_item(agent, item_id):
                return False

        return True

    def _has_item(self, agent, item_id: str) -> bool:
        """Check if agent has a specific item"""
        return any(item.id == item_id for item in agent.inventory)

    def take_damage(self, amount: float):
        """Apply damage to the object"""
        if self.health <= 0:
            return

        self.health -= amount
        if self.health <= 0:
            self._destroy()

    def _destroy(self):
        """Destroy the object"""
        self.active = False
        for callback in self.on_destroy_callbacks:
            callback()
        logger.debug(f"GameObject {self.name} destroyed")


class Container(GameObject):
    """Container object that can hold items"""

    def __init__(self, name: str, position: Vector2):
        super().__init__(name, position, ObjectType.CONTAINER)
        self.inventory: List['Item'] = []
        self.max_capacity = 20
        self.locked = False
        self.lock_difficulty = 0

    def interact(self, agent) -> Dict[str, Any]:
        """Open container and access inventory"""
        result = super().interact(agent)
        if not result['success']:
            return result

        if self.locked:
            # Check if agent can unlock
            if not self._can_unlock(agent):
                return {'success': False, 'message': 'Container is locked'}
            self.locked = False

        return {
            'success': True,
            'type': 'container',
            'inventory': self.inventory,
            'message': f'Opened {self.name}'
        }

    def _can_unlock(self, agent) -> bool:
        """Check if agent can unlock the container"""
        # Simple skill check based on dexterity
        return agent.stats.dexterity >= self.lock_difficulty

    def add_item(self, item: 'Item') -> bool:
        """Add item to container"""
        if len(self.inventory) >= self.max_capacity:
            return False
        self.inventory.append(item)
        return True

    def remove_item(self, item_id: str) -> Optional['Item']:
        """Remove and return item from container"""
        for i, item in enumerate(self.inventory):
            if item.id == item_id:
                return self.inventory.pop(i)
        return None


class ResourceNode(GameObject):
    """Resource node that can be harvested"""

    def __init__(self, name: str, position: Vector2, resource_type: str):
        super().__init__(name, position, ObjectType.RESOURCE_NODE)
        self.resource_type = resource_type
        self.resources_remaining = random.randint(3, 10)
        self.respawn_time = 300.0  # 5 minutes
        self.last_harvest_time = 0.0
        self.required_tool_type = self._determine_required_tool()

    def _determine_required_tool(self) -> Optional[str]:
        """Determine required tool based on resource type"""
        tool_requirements = {
            'ore': 'pickaxe',
            'wood': 'axe',
            'herb': None,
            'crystal': 'pickaxe',
            'fish': 'fishing_rod'
        }
        return tool_requirements.get(self.resource_type)

    def interact(self, agent) -> Dict[str, Any]:
        """Harvest resources from the node"""
        result = super().interact(agent)
        if not result['success']:
            return result

        if self.resources_remaining <= 0:
            return {'success': False, 'message': 'Resource node is depleted'}

        if self.required_tool_type and not self._has_tool(agent):
            return {'success': False, 'message': f'Requires {self.required_tool_type}'}

        # Harvest resource
        harvested_item = self._create_resource_item()
        self.resources_remaining -= 1

        if self.resources_remaining <= 0:
            self._start_respawn_timer()

        return {
            'success': True,
            'type': 'harvest',
            'item': harvested_item,
            'message': f'Harvested {harvested_item.name}'
        }

    def _has_tool(self, agent) -> bool:
        """Check if agent has required tool"""
        for item in agent.inventory:
            if hasattr(item, 'tool_type') and item.tool_type == self.required_tool_type:
                return True
        return False

    def _create_resource_item(self) -> 'Item':
        """Create the harvested resource item"""
        return Item(
            name=f"{self.resource_type}",
            item_type=ItemType.MATERIAL,
            rarity=ItemRarity.COMMON
        )

    def _start_respawn_timer(self):
        """Start respawn timer for the resource"""
        import time
        self.last_harvest_time = time.time()
        self.visible = False

    def fixed_update(self, delta_time: float):
        """Check for respawn"""
        if self.resources_remaining <= 0:
            import time
            if time.time() - self.last_harvest_time >= self.respawn_time:
                self._respawn()

    def _respawn(self):
        """Respawn the resource node"""
        self.resources_remaining = random.randint(3, 10)
        self.visible = True
        logger.debug(f"Resource node {self.name} respawned")


class Portal(GameObject):
    """Portal for transportation between areas"""

    def __init__(self, name: str, position: Vector2, destination_area: str,
                 destination_position: Vector2):
        super().__init__(name, position, ObjectType.PORTAL)
        self.destination_area = destination_area
        self.destination_position = destination_position
        self.activation_cost = 0  # Could require items or currency
        self.level_requirement = 0

    def interact(self, agent) -> Dict[str, Any]:
        """Transport agent to destination"""
        result = super().interact(agent)
        if not result['success']:
            return result

        return {
            'success': True,
            'type': 'teleport',
            'destination_area': self.destination_area,
            'destination_position': self.destination_position,
            'message': f'Teleporting to {self.destination_area}'
        }


@dataclass
class Item:
    """Base class for all items"""

    def __init__(self, name: str, item_type: ItemType, rarity: ItemRarity = ItemRarity.COMMON):
        self.id = str(uuid.uuid4())
        self.name = name
        self.item_type = item_type
        self.rarity = rarity

        # Item properties
        self.value = self._calculate_value()
        self.weight = 1.0
        self.stackable = item_type in [ItemType.CONSUMABLE, ItemType.MATERIAL, ItemType.CURRENCY]
        self.max_stack = 99 if self.stackable else 1
        self.stack_count = 1

        # Requirements
        self.level_requirement = 0
        self.class_requirement: Optional[str] = None

        # Stats and effects
        self.stats_bonus: Dict[str, int] = {}
        self.effects: List[Dict[str, Any]] = []

        # Description
        self.description = f"A {rarity.value} {item_type.value}"
        self.lore_text = ""

        logger.debug(f"Item {self.name} created ({rarity.value} {item_type.value})")

    def _calculate_value(self) -> int:
        """Calculate item value based on rarity"""
        base_values = {
            ItemRarity.COMMON: 10,
            ItemRarity.UNCOMMON: 50,
            ItemRarity.RARE: 250,
            ItemRarity.EPIC: 1000,
            ItemRarity.LEGENDARY: 5000,
            ItemRarity.ARTIFACT: 25000
        }
        return base_values.get(self.rarity, 10)

    def use(self, agent) -> Dict[str, Any]:
        """Use the item"""
        if self.item_type != ItemType.CONSUMABLE:
            return {'success': False, 'message': 'Item cannot be used'}

        # Apply effects
        for effect in self.effects:
            self._apply_effect(agent, effect)

        # Consume the item
        self.stack_count -= 1

        return {
            'success': True,
            'message': f'Used {self.name}',
            'consumed': self.stack_count <= 0
        }

    def _apply_effect(self, agent, effect: Dict[str, Any]):
        """Apply an effect to the agent"""
        effect_type = effect.get('type')

        if effect_type == 'heal':
            amount = effect.get('amount', 0)
            agent.stats.health = min(agent.stats.max_health, agent.stats.health + amount)
        elif effect_type == 'mana':
            amount = effect.get('amount', 0)
            agent.stats.mana = min(agent.stats.max_mana, agent.stats.mana + amount)
        elif effect_type == 'buff':
            # Temporary stat increase
            stat = effect.get('stat')
            amount = effect.get('amount', 0)
            duration = effect.get('duration', 0)
            # This would need a buff system to track temporary effects

    def can_equip(self, agent) -> bool:
        """Check if agent can equip this item"""
        if self.item_type not in [ItemType.WEAPON, ItemType.ARMOR, ItemType.ACCESSORY]:
            return False

        if agent.level < self.level_requirement:
            return False

        if self.class_requirement and agent.character_class != self.class_requirement:
            return False

        return True


class Weapon(Item):
    """Weapon item with damage properties"""

    def __init__(self, name: str, weapon_type: str, damage: int,
                 rarity: ItemRarity = ItemRarity.COMMON):
        super().__init__(name, ItemType.WEAPON, rarity)
        self.weapon_type = weapon_type  # sword, bow, staff, etc.
        self.damage = damage
        self.attack_speed = 1.0
        self.crit_chance = 0.05
        self.damage_type = self._determine_damage_type()

        # Update stats bonus
        self.stats_bonus = {
            'strength': damage // 10,
            'dexterity': 0 if weapon_type != 'bow' else damage // 8
        }

    def _determine_damage_type(self) -> str:
        """Determine damage type based on weapon type"""
        magic_weapons = ['staff', 'wand', 'orb']
        if self.weapon_type in magic_weapons:
            return 'magical'
        return 'physical'


class Armor(Item):
    """Armor item with defense properties"""

    def __init__(self, name: str, armor_type: str, defense: int,
                 rarity: ItemRarity = ItemRarity.COMMON):
        super().__init__(name, ItemType.ARMOR, rarity)
        self.armor_type = armor_type  # chest, helmet, boots, etc.
        self.defense = defense
        self.magic_resistance = defense // 4

        # Update stats bonus
        self.stats_bonus = {
            'constitution': defense // 10,
            'wisdom': self.magic_resistance // 10
        }


@dataclass
class Terrain:
    """Terrain features that affect movement and combat"""

    def __init__(self, terrain_type: TerrainType, position: Vector2, size: Vector2):
        self.id = str(uuid.uuid4())
        self.terrain_type = terrain_type
        self.position = position
        self.size = size

        # Terrain effects
        self.movement_modifier = self._get_movement_modifier()
        self.visibility_modifier = self._get_visibility_modifier()
        self.combat_modifier = self._get_combat_modifier()

        # Environmental hazards
        self.has_hazard = terrain_type in [TerrainType.SWAMP, TerrainType.VOLCANIC]
        self.hazard_damage = 5.0 if self.has_hazard else 0
        self.hazard_interval = 2.0  # Damage every 2 seconds

        # Special properties
        self.blocks_movement = terrain_type == TerrainType.MOUNTAIN
        self.blocks_vision = terrain_type in [TerrainType.FOREST, TerrainType.MOUNTAIN]
        self.provides_cover = terrain_type in [TerrainType.FOREST, TerrainType.CITY]

        logger.debug(f"Terrain {terrain_type.value} created at {position}")

    def _get_movement_modifier(self) -> float:
        """Get movement speed modifier for this terrain"""
        modifiers = {
            TerrainType.GRASSLAND: 1.0,
            TerrainType.FOREST: 0.7,
            TerrainType.DESERT: 0.8,
            TerrainType.MOUNTAIN: 0.5,
            TerrainType.SWAMP: 0.4,
            TerrainType.TUNDRA: 0.6,
            TerrainType.VOLCANIC: 0.7,
            TerrainType.UNDERWATER: 0.3,
            TerrainType.DUNGEON: 0.9,
            TerrainType.CITY: 1.1
        }
        return modifiers.get(self.terrain_type, 1.0)

    def _get_visibility_modifier(self) -> float:
        """Get visibility modifier for this terrain"""
        modifiers = {
            TerrainType.GRASSLAND: 1.0,
            TerrainType.FOREST: 0.5,
            TerrainType.DESERT: 1.2,
            TerrainType.MOUNTAIN: 0.8,
            TerrainType.SWAMP: 0.6,
            TerrainType.TUNDRA: 1.1,
            TerrainType.VOLCANIC: 0.7,
            TerrainType.UNDERWATER: 0.3,
            TerrainType.DUNGEON: 0.6,
            TerrainType.CITY: 1.0
        }
        return modifiers.get(self.terrain_type, 1.0)

    def _get_combat_modifier(self) -> float:
        """Get combat effectiveness modifier"""
        modifiers = {
            TerrainType.GRASSLAND: 1.0,
            TerrainType.FOREST: 0.9,  # Trees provide cover
            TerrainType.DESERT: 0.95,  # Heat exhaustion
            TerrainType.MOUNTAIN: 1.1,  # High ground advantage
            TerrainType.SWAMP: 0.7,  # Difficult footing
            TerrainType.TUNDRA: 0.9,  # Cold affects performance
            TerrainType.VOLCANIC: 0.8,  # Environmental dangers
            TerrainType.UNDERWATER: 0.5,  # Severely limited combat
            TerrainType.DUNGEON: 0.95,  # Confined spaces
            TerrainType.CITY: 1.05  # Familiar terrain
        }
        return modifiers.get(self.terrain_type, 1.0)

    def fixed_update(self, delta_time: float):
        """Update terrain effects"""
        # Could implement dynamic terrain changes here
        pass

    def affects_position(self, position: Vector2) -> bool:
        """Check if a position is affected by this terrain"""
        return (self.position.x <= position.x <= self.position.x + self.size.x and
                self.position.y <= position.y <= self.position.y + self.size.y)