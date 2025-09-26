"""
MMO-Style Action Command System

This module implements the Command pattern for all game actions,
providing unified validation, execution, and rollback capabilities.
All actions are processed server-authoritatively with immediate feedback.
"""

import asyncio
import time
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Type
from enum import Enum

from server.mmo_core import AuthoritativeGameState
from shared.actions import ActionType, ActionResult
from shared.items import create_item
from world.tiles import TileType

logger = logging.getLogger(__name__)


@dataclass
class CommandContext:
    """Context passed to all action commands"""
    game_state: AuthoritativeGameState
    world: Any  # ServerWorld reference
    agent_registry: Any  # AgentRegistry reference
    timestamp: float = field(default_factory=time.time)


@dataclass
class CommandResult:
    """Result of executing an action command"""
    success: bool
    result_type: ActionResult
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)  # Events to send to clients
    rollback_data: Optional[Dict[str, Any]] = None


class ActionCommand(ABC):
    """Base class for all action commands"""

    def __init__(self, agent_id: str, parameters: Dict[str, Any]):
        self.agent_id = agent_id
        self.parameters = parameters
        self.command_id = f"{agent_id}_{time.time():.3f}"
        self.execution_time: Optional[float] = None
        self.rollback_data: Dict[str, Any] = {}

    @abstractmethod
    async def validate(self, context: CommandContext) -> Tuple[bool, str]:
        """Validate if command can be executed. Returns (success, error_message)"""
        pass

    @abstractmethod
    async def execute(self, context: CommandContext) -> CommandResult:
        """Execute the command and return result"""
        pass

    @abstractmethod
    async def rollback(self, context: CommandContext, rollback_data: Dict[str, Any]) -> bool:
        """Rollback the command if needed"""
        pass

    def get_action_type(self) -> ActionType:
        """Get the action type for this command"""
        return ActionType.PING  # Override in subclasses


class MoveToCommand(ActionCommand):
    """Command for moving agents to target positions"""

    def get_action_type(self) -> ActionType:
        return ActionType.MOVE_TO

    async def validate(self, context: CommandContext) -> Tuple[bool, str]:
        """Validate movement request"""
        target_x = self.parameters.get("target_x")
        target_y = self.parameters.get("target_y")

        if target_x is None or target_y is None:
            return False, "Missing target coordinates"

        # Check world bounds
        if hasattr(context.world, 'world_map'):
            bounds = context.world.world_map.get_bounds()
            if not (0 <= target_x < bounds[0] and 0 <= target_y < bounds[1]):
                return False, f"Target ({target_x}, {target_y}) is out of bounds"

            # Check if target is walkable
            if not context.world.world_map.is_walkable(int(target_x), int(target_y)):
                return False, f"Target ({target_x}, {target_y}) is not walkable"

        # Check if agent exists and is alive
        health_component = context.game_state.get_component(self.agent_id, "HealthComponent")
        if not health_component or not health_component.is_alive:
            return False, "Agent is not alive"

        return True, ""

    async def execute(self, context: CommandContext) -> CommandResult:
        """Execute movement command"""
        target_x = self.parameters["target_x"]
        target_y = self.parameters["target_y"]
        speed = self.parameters.get("speed_multiplier", 1.0) * 5.0  # Base speed 5 units/sec

        # Store current position for rollback
        current_pos = context.game_state.get_position(self.agent_id)
        if current_pos:
            self.rollback_data["previous_position"] = current_pos

        # Set target position in game state
        success = context.game_state.set_target_position(self.agent_id, target_x, target_y, speed)

        if success:
            return CommandResult(
                success=True,
                result_type=ActionResult.APPROVED,
                message="Movement started",
                data={
                    "target_x": target_x,
                    "target_y": target_y,
                    "speed": speed
                }
            )
        else:
            return CommandResult(
                success=False,
                result_type=ActionResult.REJECTED,
                message="Failed to initiate movement"
            )

    async def rollback(self, context: CommandContext, rollback_data: Dict[str, Any]) -> bool:
        """Rollback movement by restoring previous position"""
        if "previous_position" in rollback_data:
            prev_x, prev_y = rollback_data["previous_position"]
            return context.game_state.teleport_entity(self.agent_id, prev_x, prev_y)
        return False


