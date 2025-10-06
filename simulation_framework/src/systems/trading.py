from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from ..entities.base import Entity


class TradeStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class TradeOffer:
    """Represents a trade offer between two entities"""

    id: int
    initiator_id: int
    target_id: int
    offered_items: List[Tuple[str, int]]  # (item_name, quantity)
    requested_items: List[Tuple[str, int]]  # (item_name, quantity)
    offered_gold: int = 0
    requested_gold: int = 0
    status: TradeStatus = TradeStatus.PENDING
    created_tick: int = 0
    expires_tick: int = 0

    def is_expired(self, current_tick: int) -> bool:
        return current_tick >= self.expires_tick

    def get_total_offered_value(self) -> float:
        """Calculate total value of offered items and gold"""
        # Simplified value calculation - could be made more sophisticated
        item_value = sum(
            self._get_item_base_value(item) * qty for item, qty in self.offered_items
        )
        return item_value + self.offered_gold

    def get_total_requested_value(self) -> float:
        """Calculate total value of requested items and gold"""
        item_value = sum(
            self._get_item_base_value(item) * qty for item, qty in self.requested_items
        )
        return item_value + self.requested_gold

    def _get_item_base_value(self, item_name: str) -> float:
        """Get base market value of an item"""
        # Simplified item values - in a full system this would come from market data
        item_values = {
            "Wood": 2.0,
            "Stone": 1.5,
            "Iron Ore": 5.0,
            "Gold Ore": 15.0,
            "Berries": 1.0,
            "Herbs": 3.0,
            "Fish": 2.5,
            "Bread": 4.0,
            "Health Potion": 25.0,
            "Wooden Sword": 15.0,
            "Stone Axe": 20.0,
            "Iron Sword": 75.0,
        }
        return item_values.get(item_name, 1.0)


class Market:
    """Central market system for tracking supply, demand, and prices"""

    def __init__(self):
        self.item_prices: Dict[str, float] = {}
        self.supply: Dict[str, int] = {}
        self.demand: Dict[str, int] = {}
        self.price_history: Dict[str, List[float]] = {}
        self.trade_volume: Dict[str, int] = {}

        # Initialize with base prices
        self._initialize_base_prices()

    def _initialize_base_prices(self) -> None:
        """Set up initial market prices"""
        base_prices = {
            "Wood": 2.0,
            "Stone": 1.5,
            "Iron Ore": 5.0,
            "Gold Ore": 15.0,
            "Berries": 1.0,
            "Herbs": 3.0,
            "Fish": 2.5,
            "Bread": 4.0,
            "Health Potion": 25.0,
            "Wooden Sword": 15.0,
            "Stone Axe": 20.0,
            "Iron Sword": 75.0,
        }

        for item, price in base_prices.items():
            self.item_prices[item] = price
            self.supply[item] = 100  # Start with balanced supply
            self.demand[item] = 100  # Start with balanced demand
            self.price_history[item] = [price]
            self.trade_volume[item] = 0

    def update_supply(self, item_name: str, change: int) -> None:
        """Update supply of an item"""
        if item_name not in self.supply:
            self.supply[item_name] = 100

        self.supply[item_name] = max(0, self.supply[item_name] + change)
        self._recalculate_price(item_name)

    def update_demand(self, item_name: str, change: int) -> None:
        """Update demand for an item"""
        if item_name not in self.demand:
            self.demand[item_name] = 100

        self.demand[item_name] = max(1, self.demand[item_name] + change)
        self._recalculate_price(item_name)

    def record_trade(self, item_name: str, quantity: int, price: float) -> None:
        """Record a completed trade"""
        if item_name not in self.trade_volume:
            self.trade_volume[item_name] = 0

        self.trade_volume[item_name] += quantity

        # Update supply and demand based on trade
        self.update_supply(item_name, -quantity)  # Reduce supply
        self.update_demand(item_name, quantity)  # Increase demand

    def _recalculate_price(self, item_name: str) -> None:
        """Recalculate price based on supply and demand"""
        if item_name not in self.item_prices:
            return

        supply = self.supply.get(item_name, 100)
        demand = self.demand.get(item_name, 100)

        # Simple supply/demand pricing model
        base_price = self.price_history[item_name][0]  # Original price
        supply_factor = 100.0 / max(supply, 10)  # Lower supply = higher price
        demand_factor = demand / 100.0  # Higher demand = higher price

        new_price = base_price * supply_factor * demand_factor

        # Limit price volatility
        current_price = self.item_prices[item_name]
        max_change = current_price * 0.2  # Max 20% change per update
        new_price = max(
            current_price - max_change, min(current_price + max_change, new_price)
        )

        # Ensure minimum price
        new_price = max(new_price, base_price * 0.1)

        self.item_prices[item_name] = new_price
        self.price_history[item_name].append(new_price)

        # Keep price history limited
        if len(self.price_history[item_name]) > 100:
            self.price_history[item_name] = self.price_history[item_name][-50:]

    def get_price(self, item_name: str) -> float:
        """Get current market price of an item"""
        return self.item_prices.get(item_name, 1.0)

    def get_current_prices(self) -> Dict[str, float]:
        """Get current market prices"""
        return self.item_prices.copy()

    def update_prices(self, current_tick: int) -> None:
        """Update market prices based on time and market dynamics"""
        # Recalculate all prices
        for item_name in list(self.item_prices.keys()):
            self._recalculate_price(item_name)

    def get_market_summary(self) -> Dict:
        """Get current market state summary"""
        return {
            "prices": self.item_prices.copy(),
            "supply": self.supply.copy(),
            "demand": self.demand.copy(),
            "trade_volume": self.trade_volume.copy(),
        }


