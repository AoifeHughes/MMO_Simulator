"""
Transactional Inventory System for MMO Architecture

This module provides atomic inventory operations with rollback capability,
ensuring inventory consistency even during server errors or network issues.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from shared.inventory import Inventory
from shared.items import Item, create_item

logger = logging.getLogger(__name__)


class TransactionType(Enum):
    """Types of inventory transactions"""

    ADD_ITEM = "add_item"
    REMOVE_ITEM = "remove_item"
    MOVE_ITEM = "move_item"
    EQUIP_ITEM = "equip_item"
    UNEQUIP_ITEM = "unequip_item"
    ADD_GOLD = "add_gold"
    REMOVE_GOLD = "remove_gold"


@dataclass
class InventoryTransaction:
    """Represents a single inventory transaction"""

    transaction_id: str
    agent_id: str
    transaction_type: TransactionType
    timestamp: float = field(default_factory=time.time)

    # Transaction parameters
    item_id: Optional[str] = None
    item_name: Optional[str] = None
    quantity: int = 1
    slot_index: Optional[int] = None
    equipment_slot: Optional[str] = None
    gold_amount: int = 0

    # Rollback data
    rollback_data: Dict[str, Any] = field(default_factory=dict)
    committed: bool = False
    rolled_back: bool = False

    # Results
    success: bool = False
    error_message: Optional[str] = None


class TransactionalInventory:
    """
    Thread-safe transactional wrapper around the base Inventory class.

    Provides atomic operations with rollback capability for reliable
    inventory management in a multiplayer environment.
    """

    def __init__(self, agent_id: str, base_inventory: Inventory):
        self.agent_id = agent_id
        self.inventory = base_inventory
        self.lock = threading.RLock()  # Reentrant lock for nested operations

        # Transaction tracking
        self.pending_transactions: Dict[str, InventoryTransaction] = {}
        self.transaction_history: List[InventoryTransaction] = []
        self.transaction_counter = 0

    def _generate_transaction_id(self) -> str:
        """Generate unique transaction ID"""
        self.transaction_counter += 1
        return f"{self.agent_id}_{self.transaction_counter}_{int(time.time() * 1000)}"

    def _create_transaction(
        self, transaction_type: TransactionType, **kwargs
    ) -> InventoryTransaction:
        """Create a new transaction"""
        transaction = InventoryTransaction(
            transaction_id=self._generate_transaction_id(),
            agent_id=self.agent_id,
            transaction_type=transaction_type,
            **kwargs,
        )
        self.pending_transactions[transaction.transaction_id] = transaction
        return transaction

    def _commit_transaction(self, transaction: InventoryTransaction):
        """Mark transaction as committed"""
        transaction.committed = True
        transaction.timestamp = time.time()

        # Move to history
        self.transaction_history.append(transaction)
        if len(self.transaction_history) > 1000:  # Keep last 1000 transactions
            self.transaction_history.pop(0)

        # Remove from pending
        if transaction.transaction_id in self.pending_transactions:
            del self.pending_transactions[transaction.transaction_id]

    def _rollback_transaction(self, transaction: InventoryTransaction) -> bool:
        """Rollback a transaction using stored rollback data"""
        if transaction.rolled_back or not transaction.rollback_data:
            return False

        try:
            transaction_type = transaction.transaction_type
            rollback_data = transaction.rollback_data

            if transaction_type == TransactionType.ADD_ITEM:
                # Remove the added item
                if "added_item_slot" in rollback_data:
                    slot_index = rollback_data["added_item_slot"]
                    if slot_index < len(self.inventory.slots):
                        self.inventory.slots[slot_index].clear()

            elif transaction_type == TransactionType.REMOVE_ITEM:
                # Restore the removed item
                if (
                    "removed_item" in rollback_data
                    and "removed_from_slot" in rollback_data
                ):
                    item_data = rollback_data["removed_item"]
                    slot_index = rollback_data["removed_from_slot"]
                    quantity = rollback_data["removed_quantity"]

                    # Recreate item and restore to slot
                    item = create_item(item_data["name"])
                    if item and slot_index < len(self.inventory.slots):
                        self.inventory.slots[slot_index].set_item(item, quantity)

            elif transaction_type == TransactionType.EQUIP_ITEM:
                # Unequip the item
                if "equipped_slot" in rollback_data:
                    slot = rollback_data["equipped_slot"]
                    if slot in self.inventory.equipped_items:
                        del self.inventory.equipped_items[slot]

                # Restore item to inventory if it was there
                if "inventory_slot" in rollback_data:
                    slot_index = rollback_data["inventory_slot"]
                    item_data = rollback_data["item_data"]
                    item = create_item(item_data["name"])
                    if item and slot_index < len(self.inventory.slots):
                        self.inventory.slots[slot_index].set_item(item, 1)

            elif transaction_type == TransactionType.ADD_GOLD:
                # Remove the added gold
                if "gold_added" in rollback_data:
                    self.inventory.gold -= rollback_data["gold_added"]
                    self.inventory.gold = max(0, self.inventory.gold)

            elif transaction_type == TransactionType.REMOVE_GOLD:
                # Restore the removed gold
                if "gold_removed" in rollback_data:
                    self.inventory.gold += rollback_data["gold_removed"]

            transaction.rolled_back = True
            logger.info(
                f"Rolled back transaction {transaction.transaction_id} for agent {self.agent_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to rollback transaction {transaction.transaction_id}: {e}"
            )
            return False

    def add_item_transactional(
        self, item: Item, quantity: int = 1
    ) -> InventoryTransaction:
        """Add item with transaction support"""
        with self.lock:
            transaction = self._create_transaction(
                TransactionType.ADD_ITEM, item_name=item.name, quantity=quantity
            )

            try:
                # Store rollback data before making changes
                transaction.rollback_data[
                    "inventory_state_before"
                ] = self.inventory.to_dict()

                # Attempt to add item
                added_count = self.inventory.add_item(item, quantity)

                if added_count > 0:
                    # Find which slot the item was added to for rollback
                    for i, slot in enumerate(self.inventory.slots):
                        if not slot.is_empty() and slot.item.name == item.name:
                            transaction.rollback_data["added_item_slot"] = i
                            break

                    transaction.success = True
                    transaction.rollback_data["actual_quantity_added"] = added_count
                    self._commit_transaction(transaction)

                    logger.debug(
                        f"Added {added_count} {item.name} to inventory for agent {self.agent_id}"
                    )
                else:
                    transaction.success = False
                    transaction.error_message = (
                        "Inventory full or item could not be added"
                    )

            except Exception as e:
                transaction.success = False
                transaction.error_message = str(e)
                logger.error(f"Error in add_item_transactional: {e}")

            return transaction

    def remove_item_transactional(
        self, item_name: str, quantity: int = 1
    ) -> InventoryTransaction:
        """Remove item with transaction support"""
        with self.lock:
            transaction = self._create_transaction(
                TransactionType.REMOVE_ITEM, item_name=item_name, quantity=quantity
            )

            try:
                # Find the item before removing
                item_slot = None
                for i, slot in enumerate(self.inventory.slots):
                    if not slot.is_empty() and slot.item.name == item_name:
                        item_slot = i
                        break

                if item_slot is not None:
                    slot = self.inventory.slots[item_slot]
                    # Store rollback data
                    transaction.rollback_data.update(
                        {
                            "removed_item": slot.item.to_dict(),
                            "removed_from_slot": item_slot,
                            "removed_quantity": min(quantity, slot.quantity),
                        }
                    )

                # Attempt to remove item
                removed_count = self.inventory.remove_item(item_name, quantity)

                if removed_count > 0:
                    transaction.success = True
                    transaction.rollback_data["actual_quantity_removed"] = removed_count
                    self._commit_transaction(transaction)

                    logger.debug(
                        f"Removed {removed_count} {item_name} from inventory for agent {self.agent_id}"
                    )
                else:
                    transaction.success = False
                    transaction.error_message = (
                        f"Item {item_name} not found or insufficient quantity"
                    )

            except Exception as e:
                transaction.success = False
                transaction.error_message = str(e)
                logger.error(f"Error in remove_item_transactional: {e}")

            return transaction

    def equip_item_transactional(self, item_id: str) -> InventoryTransaction:
        """Equip item with transaction support"""
        with self.lock:
            transaction = self._create_transaction(
                TransactionType.EQUIP_ITEM, item_id=item_id
            )

            try:
                # Find item in inventory
                item_slot = None
                for i, slot in enumerate(self.inventory.slots):
                    if not slot.is_empty() and slot.item.item_id == item_id:
                        item_slot = i
                        break

                if item_slot is None:
                    transaction.success = False
                    transaction.error_message = "Item not found in inventory"
                    return transaction

                item = self.inventory.slots[item_slot].item

                # Store rollback data
                transaction.rollback_data.update(
                    {"item_data": item.to_dict(), "inventory_slot": item_slot}
                )

                # Attempt to equip
                success = self.inventory.equip_item(item_id)

                if success:
                    transaction.success = True
                    # Store which slot it was equipped to
                    if hasattr(item, "slot"):
                        transaction.rollback_data["equipped_slot"] = item.slot

                    self._commit_transaction(transaction)
                    logger.debug(f"Equipped item {item.name} for agent {self.agent_id}")
                else:
                    transaction.success = False
                    transaction.error_message = "Failed to equip item"

            except Exception as e:
                transaction.success = False
                transaction.error_message = str(e)
                logger.error(f"Error in equip_item_transactional: {e}")

            return transaction

    def add_gold_transactional(self, amount: int) -> InventoryTransaction:
        """Add gold with transaction support"""
        with self.lock:
            transaction = self._create_transaction(
                TransactionType.ADD_GOLD, gold_amount=amount
            )

            try:
                old_gold = self.inventory.gold
                self.inventory.add_gold(amount)

                transaction.success = True
                transaction.rollback_data["gold_added"] = amount
                transaction.rollback_data["gold_before"] = old_gold
                self._commit_transaction(transaction)

                logger.debug(
                    f"Added {amount} gold to agent {self.agent_id} (total: {self.inventory.gold})"
                )

            except Exception as e:
                transaction.success = False
                transaction.error_message = str(e)
                logger.error(f"Error in add_gold_transactional: {e}")

            return transaction

    def remove_gold_transactional(self, amount: int) -> InventoryTransaction:
        """Remove gold with transaction support"""
        with self.lock:
            transaction = self._create_transaction(
                TransactionType.REMOVE_GOLD, gold_amount=amount
            )

            try:
                if self.inventory.gold < amount:
                    transaction.success = False
                    transaction.error_message = f"Insufficient gold (have: {self.inventory.gold}, need: {amount})"
                    return transaction

                old_gold = self.inventory.gold
                self.inventory.gold -= amount

                transaction.success = True
                transaction.rollback_data["gold_removed"] = amount
                transaction.rollback_data["gold_before"] = old_gold
                self._commit_transaction(transaction)

                logger.debug(
                    f"Removed {amount} gold from agent {self.agent_id} (remaining: {self.inventory.gold})"
                )

            except Exception as e:
                transaction.success = False
                transaction.error_message = str(e)
                logger.error(f"Error in remove_gold_transactional: {e}")

            return transaction

    def rollback_last_transaction(self) -> bool:
        """Rollback the most recent transaction"""
        with self.lock:
            if not self.transaction_history:
                return False

            last_transaction = self.transaction_history[-1]
            return self._rollback_transaction(last_transaction)

    def rollback_transaction_by_id(self, transaction_id: str) -> bool:
        """Rollback a specific transaction by ID"""
        with self.lock:
            # Check pending transactions first
            if transaction_id in self.pending_transactions:
                transaction = self.pending_transactions[transaction_id]
                return self._rollback_transaction(transaction)

            # Check transaction history
            for transaction in reversed(self.transaction_history):
                if transaction.transaction_id == transaction_id:
                    return self._rollback_transaction(transaction)

            return False

    def get_transaction_history(self, limit: int = 50) -> List[InventoryTransaction]:
        """Get recent transaction history"""
        with self.lock:
            return list(reversed(self.transaction_history[-limit:]))

    def get_stats(self) -> Dict[str, Any]:
        """Get inventory transaction statistics"""
        with self.lock:
            successful_transactions = sum(
                1 for t in self.transaction_history if t.success
            )
            failed_transactions = sum(
                1 for t in self.transaction_history if not t.success
            )

            return {
                "total_transactions": len(self.transaction_history),
                "successful_transactions": successful_transactions,
                "failed_transactions": failed_transactions,
                "pending_transactions": len(self.pending_transactions),
                "success_rate": successful_transactions
                / max(1, len(self.transaction_history)),
            }


class InventoryManager:
    """
    Global manager for all agent inventories with transaction support.

    This provides a centralized point for inventory operations across
    the entire MMO server.
    """

    def __init__(self):
        self.agent_inventories: Dict[str, TransactionalInventory] = {}
        self.lock = threading.Lock()

    def get_or_create_inventory(
        self, agent_id: str, base_inventory: Optional[Inventory] = None
    ) -> TransactionalInventory:
        """Get or create transactional inventory for agent"""
        with self.lock:
            if agent_id not in self.agent_inventories:
                if base_inventory is None:
                    base_inventory = Inventory()

                self.agent_inventories[agent_id] = TransactionalInventory(
                    agent_id, base_inventory
                )
                logger.debug(f"Created transactional inventory for agent {agent_id}")

            return self.agent_inventories[agent_id]

    def remove_inventory(self, agent_id: str):
        """Remove agent inventory (for cleanup when agent disconnects)"""
        with self.lock:
            if agent_id in self.agent_inventories:
                del self.agent_inventories[agent_id]
                logger.debug(f"Removed inventory for agent {agent_id}")

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all agent inventories"""
        with self.lock:
            total_transactions = 0
            total_successful = 0
            total_failed = 0

            for inventory in self.agent_inventories.values():
                stats = inventory.get_stats()
                total_transactions += stats["total_transactions"]
                total_successful += stats["successful_transactions"]
                total_failed += stats["failed_transactions"]

            return {
                "active_inventories": len(self.agent_inventories),
                "total_transactions": total_transactions,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "overall_success_rate": total_successful / max(1, total_transactions),
            }