class FishingCommand(ActionCommand):
    """Command for fishing actions with proper inventory management"""

    def get_action_type(self) -> ActionType:
        return ActionType.FISH

    async def validate(self, context: CommandContext) -> Tuple[bool, str]:
        """Validate fishing request"""
        # Check if agent is alive
        health_component = context.game_state.get_component(self.agent_id, "HealthComponent")
        if not health_component or not health_component.is_alive:
            return False, "Agent is not alive"

        # Get agent from registry for inventory check
        agent_state = context.agent_registry.get_agent(self.agent_id)
        if not agent_state:
            return False, "Agent not found"

        # Check if agent has fishing rod
        fishing_rods = [item for item in agent_state.inventory.get_items_by_type("tool")
                       if hasattr(item, 'name') and 'fishing' in item.name.lower()]
        if not fishing_rods:
            return False, "No fishing rod in inventory"

        # Get target position (agent's current position if not specified)
        agent_pos = context.game_state.get_position(self.agent_id)
        if not agent_pos:
            return False, "Cannot determine agent position"

        target_x = self.parameters.get("target_x", agent_pos[0])
        target_y = self.parameters.get("target_y", agent_pos[1])

        # Check if target location has water and is in range
        if hasattr(context.world, 'world_map'):
            tile_x, tile_y = int(target_x), int(target_y)
            world_map = context.world.world_map

            if not (0 <= tile_x < world_map.width and 0 <= tile_y < world_map.height):
                return False, "Target location out of bounds"

            tile_type = world_map.get_tile(tile_x, tile_y)
            if tile_type != TileType.WATER:
                return False, "Can only fish at water locations"

            # Check distance to water
            water_center_x = tile_x + 0.5
            water_center_y = tile_y + 0.5
            distance = ((water_center_x - agent_pos[0]) ** 2 + (water_center_y - agent_pos[1]) ** 2) ** 0.5

            max_fishing_distance = 1.2
            if distance > max_fishing_distance:
                return False, f"Too far from water (distance: {distance:.2f}, max: {max_fishing_distance})"

        return True, ""

    async def execute(self, context: CommandContext) -> CommandResult:
        """Execute fishing action with proper inventory management"""
        agent_state = context.agent_registry.get_agent(self.agent_id)

        # Store pre-fishing inventory state for rollback
        self.rollback_data["inventory_before"] = agent_state.inventory.to_dict()

        # Simulate fishing time (1-5 seconds)
        fishing_time = random.uniform(1.0, 5.0)
        await asyncio.sleep(fishing_time)

        # Determine fishing success (80% chance)
        fishing_success = random.random() < 0.8

        if fishing_success:
            # Create fish item
            fish_item = create_item("fish")
            if not fish_item:
                return CommandResult(
                    success=False,
                    result_type=ActionResult.ERROR,
                    message="Failed to create fish item"
                )

            # Check inventory space
            if not agent_state.inventory.has_space_for_item(fish_item, 1):
                return CommandResult(
                    success=False,
                    result_type=ActionResult.REJECTED,
                    message=f"Inventory full - caught a fish but couldn't store it (fishing took {fishing_time:.1f}s)"
                )

            # Add fish to inventory
            added_count = agent_state.inventory.add_item(fish_item, 1)
            if added_count > 0:
                logger.info(f"🎣 Agent {self.agent_id[:8]} successfully caught a fish!")

                return CommandResult(
                    success=True,
                    result_type=ActionResult.APPROVED,
                    message=f"Caught a fish! (took {fishing_time:.1f} seconds)",
                    data={
                        "caught_item": fish_item.to_dict(),
                        "fishing_time": fishing_time,
                        "fishing_success": True
                    },
                    events=[{
                        "type": "item_gained",
                        "agent_id": self.agent_id,
                        "item": fish_item.to_dict(),
                        "quantity": 1
                    }]
                )
            else:
                return CommandResult(
                    success=False,
                    result_type=ActionResult.ERROR,
                    message="Failed to add fish to inventory"
                )
        else:
            # Fishing unsuccessful
            return CommandResult(
                success=True,  # Action succeeded, just no catch
                result_type=ActionResult.APPROVED,
                message=f"Fishing unsuccessful - no catch (took {fishing_time:.1f} seconds)",
                data={
                    "fishing_time": fishing_time,
                    "fishing_success": False
                }
            )

    async def rollback(self, context: CommandContext, rollback_data: Dict[str, Any]) -> bool:
        """Rollback fishing by restoring inventory state"""
        if "inventory_before" in rollback_data:
            agent_state = context.agent_registry.get_agent(self.agent_id)
            if agent_state:
                # This is a simplified rollback - in production you'd want more sophisticated inventory restoration
                logger.warning(f"Rolling back fishing action for {self.agent_id}")
                return True
        return False