class TradingSystem:
    """Manages trading between entities"""

    def __init__(self):
        self.market = Market()
        self.pending_offers: Dict[int, TradeOffer] = {}
        self.next_offer_id = 1
        self.trade_history: List[Dict] = []

    def create_trade_offer(
        self,
        initiator: Entity,
        target: Entity,
        offered_items: List[Tuple[str, int]] = None,
        requested_items: List[Tuple[str, int]] = None,
        offered_gold: int = 0,
        requested_gold: int = 0,
        duration: int = 100,
    ) -> Optional[TradeOffer]:
        """Create a new trade offer"""

        if not self._can_trade(initiator, target):
            return None

        # Validate that initiator has the offered items
        if offered_items:
            for item_name, quantity in offered_items:
                if not initiator.inventory.has_item(item_name, quantity):
                    return None

        if offered_gold > 0 and initiator.inventory.gold < offered_gold:
            return None

        # Create the offer
        offer = TradeOffer(
            id=self.next_offer_id,
            initiator_id=initiator.id,
            target_id=target.id,
            offered_items=offered_items or [],
            requested_items=requested_items or [],
            offered_gold=offered_gold,
            requested_gold=requested_gold,
            created_tick=0,  # Will be set by caller
            expires_tick=duration,
        )

        self.pending_offers[self.next_offer_id] = offer
        self.next_offer_id += 1

        return offer

    def evaluate_trade_offer(self, target: Entity, offer_id: int) -> Tuple[bool, float]:
        """Evaluate a trade offer and return (should_accept, utility_score)"""

        if offer_id not in self.pending_offers:
            return False, 0.0

        offer = self.pending_offers[offer_id]

        if offer.target_id != target.id:
            return False, 0.0

        # Check if target has requested items
        if offer.requested_items:
            for item_name, quantity in offer.requested_items:
                if not target.inventory.has_item(item_name, quantity):
                    return False, 0.0

        if offer.requested_gold > 0 and target.inventory.gold < offer.requested_gold:
            return False, 0.0

        # Calculate utility of the trade
        utility_score = self._calculate_trade_utility(target, offer)

        # Decision based on personality and utility
        should_accept = self._should_accept_trade(target, offer, utility_score)

        return should_accept, utility_score

    def _calculate_trade_utility(self, entity: Entity, offer: TradeOffer) -> float:
        """Calculate how beneficial a trade is for an entity"""

        offered_value = 0.0
        requested_value = 0.0

        # Calculate value of offered items to the entity
        for item_name, quantity in offer.offered_items:
            market_price = self.market.get_price(item_name)
            personal_value = self._get_personal_item_value(entity, item_name)
            offered_value += quantity * (market_price * personal_value)

        offered_value += offer.offered_gold

        # Calculate value of requested items from the entity
        for item_name, quantity in offer.requested_items:
            market_price = self.market.get_price(item_name)
            personal_value = self._get_personal_item_value(entity, item_name)
            requested_value += quantity * (market_price * personal_value)

        requested_value += offer.requested_gold

        # Utility is the difference (positive = good deal)
        if requested_value == 0:
            return 1.0 if offered_value > 0 else 0.0

        return offered_value / requested_value

    def _get_personal_item_value(self, entity: Entity, item_name: str) -> float:
        """Get how much an entity values a specific item"""
        base_multiplier = 1.0

        # Character class preferences
        if hasattr(entity, "character_class"):
            class_name = entity.character_class.name

            if class_name == "Warrior" and "Sword" in item_name:
                base_multiplier = 1.5
            elif class_name == "Alchemist" and item_name in ["Herbs", "Health Potion"]:
                base_multiplier = 1.4
            elif class_name == "Blacksmith" and item_name in ["Iron Ore", "Stone"]:
                base_multiplier = 1.3
            elif class_name == "Hunter" and item_name in ["Wood", "Fish"]:
                base_multiplier = 1.3

        # Personality modifiers
        if hasattr(entity, "personality"):
            if entity.personality.greed > 0.7:
                if item_name == "Gold Ore" or "gold" in item_name.lower():
                    base_multiplier *= 1.3

        # Need-based valuation
        current_amount = entity.inventory.get_item_count(item_name)
        if current_amount == 0:
            base_multiplier *= 1.2  # Want items we don't have
        elif current_amount > 10:
            base_multiplier *= 0.8  # Less interested in items we have many of

        return base_multiplier

    def _should_accept_trade(
        self, entity: Entity, offer: TradeOffer, utility: float
    ) -> bool:
        """Determine if an entity should accept a trade offer"""

        # Base acceptance threshold
        threshold = 1.0  # Only accept if we get equal or better value

        # Personality modifiers
        if hasattr(entity, "personality"):
            # Greedy entities want better deals
            if entity.personality.greed > 0.6:
                threshold = 1.2

            # Sociable entities are more willing to trade
            if entity.personality.sociability > 0.6:
                threshold *= 0.9

            # Cautious entities want much better deals
            if entity.personality.caution > 0.7:
                threshold *= 1.3

        # Relationship modifier (if implemented)
        if (
            hasattr(entity, "relationships")
            and offer.initiator_id in entity.relationships
        ):
            relationship = entity.relationships[offer.initiator_id]
            threshold *= (
                1.0 - relationship * 0.2
            )  # Better relationships = lower threshold

        return utility >= threshold

    def accept_trade_offer(self, accepter: Entity, offer_id: int) -> bool:
        """Accept a trade offer and execute the trade"""

        if offer_id not in self.pending_offers:
            return False

        offer = self.pending_offers[offer_id]

        if offer.target_id != accepter.id or offer.status != TradeStatus.PENDING:
            return False

        # Find the initiator
        # This would need world context - simplified for now
        # In a full implementation, this would get the initiator from the world
        initiator = None  # Would be: world.get_entity(offer.initiator_id)

        if not initiator:
            offer.status = TradeStatus.CANCELLED
            return False

        # Execute the trade
        success = self._execute_trade(initiator, accepter, offer)

        if success:
            offer.status = TradeStatus.COMPLETED
            self._record_trade_history(offer)
        else:
            offer.status = TradeStatus.REJECTED

        return success

    def _execute_trade(
        self, initiator: Entity, accepter: Entity, offer: TradeOffer
    ) -> bool:
        """Execute the actual trade transaction"""

        # Validate both parties still have required items
        for item_name, quantity in offer.offered_items:
            if not initiator.inventory.has_item(item_name, quantity):
                return False

        for item_name, quantity in offer.requested_items:
            if not accepter.inventory.has_item(item_name, quantity):
                return False

        if offer.offered_gold > initiator.inventory.gold:
            return False

        if offer.requested_gold > accepter.inventory.gold:
            return False

        # Execute the trade
        try:
            # Remove items from initiator, give to accepter
            for item_name, quantity in offer.offered_items:
                initiator.inventory.remove_item(item_name, quantity)
                # In full implementation, would create Item objects
                # accepter.inventory.add_item(Item(...), quantity)

            # Remove items from accepter, give to initiator
            for item_name, quantity in offer.requested_items:
                accepter.inventory.remove_item(item_name, quantity)
                # initiator.inventory.add_item(Item(...), quantity)

            # Handle gold transfer
            if offer.offered_gold > 0:
                initiator.inventory.gold -= offer.offered_gold
                accepter.inventory.gold += offer.offered_gold

            if offer.requested_gold > 0:
                accepter.inventory.gold -= offer.requested_gold
                initiator.inventory.gold += offer.requested_gold

            # Update market data
            for item_name, quantity in offer.offered_items + offer.requested_items:
                price = self.market.get_price(item_name)
                self.market.record_trade(item_name, quantity, price)

            # Update relationships
            if hasattr(initiator, "add_relationship"):
                initiator.add_relationship(accepter.id, 0.1)
            if hasattr(accepter, "add_relationship"):
                accepter.add_relationship(initiator.id, 0.1)

            return True

        except Exception:
            return False

    def reject_trade_offer(self, rejector: Entity, offer_id: int) -> bool:
        """Reject a trade offer"""

        if offer_id not in self.pending_offers:
            return False

        offer = self.pending_offers[offer_id]

        if offer.target_id != rejector.id:
            return False

        offer.status = TradeStatus.REJECTED
        return True

    def _can_trade(self, entity1: Entity, entity2: Entity) -> bool:
        """Check if two entities can trade with each other"""

        # Check if both are alive
        if not (entity1.stats.is_alive() and entity2.stats.is_alive()):
            return False

        # Check distance (simplified - in full game would check actual positions)
        if hasattr(entity1, "distance_to"):
            distance = entity1.distance_to(entity2)
            if distance > 2:  # Must be adjacent or very close
                return False

        # Check hostility
        if hasattr(entity1, "is_hostile_to") and entity1.is_hostile_to(entity2):
            return False

        if hasattr(entity2, "is_hostile_to") and entity2.is_hostile_to(entity1):
            return False

        return True

    def _record_trade_history(self, offer: TradeOffer) -> None:
        """Record completed trade in history"""

        trade_record = {
            "offer_id": offer.id,
            "initiator_id": offer.initiator_id,
            "target_id": offer.target_id,
            "offered_items": offer.offered_items.copy(),
            "requested_items": offer.requested_items.copy(),
            "offered_gold": offer.offered_gold,
            "requested_gold": offer.requested_gold,
            "completed_tick": offer.expires_tick,  # Simplified
        }

        self.trade_history.append(trade_record)

        # Keep history limited
        if len(self.trade_history) > 1000:
            self.trade_history = self.trade_history[-500:]

    def cleanup_expired_offers(self, current_tick: int) -> None:
        """Remove expired trade offers"""

        expired_offers = [
            offer_id
            for offer_id, offer in self.pending_offers.items()
            if offer.is_expired(current_tick) and offer.status == TradeStatus.PENDING
        ]

        for offer_id in expired_offers:
            self.pending_offers[offer_id].status = TradeStatus.CANCELLED
            del self.pending_offers[offer_id]

    def get_pending_offers_for_entity(self, entity_id: int) -> List[TradeOffer]:
        """Get all pending trade offers for an entity"""

        return [
            offer
            for offer in self.pending_offers.values()
            if offer.target_id == entity_id and offer.status == TradeStatus.PENDING
        ]

    def update(self, current_tick: int) -> None:
        """Update trading system - clean up expired offers"""
        self.cleanup_expired_offers(current_tick)

    def get_completed_trades(self) -> List[Dict]:
        """Get list of completed trades (for logging)"""
        return [trade for trade in self.trade_history if trade]

    def get_trade_summary(self) -> Dict:
        """Get trading system summary for debugging"""
        return {
            "pending_offers": len(self.pending_offers),
            "completed_trades": len([t for t in self.trade_history if t]),
            "market_summary": self.market.get_market_summary(),
            "next_offer_id": self.next_offer_id,
        }
