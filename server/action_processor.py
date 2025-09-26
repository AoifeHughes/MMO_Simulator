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
import uuid
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
from server.world_objects import get_recipe
from debug_tracker import track_agent_action, track_agent_position
from shared.position_sync import get_position_sync, validate_action_position, update_agent_position
from shared.action_constants import DISTANCES, THRESHOLDS, position_tracker
from shared.position_stats import record_position_discrepancy, record_action_distance_attempt

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
            ActionType.FISH: 1.0,  # Fishing attempt cooldown
            ActionType.HARVEST_WOOD: 2.0,  # Wood harvesting cooldown
            ActionType.CRAFT_ITEM: 5.0,  # Item crafting cooldown
            ActionType.TRADE_REQUEST: 1.0,  # Trade request cooldown
            ActionType.TRADE_ACCEPT: 0.5,  # Trade accept cooldown
            ActionType.TRADE_DECLINE: 0.5,  # Trade decline cooldown
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

        # Update position sync with current agent state
        update_agent_position(agent.agent_id, agent.position[0], agent.position[1])

        # Check if target location has water
        world_map = context.world.world_map
        tile_x, tile_y = int(target_x), int(target_y)

        if not (0 <= tile_x < world_map.width and 0 <= tile_y < world_map.height):
            return False, "Target location out of bounds"

        tile_type = world_map.get_tile(tile_x, tile_y)
        if tile_type != TileType.WATER:
            return False, "Can only fish at water locations"

        # MMO-style distance validation - server is authoritative, no position corrections
        max_fishing_distance = DISTANCES.FISHING_RANGE

        # Calculate actual distance between agent and target
        agent_pos = (agent.position[0], agent.position[1])
        target_pos = (target_x, target_y)
        dx = target_pos[0] - agent_pos[0]
        dy = target_pos[1] - agent_pos[1]
        actual_distance = (dx * dx + dy * dy) ** 0.5

        # DEBUG: Log server's view of agent position for fishing
        logger.debug(f"🔍 FISHING SERVER position for {agent.agent_id[:8]}: ({agent_pos[0]:.3f}, {agent_pos[1]:.3f})")
        logger.debug(f"🔍 FISHING SERVER calculating distance to target ({target_pos[0]:.3f}, {target_pos[1]:.3f}): {actual_distance:.3f}")

        # Simple binary validation - no position corrections
        is_valid = actual_distance <= max_fishing_distance

        # Record distance validation statistics
        record_action_distance_attempt("fishing", agent_pos, target_pos, max_fishing_distance, is_valid)

        if not is_valid:
            error_msg = f"Fishing failed: distance {actual_distance:.2f} > max {max_fishing_distance:.2f}. Move closer to the water."
            logger.info(f"🎣 Fishing rejected for {agent.agent_id[:8]}: {error_msg}")

            # Track client-server position discrepancy for debugging
            record_position_discrepancy(agent.agent_id, agent_pos, agent_pos, "fishing_validation")

            # Track the failed action for debugging
            track_agent_action(agent.agent_id, "fishing", target_pos, agent_pos, False, error_msg)
            return False, error_msg

        return True, ""

    def get_supported_actions(self) -> Set[ActionType]:
        return {ActionType.FISH}


