#!/usr/bin/env python3
"""
Test script for the new unified action system

This script creates a simple scenario to test:
1. Action manager initialization
2. Basic action request-response flow
3. RequestAction behavior tree nodes
4. Server action processing and validation

Run this instead of the full simulation to test just the action system.
"""

import asyncio
import logging
import time

import pytest

from client.action_manager import ActionManager
from client.behavior_tree.nodes.request_action import RequestMoveTo
from shared.actions import ActionRequest, ActionType, move_to_params
from shared.messages import Message, MessageType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockAgent:
    """Mock agent for testing action system"""

    def __init__(self, agent_id: str):
        self.id = agent_id
        self.x = 50.0
        self.y = 50.0
        self.action_manager = None

    def get_nearest_entity_of_type(self, entity_types):
        # Mock: return a fake target for testing
        return {"id": "test_target", "x": 60.0, "y": 60.0}


class MockClient:
    """Mock client for testing"""

    def __init__(self):
        self.sent_messages = []

    async def send_tcp_message(self, message: Message):
        """Mock message sending - just log what we would send"""
        logger.info(f"[MOCK CLIENT] Would send message: {message.type.value}")
        logger.debug(f"[MOCK CLIENT] Message payload: {message.payload}")
        self.sent_messages.append(message)

        # Mock immediate success response for testing
        if message.type == MessageType.ACTION_REQUEST:
            from shared.actions import ActionResponse, ActionResult

            # Create a mock successful response
            request_data = message.payload
            response = ActionResponse(
                action_id=request_data.get("action_id", "test"),
                agent_id=request_data.get("agent_id", "test_agent"),
                action_type=ActionType(request_data.get("action_type", "move_to")),
                result=ActionResult.APPROVED,
                message="Mock action approved",
                approved_parameters=request_data.get("parameters", {}),
            )

            # Simulate async response processing
            await asyncio.sleep(0.1)
            await self.mock_agent.action_manager.handle_response(response)

    def set_mock_agent(self, agent):
        self.mock_agent = agent


@pytest.mark.asyncio
async def test_action_manager():
    """Test basic action manager functionality"""
    logger.info("=== Testing Action Manager ===")

    # Create mock components
    mock_client = MockClient()
    mock_agent = MockAgent("test_agent_001")
    mock_client.set_mock_agent(mock_agent)

    # Initialize action manager
    action_manager = ActionManager(
        agent_id=mock_agent.id,
        send_message_callback=mock_client.send_tcp_message,
    )
    mock_agent.action_manager = action_manager

    # Test basic action request
    logger.info("Testing basic MOVE_TO action request...")
    action_id = await action_manager.request_action(
        action_type=ActionType.MOVE_TO,
        parameters=move_to_params(75.0, 75.0, 1.0),
        predict=True,
    )

    logger.info(f"Action request sent with ID: {action_id}")

    # Wait a bit for the mock response
    await asyncio.sleep(0.2)

    # Check stats
    stats = action_manager.get_stats()
    logger.info(f"Action manager stats: {stats}")

    assert (
        stats["requests_sent"] == 1
    ), f"Expected 1 request sent, got {stats['requests_sent']}"
    assert (
        stats["responses_received"] == 1
    ), f"Expected 1 response received, got {stats['responses_received']}"

    logger.info("✅ Action manager test passed!")


@pytest.mark.asyncio
async def test_request_action_node():
    """Test RequestAction behavior tree node"""
    logger.info("=== Testing RequestAction Behavior Tree Node ===")

    # Create mock components
    mock_client = MockClient()
    mock_agent = MockAgent("test_agent_002")
    mock_client.set_mock_agent(mock_agent)

    # Initialize action manager
    action_manager = ActionManager(
        agent_id=mock_agent.id,
        send_message_callback=mock_client.send_tcp_message,
    )
    mock_agent.action_manager = action_manager

    # Create RequestMoveTo node
    move_node = RequestMoveTo(
        target_x=80.0,
        target_y=20.0,
        speed_multiplier=1.5,
    )

    # Test node execution
    logger.info("Starting RequestMoveTo behavior tree node...")
    success = move_node.start_action(mock_agent)
    assert success, "RequestMoveTo node should start successfully"

    # Simulate behavior tree updates
    from client.behavior_tree.nodes.base import NodeStatus

    max_updates = 10
    updates = 0

    while updates < max_updates:
        status = await move_node.update_action(mock_agent, 0.1)
        updates += 1

        logger.info(f"Update {updates}: Node status = {status}")

        if status == NodeStatus.SUCCESS:
            logger.info("✅ RequestMoveTo node completed successfully!")
            break
        elif status == NodeStatus.FAILURE:
            logger.error("❌ RequestMoveTo node failed!")
            break
        elif status == NodeStatus.RUNNING:
            # Keep updating
            await asyncio.sleep(0.1)
        else:
            logger.warning(f"Unexpected node status: {status}")
            break

    # Check final stats
    stats = action_manager.get_stats()
    logger.info(f"Final action manager stats: {stats}")

    assert stats["requests_sent"] >= 1, "Should have sent at least one request"
    logger.info("✅ RequestAction behavior tree node test passed!")


@pytest.mark.asyncio
async def test_prediction_system():
    """Test client-side prediction"""
    logger.info("=== Testing Client-Side Prediction ===")

    # Create mock components
    mock_client = MockClient()
    mock_agent = MockAgent("test_agent_003")
    mock_client.set_mock_agent(mock_agent)

    action_manager = ActionManager(
        agent_id=mock_agent.id,
        send_message_callback=mock_client.send_tcp_message,
    )
    mock_agent.action_manager = action_manager

    # Test prediction callbacks
    predictions_made = []
    rollbacks_applied = []

    async def prediction_callback(request, predicted_state):
        predictions_made.append((request.action_id, predicted_state))
        logger.info(f"Prediction applied for action {request.action_id}")

    async def rollback_callback(request, predicted_state):
        rollbacks_applied.append((request.action_id, predicted_state))
        logger.info(f"Rollback applied for action {request.action_id}")

    action_manager.register_prediction_callback(prediction_callback)
    action_manager.register_rollback_callback(rollback_callback)

    # Request action with prediction
    action_id = await action_manager.request_action(
        action_type=ActionType.MOVE_TO,
        parameters=move_to_params(25.0, 25.0),
        predict=True,
    )

    # Wait for processing
    await asyncio.sleep(0.2)

    # Check results
    stats = action_manager.get_stats()
    logger.info(
        f"Prediction stats: predictions={stats['predictions_made']}, rollbacks={stats['rollbacks_applied']}"
    )

    assert len(predictions_made) >= 1, "Should have made at least one prediction"
    logger.info("✅ Client-side prediction test passed!")


async def main():
    """Run all action system tests"""
    logger.info("🚀 Starting Action System Tests")

    try:
        await test_action_manager()
        await test_request_action_node()
        await test_prediction_system()

        logger.info("🎉 All action system tests passed!")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
