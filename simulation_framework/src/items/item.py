from __future__ import annotations
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class Item:
    id: int
    name: str
    item_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    value: int = 0
    weight: float = 1.0
    max_stack_size: int = 99

    def can_stack(self) -> bool:
        return self.max_stack_size > 1

    def get_property(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def set_property(self, key: str, value: Any) -> None:
        self.properties[key] = value

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Item:
        return cls(
            id=data.get("id", 0),
            name=data["name"],
            item_type=data["type"],
            properties=data.get("properties", {}),
            description=data.get("description", ""),
            value=data.get("value", 0),
            weight=data.get("weight", 1.0),
            max_stack_size=data.get("max_stack", 99)
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.item_type,
            "properties": self.properties,
            "description": self.description,
            "value": self.value,
            "weight": self.weight,
            "max_stack": self.max_stack_size
        }

    def __hash__(self) -> int:
        return hash((self.id, self.name, self.item_type))

    def __eq__(self, other) -> bool:
        if not isinstance(other, Item):
            return False
        return self.id == other.id and self.name == other.name

    def __repr__(self) -> str:
        return f"Item({self.name}, type={self.item_type})"