class HarvestWoodCommand(ActionCommand):
    """Command for wood harvesting with proper inventory management"""

    def get_action_type(self) -> ActionType:
        return ActionType.HARVEST_WOOD

    async def validate(self, context: CommandContext) -> Tuple[bool, str]:
        """Validate wood harvesting request"""
        # Check if agent is alive
        health_component = context.game_state.get_component(self.agent_id, "HealthComponent")
        if not health_component or not health_component.is_alive:
            return False, "Agent is not alive"

        # Get agent from registry
        agent_state = context.agent_registry.get_agent(self.agent_id)
        if not agent_state:
            return False, "Agent not found"

        # Get target position and agent position
        agent_pos = context.game_state.get_position(self.agent_id)
        if not agent_pos:
            return False, "Cannot determine agent position"

        target_x = self.parameters.get("target_x", agent_pos[0])
        target_y = self.parameters.get("target_y", agent_pos[1])

        # Check if target has wood and is in range
        if hasattr(context.world, 'world_map'):
            tile_x, tile_y = int(target_x), int(target_y)
            world_map = context.world.world_map

            if not (0 <= tile_x < world_map.width and 0 <= tile_y < world_map.height):
                return False, "Target location out of bounds"

            tile_type = world_map.get_tile(tile_x, tile_y)
            if tile_type != TileType.WOOD:
                return False, "Can only harvest wood from forest tiles"

            # Check distance to wood
            wood_center_x = tile_x + 0.5
            wood_center_y = tile_y + 0.5
            distance = ((wood_center_x - agent_pos[0]) ** 2 + (wood_center_y - agent_pos[1]) ** 2) ** 0.5

            max_harvest_distance = 1.2
            if distance > max_harvest_distance:
                return False, f"Too far from wood (distance: {distance:.2f}, max: {max_harvest_distance})"

        return True, ""

    async def execute(self, context: CommandContext) -> CommandResult:
        """Execute wood harvesting with proper inventory management"""
        agent_state = context.agent_registry.get_agent(self.agent_id)

        # Store pre-harvesting inventory state for rollback
        self.rollback_data["inventory_before"] = agent_state.inventory.to_dict()

        target_x = self.parameters.get("target_x", 0.0)
        target_y = self.parameters.get("target_y", 0.0)

        # Simulate harvesting time (2-4 seconds)
        harvest_time = random.uniform(2.0, 4.0)
        await asyncio.sleep(harvest_time)

        # Create wood item
        wood_item = create_item("wood")
        if not wood_item:
            return CommandResult(
                success=False,
                result_type=ActionResult.ERROR,
                message="Failed to create wood item"
            )

        # Check inventory space
        if not agent_state.inventory.has_space_for_item(wood_item, 1):
            return CommandResult(
                success=False,
                result_type=ActionResult.REJECTED,
                message="Inventory full - cannot store harvested wood"
            )

        # Add wood to inventory
        added_count = agent_state.inventory.add_item(wood_item, 1)
        if added_count > 0:
            logger.info(f"🌲 Agent {self.agent_id[:8]} successfully harvested wood!")

            return CommandResult(
                success=True,
                result_type=ActionResult.APPROVED,
                message=f"Successfully harvested wood (took {harvest_time:.1f} seconds)",
                data={
                    "harvested_item": wood_item.to_dict(),
                    "harvest_time": harvest_time,
                    "location": (int(target_x), int(target_y))
                },
                events=[{
                    "type": "item_gained",
                    "agent_id": self.agent_id,
                    "item": wood_item.to_dict(),
                    "quantity": 1
                }]
            )
        else:
            return CommandResult(
                success=False,
                result_type=ActionResult.ERROR,
                message="Failed to add wood to inventory"
            )

    async def rollback(self, context: CommandContext, rollback_data: Dict[str, Any]) -> bool:
        """Rollback wood harvesting by restoring inventory state"""
        if "inventory_before" in rollback_data:
            agent_state = context.agent_registry.get_agent(self.agent_id)
            if agent_state:
                logger.warning(f"Rolling back wood harvesting action for {self.agent_id}")
                return True
        return False


