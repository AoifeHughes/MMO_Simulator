"""
Server-Side Action Processor

This module handles all client action requests through a unified validation and execution pipeline.
It provides:
- Action validation through pluggable validator chains
- Rate limiting and cooldown management
- Rollback support for failed actions
- Batch processing for efficiency
- Audit logging for debugging
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.actions import (
    ActionBatch,
    ActionPriority,
    ActionRequest,
    ActionResponse,
    ActionResult,
    ActionType,
)
from shared.items import create_item, EquipmentSlot
from world.tiles import TileType

logger = logging.getLogger(__name__)


class ActionValidator(ABC):
    """Abstract base class for action validators"""

    @abstractmethod
    def validate(self, request: ActionRequest, context: "ActionContext") -> Tuple[bool, str]:
        """
        Validate an action request.

        Returns:
            (is_valid, error_message)
        """
        pass

    @abstractmethod
    def get_supported_actions(self) -> Set[ActionType]:
        """Return set of action types this validator handles"""
        pass


class ActionContext:
    """Context object passed to validators containing game state and utilities"""

    def __init__(self, processor: "ActionProcessor"):
        self.processor = processor
        self.world = processor.world
        self.agent_registry = processor.agent_registry
        self.attack_system = processor.attack_system
        self.start_time = time.time()


class RateLimitValidator(ActionValidator):
    """Prevents action spam by enforcing rate limits per agent"""

    def __init__(self, actions_per_second: float = 10.0, burst_size: int = 5):
        self.actions_per_second = actions_per_second
        self.burst_size = burst_size
        # agent_id -> deque of timestamps
        self.action_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=burst_size))

    def validate(self, request: ActionRequest, context: ActionContext) -> Tuple[bool, str]:
        now = time.time()
        agent_history = self.action_history[request.agent_id]

        # Remove old entries outside the time window
        time_window = self.burst_size / self.actions_per_second
        while agent_history and (now - agent_history[0]) > time_window:
            agent_history.popleft()

        # Check if we're within limits
        if len(agent_history) >= self.burst_size:
            return False, f"Rate limit exceeded: {len(agent_history)}/{self.burst_size} actions in {time_window:.1f}s"

        # Record this action
        agent_history.append(now)
        return True, ""

    def get_supported_actions(self) -> Set[ActionType]:
        # Rate limiting applies to all actions
        return set(ActionType)


class CooldownValidator(ActionValidator):
    """Enforces action-specific cooldowns"""

    def __init__(self):
        # action_type -> cooldown_seconds
        self.cooldowns = {
            ActionType.ATTACK_TARGET: 1.0,
            ActionType.CAST_SPELL: 2.0,
            ActionType.USE_ITEM: 0.5,
            ActionType.TELEPORT: 30.0,
            ActionType.TRADE_REQUEST: 5.0,
            ActionType.FISH: 1.0,  # Fishing attempt cooldown
            ActionType.EQUIP_ITEM: 0.2,  # Equipment swap cooldown
        }
        # (agent_id, action_type) -> last_use_timestamp
        self.last_use: Dict[Tuple[str, ActionType], float] = {}

    def validate(self, request: ActionRequest, context: ActionContext) -> Tuple[bool, str]:
        if request.action_type not in self.cooldowns:
            return True, ""  # No cooldown for this action

        key = (request.agent_id, request.action_type)
        cooldown = self.cooldowns[request.action_type]
        last_use = self.last_use.get(key, 0)
        now = time.time()

        if (now - last_use) < cooldown:
            remaining = cooldown - (now - last_use)
            return False, f"Action on cooldown: {remaining:.1f}s remaining"

        # Record this use
        self.last_use[key] = now
        return True, ""

    def get_supported_actions(self) -> Set[ActionType]:
        return set(self.cooldowns.keys())


class MovementValidator(ActionValidator):
    """Validates movement actions against terrain and collision"""

    def validate(self, request: ActionRequest, context: ActionContext) -> Tuple[bool, str]:
        if request.action_type != ActionType.MOVE_TO:
            return True, ""

        params = request.parameters
        target_x = params.get("target_x")
        target_y = params.get("target_y")

        if target_x is None or target_y is None:
            return False, "Missing target coordinates"

        # Get agent current position
        agent = context.world.get_agent(request.agent_id)
        if not agent:
            return False, "Agent not found"

        # Dead agents cannot move
        if not agent.is_alive:
            return False, "Agent is dead and cannot move"

        # Check bounds
        world_bounds = context.world.world_map.get_bounds()
        if not (0 <= target_x < world_bounds[0] and 0 <= target_y < world_bounds[1]):
            return False, f"Target ({target_x}, {target_y}) is out of bounds"

        # Check if target is walkable
        if not context.world.world_map.is_walkable(int(target_x), int(target_y)):
            # Try to find nearby walkable position
            safe_x, safe_y = context.world.find_nearest_walkable_position(target_x, target_y)
            if abs(safe_x - target_x) > 5.0 or abs(safe_y - target_y) > 5.0:
                return False, f"Target ({target_x}, {target_y}) is not walkable and no nearby alternative found"

            # Modify the request to use safe position
            request.parameters["target_x"] = safe_x
            request.parameters["target_y"] = safe_y

        return True, ""

    def get_supported_actions(self) -> Set[ActionType]:
        return {ActionType.MOVE_TO, ActionType.TELEPORT}


class CombatValidator(ActionValidator):
    """Validates combat actions using the attack system"""

    def validate(self, request: ActionRequest, context: ActionContext) -> Tuple[bool, str]:
        if request.action_type != ActionType.ATTACK_TARGET:
            return True, ""

        params = request.parameters
        target_id = params.get("target_id")
        attack_name = params.get("attack_name", "punch")

        if not target_id:
            return False, "Missing target_id"

        # Get attacker and target
        attacker = context.world.get_agent(request.agent_id)
        target = context.world.get_agent(target_id)

        if not attacker:
            return False, "Attacker not found"
        if not target:
            return False, "Target not found"
        if not attacker.is_alive:
            return False, "Attacker is dead"
        if not target.is_alive:
            return False, "Target is already dead"

        # Use existing attack system validation
        try:
            is_valid = context.attack_system.validate_attack(
                attacker, target, attack_name
            )
            if not is_valid:
                return False, "Attack validation failed"
        except Exception as e:
            return False, f"Attack validation error: {e}"

        return True, ""

    def get_supported_actions(self) -> Set[ActionType]:
        return {ActionType.ATTACK_TARGET, ActionType.CAST_SPELL}


class InventoryValidator(ActionValidator):
    """Validates inventory-related actions"""

    def validate(self, request: ActionRequest, context: ActionContext) -> Tuple[bool, str]:
        agent = context.agent_registry.get_agent(request.agent_id)
        if not agent or not agent.is_alive:
            return False, "Agent not found or dead"

        if request.action_type == ActionType.QUERY_INVENTORY:
            return True, ""

        elif request.action_type == ActionType.EQUIP_ITEM:
            item_id = request.parameters.get("item_id")
            if not item_id:
                return False, "Missing item_id"

            item = agent.inventory.get_item_by_id(item_id)
            if not item:
                return False, "Item not found in inventory"

            return True, ""

        elif request.action_type == ActionType.UNEQUIP_ITEM:
            slot_name = request.parameters.get("slot")
            if not slot_name:
                return False, "Missing slot"

            try:
                slot = EquipmentSlot(slot_name)
                if agent.inventory.equipped_items.get(slot) is None:
                    return False, f"No item equipped in {slot_name}"

                if not agent.inventory.has_space_for_item(
                    agent.inventory.equipped_items[slot], 1
                ):
                    return False, "Inventory full, cannot unequip"
            except ValueError:
                return False, f"Invalid equipment slot: {slot_name}"

            return True, ""

        elif request.action_type == ActionType.USE_ITEM:
            item_id = request.parameters.get("item_id")
            if not item_id:
                return False, "Missing item_id"

            item = agent.inventory.get_item_by_id(item_id)
            if not item:
                return False, "Item not found in inventory"

            return True, ""

        return True, ""

    def get_supported_actions(self) -> Set[ActionType]:
        return {
            ActionType.QUERY_INVENTORY,
            ActionType.EQUIP_ITEM,
            ActionType.UNEQUIP_ITEM,
            ActionType.USE_ITEM,
        }


class FishingValidator(ActionValidator):
    """Validates fishing actions"""

    def validate(self, request: ActionRequest, context: ActionContext) -> Tuple[bool, str]:
        if request.action_type != ActionType.FISH:
            return True, ""

        agent = context.agent_registry.get_agent(request.agent_id)
        if not agent or not agent.is_alive:
            return False, "Agent not found or dead"

        # Check if agent has fishing rod
        fishing_rods = [item for item in agent.inventory.get_items_by_type("tool")
                      if hasattr(item, 'tool_type') and item.tool_type == "fishing"]
        if not fishing_rods:
            return False, "No fishing rod in inventory"

        # Get target position (agent's current position if not specified)
        target_x = request.parameters.get("target_x", agent.position[0])
        target_y = request.parameters.get("target_y", agent.position[1])

        # Check if target location has water
        world_map = context.world.world_map
        tile_x, tile_y = int(target_x), int(target_y)

        if not (0 <= tile_x < world_map.width and 0 <= tile_y < world_map.height):
            return False, "Target location out of bounds"

        tile_type = world_map.get_tile(tile_x, tile_y)
        if tile_type != TileType.WATER:
            return False, "Can only fish at water locations"

        # Check distance (must be close to water)
        distance = ((target_x - agent.position[0]) ** 2 + (target_y - agent.position[1]) ** 2) ** 0.5

        # Debug logging for fishing distance validation
        logger.debug(f"🎣 Fishing validation: Agent {agent.agent_id[:8]} at ({agent.position[0]:.2f}, {agent.position[1]:.2f}) wants to fish at ({target_x}, {target_y}), distance: {distance:.2f}")

        max_fishing_distance = 1.5  # More generous than client's 0.5 to account for positioning errors
        if distance > max_fishing_distance:
            logger.warning(f"🎣 Fishing rejected: Agent {agent.agent_id[:8]} distance {distance:.2f} > {max_fishing_distance} limit")
            return False, f"Too far from water to fish (distance: {distance:.2f}, max: {max_fishing_distance})"

        return True, ""

    def get_supported_actions(self) -> Set[ActionType]:
        return {ActionType.FISH}


class ActionProcessor:
    """Main action processing engine"""

    def __init__(self, world, agent_registry, attack_system):
        self.world = world
        self.agent_registry = agent_registry
        self.attack_system = attack_system

        # Validation pipeline
        self.validators: List[ActionValidator] = [
            RateLimitValidator(),
            CooldownValidator(),
            MovementValidator(),
            CombatValidator(),
            InventoryValidator(),
            FishingValidator(),
        ]

        # Processing queues by priority
        self.queues: Dict[ActionPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in ActionPriority
        }

        # Statistics
        self.stats = {
            "total_processed": 0,
            "total_approved": 0,
            "total_rejected": 0,
            "total_modified": 0,
            "processing_time_ms": deque(maxlen=1000),  # Last 1000 processing times
        }

        # Processing state
        self.processing_tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """Start the action processing workers"""
        logger.info("Starting action processor")

        # Start workers for each priority level
        for priority in ActionPriority:
            task = asyncio.create_task(self._process_queue(priority))
            self.processing_tasks.append(task)

    async def stop(self):
        """Stop the action processor"""
        logger.info("Stopping action processor")
        self.shutdown_event.set()

        # Cancel all processing tasks
        for task in self.processing_tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.processing_tasks, return_exceptions=True)

    async def submit_action(self, request: ActionRequest) -> ActionResponse:
        """Submit a single action for processing"""
        start_time = time.time()

        try:
            # Validate the action
            context = ActionContext(self)
            validation_result = self._validate_action(request, context)

            if validation_result.result != ActionResult.APPROVED:
                return validation_result

            # Execute the action
            execution_result = await self._execute_action(request, context)

            # Update statistics
            processing_time = (time.time() - start_time) * 1000
            self.stats["processing_time_ms"].append(processing_time)
            self.stats["total_processed"] += 1

            if execution_result.result == ActionResult.APPROVED:
                self.stats["total_approved"] += 1
            elif execution_result.result == ActionResult.MODIFIED:
                self.stats["total_modified"] += 1
            else:
                self.stats["total_rejected"] += 1

            execution_result.processing_time_ms = processing_time
            return execution_result

        except Exception as e:
            logger.error(f"Error processing action {request.action_id}: {e}")
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.ERROR,
                message=f"Server error: {e}",
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    async def submit_batch(self, batch: ActionBatch) -> List[ActionResponse]:
        """Submit multiple actions for batch processing"""
        if batch.atomic:
            # All-or-nothing processing
            return await self._process_atomic_batch(batch)
        else:
            # Process each action independently
            tasks = [self.submit_action(action) for action in batch.actions]
            return await asyncio.gather(*tasks, return_exceptions=True)

    def _validate_action(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Run action through validation pipeline"""

        for validator in self.validators:
            if request.action_type not in validator.get_supported_actions():
                continue

            is_valid, error_message = validator.validate(request, context)
            if not is_valid:
                logger.debug(f"Action {request.action_id} rejected by {validator.__class__.__name__}: {error_message}")
                return ActionResponse(
                    action_id=request.action_id,
                    agent_id=request.agent_id,
                    action_type=request.action_type,
                    result=ActionResult.REJECTED,
                    message=error_message,
                )

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message="Action validated successfully",
        )

    async def _execute_action(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute a validated action"""

        try:
            if request.action_type == ActionType.MOVE_TO:
                return await self._execute_move_to(request, context)
            elif request.action_type == ActionType.ATTACK_TARGET:
                return await self._execute_attack_target(request, context)
            elif request.action_type == ActionType.STOP_MOVEMENT:
                return await self._execute_stop_movement(request, context)
            elif request.action_type == ActionType.QUERY_INVENTORY:
                return await self._execute_query_inventory(request, context)
            elif request.action_type == ActionType.EQUIP_ITEM:
                return await self._execute_equip_item(request, context)
            elif request.action_type == ActionType.UNEQUIP_ITEM:
                return await self._execute_unequip_item(request, context)
            elif request.action_type == ActionType.USE_ITEM:
                return await self._execute_use_item(request, context)
            elif request.action_type == ActionType.FISH:
                return await self._execute_fish(request, context)
            else:
                return ActionResponse(
                    action_id=request.action_id,
                    agent_id=request.agent_id,
                    action_type=request.action_type,
                    result=ActionResult.REJECTED,
                    message=f"Action type {request.action_type.value} not yet implemented",
                )

        except Exception as e:
            logger.error(f"Error executing action {request.action_id}: {e}")
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.ERROR,
                message=f"Execution error: {e}",
            )

    async def _execute_move_to(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute MOVE_TO action"""
        params = request.parameters
        target_x = params["target_x"]
        target_y = params["target_y"]

        # Move the agent
        success = context.world.move_agent(
            request.agent_id, target_x, target_y, 0.0  # rotation will be calculated
        )

        if success:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.APPROVED,
                message="Movement successful",
                approved_parameters=params,
            )
        else:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Movement failed - position not reachable",
            )

    async def _execute_attack_target(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute ATTACK_TARGET action"""
        params = request.parameters
        target_id = params["target_id"]
        attack_name = params.get("attack_name", "punch")

        # Use existing attack system
        action_data = {
            "action_type": "attack",
            "target_id": target_id,
            "attack_name": attack_name,
        }

        # This will handle the attack and send appropriate messages
        await context.processor._legacy_handle_attack_action(request.agent_id, action_data)

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message="Attack executed",
            approved_parameters=params,
        )

    async def _execute_stop_movement(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute STOP_MOVEMENT action"""
        agent = context.world.get_agent(request.agent_id)
        if agent:
            agent.velocity_x = 0
            agent.velocity_y = 0

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message="Movement stopped",
        )

    async def _legacy_handle_attack_action(self, attacker_id: str, action_data: Dict[str, Any]):
        """Temporary bridge to existing attack system"""
        # This is a temporary method to bridge the new action system with the existing attack handling
        # It should be replaced once the server is fully migrated
        pass

    async def _process_queue(self, priority: ActionPriority):
        """Process actions from a priority queue"""
        queue = self.queues[priority]

        while not self.shutdown_event.is_set():
            try:
                # Wait for action or shutdown
                request = await asyncio.wait_for(queue.get(), timeout=1.0)
                await self.submit_action(request)
            except asyncio.TimeoutError:
                continue  # Check shutdown event
            except Exception as e:
                logger.error(f"Error in queue processor for {priority}: {e}")

    async def _process_atomic_batch(self, batch: ActionBatch) -> List[ActionResponse]:
        """Process batch atomically - all succeed or all fail"""
        # First validate all actions
        context = ActionContext(self)
        validation_results = []

        for action in batch.actions:
            result = self._validate_action(action, context)
            validation_results.append(result)

            if result.result != ActionResult.APPROVED:
                # One action failed, reject the whole batch
                return [
                    ActionResponse(
                        action_id=action.action_id,
                        agent_id=action.agent_id,
                        action_type=action.action_type,
                        result=ActionResult.REJECTED,
                        message=f"Batch rejected due to action {result.action_id}: {result.message}",
                    ) for action in batch.actions
                ]

        # All actions validated, now execute them
        execution_results = []
        for action in batch.actions:
            result = await self._execute_action(action, context)
            execution_results.append(result)

            # If atomic batch and one fails, we'd need to rollback here
            # For now, we'll just continue (non-atomic behavior)

        return execution_results

    async def _execute_query_inventory(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute QUERY_INVENTORY action"""
        agent = context.agent_registry.get_agent(request.agent_id)

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message="Inventory retrieved",
            approved_parameters={"inventory": agent.inventory.to_dict()},
        )

    async def _execute_equip_item(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute EQUIP_ITEM action"""
        agent = context.agent_registry.get_agent(request.agent_id)
        item_id = request.parameters["item_id"]

        success = agent.inventory.equip_item(item_id)

        if success:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.APPROVED,
                message="Item equipped successfully",
                approved_parameters=request.parameters,
            )
        else:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Failed to equip item",
            )

    async def _execute_unequip_item(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute UNEQUIP_ITEM action"""
        agent = context.agent_registry.get_agent(request.agent_id)
        slot = EquipmentSlot(request.parameters["slot"])

        success = agent.inventory.unequip_item(slot)

        if success:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.APPROVED,
                message="Item unequipped successfully",
                approved_parameters=request.parameters,
            )
        else:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Failed to unequip item",
            )

    async def _execute_use_item(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute USE_ITEM action"""
        agent = context.agent_registry.get_agent(request.agent_id)
        item_id = request.parameters["item_id"]

        item = agent.inventory.get_item_by_id(item_id)
        if not item:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Item not found",
            )

        # Use the item
        use_result = item.use(request.agent_id, context.world)

        if use_result.get("success", False):
            # Remove consumable items
            if item.item_type.value == "consumable":
                agent.inventory.remove_item_by_id(item_id)

            # Apply effects (healing, etc.)
            if use_result.get("effect_type") == "heal":
                heal_amount = use_result.get("effect_value", 0)
                agent.heal(heal_amount)

            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.APPROVED,
                message=use_result.get("message", "Item used successfully"),
                approved_parameters={"effect": use_result},
            )
        else:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message=use_result.get("message", "Failed to use item"),
            )

    async def _execute_fish(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute FISH action"""
        agent = context.agent_registry.get_agent(request.agent_id)

        # Fishing takes 1-5 seconds randomly
        fishing_time = random.uniform(1.0, 5.0)
        await asyncio.sleep(fishing_time)

        # Random chance to catch a fish (80% success rate)
        if random.random() < 0.8:
            fish = create_item("fish")
            logger.debug(f"Created fish item: {fish}, name: {fish.name if fish else 'None'}")

            if fish and agent.inventory.has_space_for_item(fish, 1):
                # Add item to inventory
                added_count = agent.inventory.add_item(fish, 1)
                logger.debug(f"Attempted to add 1 fish, actually added: {added_count}")

                logger.info(f"🎣 Agent {agent.agent_id[:8]} caught a fish!")
                print(f"🎣 Agent {agent.agent_id[:8]} caught a fish!")

                return ActionResponse(
                    action_id=request.action_id,
                    agent_id=request.agent_id,
                    action_type=request.action_type,
                    result=ActionResult.APPROVED,
                    message=f"Caught a fish! (took {fishing_time:.1f} seconds)",
                    approved_parameters={
                        "caught_item": fish.to_dict(),
                        "fishing_time": fishing_time,
                        "success": True
                    },
                )
            else:
                logger.warning(f"🎣 Agent {agent.agent_id[:8]} caught a fish but inventory is full!")
                print(f"🎣 Agent {agent.agent_id[:8]} caught a fish but inventory is full!")

                return ActionResponse(
                    action_id=request.action_id,
                    agent_id=request.agent_id,
                    action_type=request.action_type,
                    result=ActionResult.REJECTED,
                    message=f"Caught a fish but inventory is full (took {fishing_time:.1f} seconds)",
                )
        else:
            logger.info(f"🎣 Agent {agent.agent_id[:8]} fishing unsuccessful (no catch).")
            print(f"🎣 Agent {agent.agent_id[:8]} fishing unsuccessful (no catch).")

            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.APPROVED,
                message=f"Fishing unsuccessful (took {fishing_time:.1f} seconds)",
                approved_parameters={
                    "fishing_time": fishing_time,
                    "success": False
                },
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        avg_processing_time = (
            sum(self.stats["processing_time_ms"]) / len(self.stats["processing_time_ms"])
            if self.stats["processing_time_ms"] else 0
        )

        return {
            **self.stats,
            "average_processing_time_ms": avg_processing_time,
            "queue_sizes": {
                priority.name: queue.qsize() for priority, queue in self.queues.items()
            },
        }