class ActionProcessor:
    """Main action processing engine"""

    def __init__(self, world, agent_registry, attack_system):
        self.world = world
        self.agent_registry = agent_registry
        self.attack_system = attack_system

        # Trade session management
        self.active_trades: Dict[str, Dict[str, Any]] = {}  # trade_id -> trade_data
        self.agent_trades: Dict[str, str] = {}  # agent_id -> trade_id

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
            elif request.action_type == ActionType.HARVEST_WOOD:
                return await self._execute_harvest_wood(request, context)
            elif request.action_type == ActionType.CRAFT_ITEM:
                return await self._execute_craft_item(request, context)
            elif request.action_type == ActionType.TRADE_REQUEST:
                return await self._execute_trade_request(request, context)
            elif request.action_type == ActionType.TRADE_ACCEPT:
                return await self._execute_trade_accept(request, context)
            elif request.action_type == ActionType.TRADE_DECLINE:
                return await self._execute_trade_decline(request, context)
            elif request.action_type == ActionType.EXPLORATION_REPORT:
                return await self._execute_exploration_report(request, context)
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

        # No position corrections - server doesn't move agents during actions
        # In MMO-style architecture, clients must be positioned correctly before requesting actions

        # Fishing takes 1-5 seconds randomly
        fishing_time = random.uniform(1.0, 5.0)
        await asyncio.sleep(fishing_time)

        # Random chance to catch a fish (80% success rate)
        if random.random() < 0.8:
            fish = create_item("fish")
            logger.debug(f"Created fish item: {fish}, name: {fish.name if fish else 'None'}")

            if fish and agent.inventory.has_space_for_item(fish, 1):
                # Add item to inventory - with better error handling
                added_count = agent.inventory.add_item(fish, 1)
                logger.debug(f"Attempted to add 1 fish, actually added: {added_count}")

                # If add_item failed, try manual slot assignment
                if added_count == 0:
                    for slot in agent.inventory.slots:
                        if slot.is_empty():
                            slot.set_item(fish, 1)
                            added_count = 1
                            logger.info(f"🎣 Manually added fish to empty slot for agent {agent.agent_id[:8]}")
                            break

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

    async def _execute_harvest_wood(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute HARVEST_WOOD action"""
        agent = context.agent_registry.get_agent(request.agent_id)
        target_x = request.parameters.get("target_x", agent.position[0])
        target_y = request.parameters.get("target_y", agent.position[1])

        # Update position sync with current agent state
        update_agent_position(agent.agent_id, agent.position[0], agent.position[1])

        # MMO-style distance validation - server is authoritative, no position corrections
        max_harvest_distance = DISTANCES.WOOD_HARVESTING_RANGE

        # Calculate actual distance between agent and target
        agent_pos = (agent.position[0], agent.position[1])
        target_pos = (target_x, target_y)
        dx = target_pos[0] - agent_pos[0]
        dy = target_pos[1] - agent_pos[1]
        actual_distance = (dx * dx + dy * dy) ** 0.5

        # Simple binary validation - no position corrections
        is_valid = actual_distance <= max_harvest_distance

        # Record distance validation statistics
        record_action_distance_attempt("wood_harvesting", agent_pos, target_pos, max_harvest_distance, is_valid)

        if not is_valid:
            error_msg = f"Wood harvesting failed: distance {actual_distance:.2f} > max {max_harvest_distance:.2f}. Move closer to the trees."
            logger.info(f"🌲 Wood harvesting rejected for {agent.agent_id[:8]}: {error_msg}")

            # Track client-server position discrepancy for debugging
            record_position_discrepancy(agent.agent_id, agent_pos, agent_pos, "wood_harvesting_validation")

            # Track the failed action for debugging
            track_agent_action(agent.agent_id, "harvest_wood", target_pos, agent_pos, False, error_msg)
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message=error_msg
            )

        # Check if target tile is forest
        tile_x, tile_y = int(target_x), int(target_y)
        tile_type = context.world.world_map.get_tile(tile_x, tile_y)
        if tile_type != TileType.WOOD:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Can only harvest wood from forest tiles"
            )

        # No position corrections - server doesn't move agents during actions
        # In MMO-style architecture, clients must be positioned correctly before requesting actions

        # Harvesting takes 2-4 seconds
        harvest_time = random.uniform(2.0, 4.0)
        await asyncio.sleep(harvest_time)

        # Create wood item and try to add to inventory
        wood_item = create_item("wood")
        if wood_item and agent.inventory.has_space_for_item(wood_item, 1):
            added_count = agent.inventory.add_item(wood_item, 1)

            # If add_item failed, try manual slot assignment
            if added_count == 0:
                for slot in agent.inventory.slots:
                    if slot.is_empty():
                        slot.set_item(wood_item, 1)
                        added_count = 1
                        logger.info(f"🌲 Manually added wood to empty slot for agent {agent.agent_id[:8]}")
                        break

        if wood_item and added_count > 0:
            logger.info(f"🌲 Agent {agent.agent_id[:8]} harvested wood at ({tile_x}, {tile_y})")

            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.APPROVED,
                message=f"Successfully harvested wood (took {harvest_time:.1f} seconds)",
                approved_parameters={
                    "harvested_item": wood_item.to_dict(),
                    "harvest_time": harvest_time,
                    "location": (tile_x, tile_y)
                }
            )
        else:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Could not harvest wood - inventory may be full"
            )

    async def _execute_craft_item(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute CRAFT_ITEM action"""
        agent = context.agent_registry.get_agent(request.agent_id)
        recipe_name = request.parameters.get("recipe_name")
        target_x = request.parameters.get("target_x", agent.position[0])
        target_y = request.parameters.get("target_y", agent.position[1])

        # Get recipe
        recipe = get_recipe(recipe_name)
        if not recipe:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message=f"Unknown recipe: {recipe_name}"
            )

        # Check if agent is close to target location
        agent_x, agent_y = agent.position
        distance = ((target_x - agent_x) ** 2 + (target_y - agent_y) ** 2) ** 0.5
        if distance > 2.0:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Too far from crafting location"
            )

        # Check if target tile is suitable (not water)
        tile_x, tile_y = int(target_x), int(target_y)
        tile_type = context.world.world_map.get_tile(tile_x, tile_y)
        if tile_type == TileType.WATER:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Cannot craft on water tiles"
            )

        # Check if agent has required items
        inventory_items = {}
        for slot in agent.inventory.slots:
            if not slot.is_empty():
                item_name = slot.item.name
                inventory_items[item_name] = inventory_items.get(item_name, 0) + slot.quantity

        if not recipe.can_craft(inventory_items):
            missing_items = []
            for item_name, required_qty in recipe.required_items.items():
                current_qty = inventory_items.get(item_name, 0)
                if current_qty < required_qty:
                    missing_items.append(f"{item_name} (need {required_qty}, have {current_qty})")

            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message=f"Missing required items: {', '.join(missing_items)}"
            )

        # Crafting takes time
        await asyncio.sleep(recipe.craft_time)

        # Consume ingredients from inventory
        for item_name, required_qty in recipe.required_items.items():
            agent.inventory.remove_item(item_name, required_qty)

        # Create world object
        if recipe.recipe_name == "basic_fire":
            created_object = context.world.world_objects.create_fire(
                target_x, target_y, agent.agent_id, recipe.result_duration
            )
        elif recipe.recipe_name == "campfire":
            created_object = context.world.world_objects.create_campfire(
                target_x, target_y, agent.agent_id
            )
        else:
            created_object = context.world.world_objects.create_fire(
                target_x, target_y, agent.agent_id, recipe.result_duration
            )

        # Record craft in database if available
        if hasattr(context.world, 'server') and hasattr(context.world.server, 'database_manager'):
            ingredients_list = [{"item_name": name, "quantity": qty} for name, qty in recipe.required_items.items()]
            await context.world.server.database_manager.record_craft(
                agent.agent_id, recipe_name, ingredients_list,
                created_object.object_type.value, (target_x, target_y),
                recipe.result_duration, True
            )

        logger.info(f"🔥 Agent {agent.agent_id[:8]} crafted {recipe_name} at ({target_x:.1f}, {target_y:.1f})")

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message=f"Successfully crafted {recipe_name}",
            approved_parameters={
                "recipe_name": recipe_name,
                "created_object": created_object.to_dict(),
                "craft_time": recipe.craft_time,
                "location": (target_x, target_y)
            }
        )

    async def _execute_trade_request(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute TRADE_REQUEST action - initiate a trade with another agent"""
        agent = context.agent_registry.get_agent(request.agent_id)
        target_agent_id = request.parameters.get("target_agent_id")
        offered_items = request.parameters.get("offered_items", [])
        requested_items = request.parameters.get("requested_items", [])

        # Check if target agent exists
        target_agent = context.agent_registry.get_agent(target_agent_id)
        if not target_agent:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Target agent not found"
            )

        # Check if agents are within trading distance
        agent_x, agent_y = agent.position
        target_x, target_y = target_agent.position
        distance = ((target_x - agent_x) ** 2 + (target_y - agent_y) ** 2) ** 0.5
        if distance > 5.0:  # 5 unit trading range
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Target agent too far for trading"
            )

        # Check if either agent is already in a trade
        if request.agent_id in self.agent_trades or target_agent_id in self.agent_trades:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="One of the agents is already in a trade"
            )

        # Validate offered items exist in agent's inventory
        for offered_item in offered_items:
            item_id = offered_item.get("item_id")
            quantity = offered_item.get("quantity", 1)

            # Find item in inventory
            found_item = agent.inventory.get_item_by_id(item_id)
            if not found_item:
                return ActionResponse(
                    action_id=request.action_id,
                    agent_id=request.agent_id,
                    action_type=request.action_type,
                    result=ActionResult.REJECTED,
                    message=f"Offered item {item_id} not found in inventory"
                )

        # Create trade session
        trade_id = str(uuid.uuid4())[:8]
        trade_data = {
            "trade_id": trade_id,
            "initiator": request.agent_id,
            "target": target_agent_id,
            "offered_items": offered_items,
            "requested_items": requested_items,
            "status": "pending",
            "created_time": time.time(),
            "location": ((agent_x + target_x) / 2, (agent_y + target_y) / 2)
        }

        self.active_trades[trade_id] = trade_data
        self.agent_trades[request.agent_id] = trade_id
        self.agent_trades[target_agent_id] = trade_id

        logger.info(f"💱 Trade {trade_id} initiated between {request.agent_id[:8]} and {target_agent_id[:8]}")

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message=f"Trade request sent to {target_agent_id}",
            approved_parameters={
                "trade_id": trade_id,
                "target_agent_id": target_agent_id,
                "offered_items": offered_items,
                "requested_items": requested_items
            }
        )

    async def _execute_trade_accept(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute TRADE_ACCEPT action - accept a pending trade"""
        agent = context.agent_registry.get_agent(request.agent_id)
        trade_id = request.parameters.get("trade_id")

        # Check if trade exists
        if trade_id not in self.active_trades:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Trade not found"
            )

        trade_data = self.active_trades[trade_id]

        # Check if agent is the target of this trade
        if request.agent_id != trade_data["target"]:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="You are not the target of this trade"
            )

        # Check if trade is still pending
        if trade_data["status"] != "pending":
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message=f"Trade is no longer pending (status: {trade_data['status']})"
            )

        # Get both agents
        initiator_agent = context.agent_registry.get_agent(trade_data["initiator"])
        target_agent = context.agent_registry.get_agent(trade_data["target"])

        if not initiator_agent or not target_agent:
            self._cleanup_trade(trade_id)
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="One of the trading agents is no longer available"
            )

        # Execute the trade - transfer items
        offered_items = trade_data["offered_items"]
        requested_items = trade_data["requested_items"]

        # Remove offered items from initiator
        for offered_item in offered_items:
            item_id = offered_item["item_id"]
            quantity = offered_item["quantity"]
            removed_item = initiator_agent.inventory.remove_item_by_id(item_id)
            if removed_item:
                # Add to target's inventory
                target_agent.inventory.add_item(removed_item, quantity)

        # For requested items, we need to find them in target's inventory by name
        for requested_item in requested_items:
            item_name = requested_item["item_name"]
            quantity = requested_item["quantity"]
            removed_qty = target_agent.inventory.remove_item(item_name, quantity)
            if removed_qty > 0:
                # Create the item and add to initiator's inventory
                new_item = create_item(item_name.lower().replace(" ", "_"))
                if new_item:
                    initiator_agent.inventory.add_item(new_item, removed_qty)

        # Record trade in database if available
        if hasattr(context.world, 'server') and hasattr(context.world.server, 'database_manager'):
            initiator_items = [{"item_name": context.agent_registry.get_agent(trade_data["initiator"]).inventory.get_item_by_id(item["item_id"]).name, "quantity": item["quantity"]} for item in offered_items]
            target_items = [{"item_name": item["item_name"], "quantity": item["quantity"]} for item in requested_items]

            await context.world.server.database_manager.record_trade(
                trade_data["initiator"], trade_data["target"],
                initiator_items, target_items, trade_data["location"]
            )

        # Mark trade as completed and cleanup
        trade_data["status"] = "completed"
        self._cleanup_trade(trade_id)

        logger.info(f"💱 Trade {trade_id} completed between {trade_data['initiator'][:8]} and {trade_data['target'][:8]}")

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message="Trade completed successfully",
            approved_parameters={
                "trade_id": trade_id,
                "completed": True
            }
        )

    async def _execute_trade_decline(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Execute TRADE_DECLINE action - decline a pending trade"""
        agent = context.agent_registry.get_agent(request.agent_id)
        trade_id = request.parameters.get("trade_id")

        # Check if trade exists
        if trade_id not in self.active_trades:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="Trade not found"
            )

        trade_data = self.active_trades[trade_id]

        # Check if agent is involved in this trade
        if request.agent_id not in [trade_data["initiator"], trade_data["target"]]:
            return ActionResponse(
                action_id=request.action_id,
                agent_id=request.agent_id,
                action_type=request.action_type,
                result=ActionResult.REJECTED,
                message="You are not involved in this trade"
            )

        # Mark trade as declined and cleanup
        trade_data["status"] = "declined"
        self._cleanup_trade(trade_id)

        logger.info(f"💱 Trade {trade_id} declined by {request.agent_id[:8]}")

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message="Trade declined",
            approved_parameters={
                "trade_id": trade_id,
                "declined": True
            }
        )

    async def _execute_exploration_report(self, request: ActionRequest, context: ActionContext) -> ActionResponse:
        """Handle agent exploration reports"""
        parameters = request.parameters or {}

        # Extract report data
        explored_tiles = parameters.get("explored_tiles", 0)
        total_tiles = parameters.get("total_tiles", 1)
        exploration_percent = parameters.get("exploration_percent", 0.0)

        # Update agent exploration stats if we have the agent registry
        agent_state = self.server.agent_registry.get_agent(request.agent_id)
        if agent_state:
            agent_state.stats["exploration_percent"] = exploration_percent
            agent_state.stats["explored_tiles_count"] = explored_tiles

        return ActionResponse(
            action_id=request.action_id,
            agent_id=request.agent_id,
            action_type=request.action_type,
            result=ActionResult.APPROVED,
            message=f"Exploration report received: {exploration_percent:.1f}% complete",
            approved_parameters={
                "explored_tiles": explored_tiles,
                "total_tiles": total_tiles,
                "exploration_percent": exploration_percent
            }
        )

    def _cleanup_trade(self, trade_id: str):
        """Clean up a completed or cancelled trade"""
        if trade_id in self.active_trades:
            trade_data = self.active_trades[trade_id]

            # Remove agent trade assignments
            if trade_data["initiator"] in self.agent_trades:
                del self.agent_trades[trade_data["initiator"]]
            if trade_data["target"] in self.agent_trades:
                del self.agent_trades[trade_data["target"]]

            # Remove trade
            del self.active_trades[trade_id]

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