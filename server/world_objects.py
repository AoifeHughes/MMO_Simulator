"""
World Objects System for temporary objects like fires, crafted items, etc.

This module manages temporary objects that exist in the world for a limited time
and can be detected by agents within their vision range.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class WorldObjectType(Enum):
    """Types of world objects"""
    FIRE = "fire"
    CAMPFIRE = "campfire"
    CRAFTING_STATION = "crafting_station"


@dataclass
class WorldObject:
    """Represents a temporary object in the world"""
    object_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    object_type: WorldObjectType = WorldObjectType.FIRE
    position: Tuple[float, float] = (0.0, 0.0)
    created_time: float = field(default_factory=time.time)
    duration: float = 300.0  # 5 minutes default
    created_by: Optional[str] = None  # Agent ID who created it

    # Object properties
    properties: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if the object has expired"""
        return time.time() - self.created_time >= self.duration

    def time_remaining(self) -> float:
        """Get time remaining before expiration"""
        remaining = self.duration - (time.time() - self.created_time)
        return max(0.0, remaining)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for client transmission"""
        return {
            "object_id": self.object_id,
            "object_type": self.object_type.value,
            "position": self.position,
            "created_time": self.created_time,
            "duration": self.duration,
            "time_remaining": self.time_remaining(),
            "created_by": self.created_by,
            "properties": self.properties.copy()
        }


class WorldObjectManager:
    """Manages all world objects with automatic expiration"""

    def __init__(self):
        self.objects: Dict[str, WorldObject] = {}
        self.last_cleanup = time.time()
        self.cleanup_interval = 10.0  # Cleanup every 10 seconds

    def create_fire(self, x: float, y: float, created_by: Optional[str] = None, duration: float = 300.0) -> WorldObject:
        """Create a fire object that expires after duration seconds"""
        fire = WorldObject(
            object_type=WorldObjectType.FIRE,
            position=(x, y),
            duration=duration,
            created_by=created_by,
            properties={
                "heat_radius": 3.0,
                "light_radius": 5.0,
                "can_cook": True
            }
        )

        self.objects[fire.object_id] = fire
        return fire

    def create_campfire(self, x: float, y: float, created_by: Optional[str] = None) -> WorldObject:
        """Create a longer-lasting campfire"""
        campfire = WorldObject(
            object_type=WorldObjectType.CAMPFIRE,
            position=(x, y),
            duration=900.0,  # 15 minutes
            created_by=created_by,
            properties={
                "heat_radius": 5.0,
                "light_radius": 8.0,
                "can_cook": True,
                "upgraded_fire": True
            }
        )

        self.objects[campfire.object_id] = campfire
        return campfire

    def remove_object(self, object_id: str) -> bool:
        """Remove a world object"""
        if object_id in self.objects:
            del self.objects[object_id]
            return True
        return False

    def get_object(self, object_id: str) -> Optional[WorldObject]:
        """Get a world object by ID"""
        return self.objects.get(object_id)

    def get_objects_near(self, x: float, y: float, radius: float) -> List[WorldObject]:
        """Get all objects within radius of position"""
        nearby = []
        for obj in self.objects.values():
            obj_x, obj_y = obj.position
            distance = ((x - obj_x) ** 2 + (y - obj_y) ** 2) ** 0.5
            if distance <= radius:
                nearby.append(obj)
        return nearby

    def get_fires_near(self, x: float, y: float, radius: float) -> List[WorldObject]:
        """Get all fire objects within radius"""
        fires = []
        for obj in self.get_objects_near(x, y, radius):
            if obj.object_type in [WorldObjectType.FIRE, WorldObjectType.CAMPFIRE]:
                fires.append(obj)
        return fires

    def cleanup_expired_objects(self) -> int:
        """Remove expired objects, returns number removed"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return 0

        expired_ids = []
        for obj_id, obj in self.objects.items():
            if obj.is_expired():
                expired_ids.append(obj_id)

        for obj_id in expired_ids:
            del self.objects[obj_id]

        self.last_cleanup = current_time
        return len(expired_ids)

    def update(self) -> int:
        """Update world objects and cleanup expired ones"""
        return self.cleanup_expired_objects()

    def get_all_objects(self) -> List[WorldObject]:
        """Get all active world objects"""
        return list(self.objects.values())

    def get_objects_by_type(self, object_type: WorldObjectType) -> List[WorldObject]:
        """Get all objects of a specific type"""
        return [obj for obj in self.objects.values() if obj.object_type == object_type]

    def to_dict(self) -> Dict[str, Any]:
        """Convert all objects to dictionary for client transmission"""
        return {
            "objects": [obj.to_dict() for obj in self.objects.values()],
            "total_objects": len(self.objects)
        }


# Crafting Recipes System
@dataclass
class CraftingRecipe:
    """Defines what ingredients are needed to craft an item"""
    recipe_name: str
    required_items: Dict[str, int]  # item_name -> quantity
    result_object: WorldObjectType
    result_duration: float = 300.0  # Default 5 minutes
    craft_time: float = 2.0  # Time to complete crafting

    def can_craft(self, inventory_items: Dict[str, int]) -> bool:
        """Check if agent has required items to craft"""
        for item_name, required_qty in self.required_items.items():
            if inventory_items.get(item_name, 0) < required_qty:
                return False
        return True

    def consume_ingredients(self, inventory_items: Dict[str, int]) -> Dict[str, int]:
        """Remove required items from inventory, return updated inventory"""
        updated = inventory_items.copy()
        for item_name, required_qty in self.required_items.items():
            updated[item_name] -= required_qty
            if updated[item_name] <= 0:
                del updated[item_name]
        return updated


# Default crafting recipes
CRAFTING_RECIPES = {
    "basic_fire": CraftingRecipe(
        recipe_name="basic_fire",
        required_items={"wood": 2},
        result_object=WorldObjectType.FIRE,
        result_duration=300.0,  # 5 minutes
        craft_time=3.0
    ),
    "campfire": CraftingRecipe(
        recipe_name="campfire",
        required_items={"wood": 5},
        result_object=WorldObjectType.CAMPFIRE,
        result_duration=900.0,  # 15 minutes
        craft_time=5.0
    )
}


def get_recipe(recipe_name: str) -> Optional[CraftingRecipe]:
    """Get a crafting recipe by name"""
    return CRAFTING_RECIPES.get(recipe_name)


def get_available_recipes() -> Dict[str, CraftingRecipe]:
    """Get all available crafting recipes"""
    return CRAFTING_RECIPES.copy()