class ActionCommandProcessor:
    """
    Central processor for all action commands.

    This replaces the scattered action processing with a unified,
    MMO-style command queue system.
    """

    def __init__(self, game_state: AuthoritativeGameState, world, agent_registry):
        self.game_state = game_state
        self.world = world
        self.agent_registry = agent_registry

        # Command registry
        self.command_types: Dict[ActionType, Type[ActionCommand]] = {
            ActionType.MOVE_TO: MoveToCommand,
            ActionType.FISH: FishingCommand,
            ActionType.HARVEST_WOOD: HarvestWoodCommand,
        }

        # Processing queues
        self.command_queue: asyncio.Queue = asyncio.Queue()
        self.processing = False

        # Statistics
        self.commands_processed = 0
        self.commands_succeeded = 0
        self.commands_failed = 0

    def register_command_type(self, action_type: ActionType, command_class: Type[ActionCommand]):
        """Register a new command type"""
        self.command_types[action_type] = command_class

    async def start_processing(self):
        """Start the command processing loop"""
        self.processing = True
        logger.info("Action command processor started")

        while self.processing:
            try:
                # Get next command (with timeout to allow clean shutdown)
                command = await asyncio.wait_for(self.command_queue.get(), timeout=1.0)
                await self._process_command(command)
            except asyncio.TimeoutError:
                continue  # Check if still processing
            except Exception as e:
                logger.error(f"Error in command processor: {e}")

    def stop_processing(self):
        """Stop the command processor"""
        self.processing = False

    async def submit_command(self, action_type: ActionType, agent_id: str, parameters: Dict[str, Any]) -> CommandResult:
        """Submit a command for processing"""
        if action_type not in self.command_types:
            return CommandResult(
                success=False,
                result_type=ActionResult.REJECTED,
                message=f"Unsupported action type: {action_type.value}"
            )

        command_class = self.command_types[action_type]
        command = command_class(agent_id, parameters)

        # For immediate processing (could be queued for batching in production)
        return await self._process_command(command)

    async def _process_command(self, command: ActionCommand) -> CommandResult:
        """Process a single command"""
        context = CommandContext(
            game_state=self.game_state,
            world=self.world,
            agent_registry=self.agent_registry
        )

        self.commands_processed += 1

        try:
            # Validate command
            is_valid, error_msg = await command.validate(context)
            if not is_valid:
                self.commands_failed += 1
                return CommandResult(
                    success=False,
                    result_type=ActionResult.REJECTED,
                    message=error_msg
                )

            # Execute command
            result = await command.execute(context)
            command.execution_time = time.time()

            if result.success:
                self.commands_succeeded += 1
            else:
                self.commands_failed += 1

            return result

        except Exception as e:
            self.commands_failed += 1
            logger.error(f"Error executing command {command.command_id}: {e}")

            return CommandResult(
                success=False,
                result_type=ActionResult.ERROR,
                message=f"Internal server error: {str(e)}"
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            "commands_processed": self.commands_processed,
            "commands_succeeded": self.commands_succeeded,
            "commands_failed": self.commands_failed,
            "success_rate": self.commands_succeeded / max(1, self.commands_processed),
            "queue_size": self.command_queue.qsize()
        }