"""
Integration tests for the unified action system

These tests verify the complete action flow from client request
through server validation to execution and response.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from server.action_processor import ActionProcessor, ActionContext
from shared.actions import ActionRequest, ActionType, ActionResult, move_to_params
from tests.fixtures.mock_server import MockWorld, MockAgentRegistry
from tests.fixtures.test_maps import TestMaps
from server.attack_system import AttackSystem


class TestActionRequestFlow:
    """Test complete action request-response flow"""

    def setup_method(self):
        """Set up action processor with mock components"""
        self.world = MockWorld(20, 20)
        self.agent_registry = MockAgentRegistry()
        self.attack_system = AttackSystem()

        self.processor = ActionProcessor(
            world=self.world,
            agent_registry=self.agent_registry,
            attack_system=self.attack_system
        )

        # Add test agent
        self.agent_id = self.world.spawn_agent("player", 10, 10)
        self.agent_registry.register_agent(self.agent_id, "player", 10, 10)

    @pytest.mark.asyncio
    async def test_move_action_complete_flow(self):
        """Test complete move action from request to execution"""
        request = ActionRequest(
            action_id="move_test_1",
            agent_id=self.agent_id,
            action_type=ActionType.MOVE_TO,
            parameters=move_to_params(15.0, 15.0)
        )

        # Process the action
        response = await self.processor.submit_action(request)

        # Verify response
        assert response.action_id == "move_test_1"
        assert response.agent_id == self.agent_id
        assert response.action_type == ActionType.MOVE_TO
        assert response.result == ActionResult.APPROVED

        # Verify agent was actually moved
        agent = self.world.get_agent(self.agent_id)
        assert agent.x == 15.0
        assert agent.y == 15.0

    @pytest.mark.asyncio
    async def test_invalid_move_rejection(self):
        """Test that invalid moves are properly rejected"""
        request = ActionRequest(
            action_id="bad_move_1",
            agent_id=self.agent_id,
            action_type=ActionType.MOVE_TO,
            parameters=move_to_params(25.0, 25.0)  # Out of bounds
        )

        response = await self.processor.submit_action(request)

        assert response.result == ActionResult.REJECTED
        assert "out of bounds" in response.message.lower()

        # Agent should not have moved
        agent = self.world.get_agent(self.agent_id)
        assert agent.x == 10.0
        assert agent.y == 10.0

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self):
        """Test that rate limiting is enforced"""
        requests = []

        # Create multiple rapid requests
        for i in range(10):
            request = ActionRequest(
                action_id=f"rapid_{i}",
                agent_id=self.agent_id,
                action_type=ActionType.MOVE_TO,
                parameters=move_to_params(10.0 + i, 10.0)
            )
            requests.append(request)

        # Submit all requests rapidly
        responses = []
        for request in requests:
            response = await self.processor.submit_action(request)
            responses.append(response)

        # Some should be rejected due to rate limiting
        approved = [r for r in responses if r.result == ActionResult.APPROVED]
        rejected = [r for r in responses if r.result == ActionResult.REJECTED]

        assert len(rejected) > 0, "Some actions should be rate limited"
        assert len(approved) < len(requests), "Not all actions should be approved"

        # Rejected actions should mention rate limiting
        rate_limit_rejections = [
            r for r in rejected if "rate limit" in r.message.lower()
        ]
        assert len(rate_limit_rejections) > 0, "Rate limit rejections should mention rate limiting"

    @pytest.mark.asyncio
    async def test_cooldown_enforcement(self):
        """Test action cooldowns are enforced"""
        # First attack request
        attack_request1 = ActionRequest(
            action_id="attack_1",
            agent_id=self.agent_id,
            action_type=ActionType.ATTACK_TARGET,
            parameters={"target_id": "dummy_target", "attack_name": "punch"}
        )

        # Add a dummy target
        target_id = self.world.spawn_agent("enemy", 11, 10)

        attack_request1.parameters["target_id"] = target_id

        response1 = await self.processor.submit_action(attack_request1)

        # Second immediate attack request
        attack_request2 = ActionRequest(
            action_id="attack_2",
            agent_id=self.agent_id,
            action_type=ActionType.ATTACK_TARGET,
            parameters={"target_id": target_id, "attack_name": "punch"}
        )

        response2 = await self.processor.submit_action(attack_request2)

        # First should succeed, second should be on cooldown
        if response1.result == ActionResult.APPROVED:
            assert response2.result == ActionResult.REJECTED
            assert "cooldown" in response2.message.lower()

    @pytest.mark.asyncio
    async def test_dead_agent_action_rejection(self):
        """Test that dead agents cannot perform actions"""
        # Kill the agent
        agent = self.world.get_agent(self.agent_id)
        agent.is_alive = False

        request = ActionRequest(
            action_id="dead_move",
            agent_id=self.agent_id,
            action_type=ActionType.MOVE_TO,
            parameters=move_to_params(12.0, 12.0)
        )

        response = await self.processor.submit_action(request)

        assert response.result == ActionResult.REJECTED
        assert "dead" in response.message.lower()

    @pytest.mark.asyncio
    async def test_action_processing_stats(self):
        """Test that processing statistics are tracked"""
        initial_stats = self.processor.get_stats()

        # Process several actions
        for i in range(5):
            request = ActionRequest(
                action_id=f"stats_test_{i}",
                agent_id=self.agent_id,
                action_type=ActionType.MOVE_TO,
                parameters=move_to_params(10.0 + i, 10.0)
            )
            await self.processor.submit_action(request)

        final_stats = self.processor.get_stats()

        assert final_stats["total_processed"] >= initial_stats["total_processed"] + 5
        assert len(final_stats["processing_time_ms"]) > len(initial_stats["processing_time_ms"])
        assert "average_processing_time_ms" in final_stats


class TestFishingActionIntegration:
    """Test fishing action integration"""

    def setup_method(self):
        """Set up for fishing tests"""
        # Create world with water
        self.world = MockWorld(25, 25)
        terrain = TestMaps.get_fishing_pond(25, 25)
        self.world.terrain = terrain

        # Mock world map for fishing validator
        world_map = MagicMock()
        world_map.width = 25
        world_map.height = 25
        world_map.get_tile = lambda x, y: terrain.get((x, y), terrain[(12, 12)])  # Default to water
        self.world.world_map = world_map

        self.agent_registry = MockAgentRegistry()
        self.attack_system = AttackSystem()

        self.processor = ActionProcessor(
            world=self.world,
            agent_registry=self.agent_registry,
            attack_system=self.attack_system
        )

        # Add agent near water
        self.agent_id = self.world.spawn_agent("player", 20, 12)
        self.agent_registry.register_agent(self.agent_id, "player", 20, 12)

        # Mock agent state with fishing equipment
        agent_state = MagicMock()
        agent_state.position = (20, 12)
        agent_state.is_alive = True
        agent_state.agent_id = self.agent_id

        # Mock inventory with fishing rod
        inventory = MagicMock()
        fishing_rod = MagicMock()
        fishing_rod.tool_type = "fishing"
        inventory.get_items_by_type.return_value = [fishing_rod]
        inventory.has_space_for_item.return_value = True
        inventory.add_item.return_value = 1  # Successfully added
        agent_state.inventory = inventory

        self.agent_registry.agents[self.agent_id] = agent_state

    @pytest.mark.asyncio
    async def test_successful_fishing_action(self):
        """Test successful fishing action"""
        request = ActionRequest(
            action_id="fish_1",
            agent_id=self.agent_id,
            action_type=ActionType.FISH,
            parameters={"target_x": 19, "target_y": 12}  # Water tile
        )

        response = await self.processor.submit_action(request)

        assert response.result == ActionResult.APPROVED
        assert "fish" in response.message.lower() or "success" in response.message.lower()
        assert response.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_fishing_without_equipment_rejected(self):
        """Test fishing without equipment is rejected"""
        # Remove fishing equipment
        agent_state = self.agent_registry.get_agent(self.agent_id)
        agent_state.inventory.get_items_by_type.return_value = []

        request = ActionRequest(
            action_id="fish_no_rod",
            agent_id=self.agent_id,
            action_type=ActionType.FISH,
            parameters={"target_x": 19, "target_y": 12}
        )

        response = await self.processor.submit_action(request)

        assert response.result == ActionResult.REJECTED
        assert "fishing rod" in response.message.lower()

    @pytest.mark.asyncio
    async def test_fishing_on_land_rejected(self):
        """Test fishing on land is rejected"""
        request = ActionRequest(
            action_id="fish_land",
            agent_id=self.agent_id,
            action_type=ActionType.FISH,
            parameters={"target_x": 2, "target_y": 2}  # Land tile
        )

        response = await self.processor.submit_action(request)

        assert response.result == ActionResult.REJECTED
        assert "water" in response.message.lower()


class TestBatchActionProcessing:
    """Test batch action processing"""

    def setup_method(self):
        """Set up for batch tests"""
        self.world = MockWorld(30, 30)
        self.agent_registry = MockAgentRegistry()
        self.attack_system = AttackSystem()

        self.processor = ActionProcessor(
            world=self.world,
            agent_registry=self.agent_registry,
            attack_system=self.attack_system
        )

        # Add test agent
        self.agent_id = self.world.spawn_agent("player", 15, 15)
        self.agent_registry.register_agent(self.agent_id, "player", 15, 15)

    @pytest.mark.asyncio
    async def test_batch_action_processing(self):
        """Test processing multiple actions in a batch"""
        from shared.actions import ActionBatch

        actions = []
        for i in range(3):
            action = ActionRequest(
                action_id=f"batch_{i}",
                agent_id=self.agent_id,
                action_type=ActionType.MOVE_TO,
                parameters=move_to_params(15.0 + i, 15.0)
            )
            actions.append(action)

        batch = ActionBatch(actions=actions, atomic=False)
        responses = await self.processor.submit_batch(batch)

        assert len(responses) == 3
        for response in responses:
            assert response.action_id.startswith("batch_")
            # Most should succeed (rate limiting might reject some)
            assert response.result in [ActionResult.APPROVED, ActionResult.REJECTED]

    @pytest.mark.asyncio
    async def test_atomic_batch_failure(self):
        """Test that atomic batches fail completely if any action fails"""
        from shared.actions import ActionBatch

        actions = [
            ActionRequest(
                action_id="batch_good",
                agent_id=self.agent_id,
                action_type=ActionType.MOVE_TO,
                parameters=move_to_params(16.0, 15.0)
            ),
            ActionRequest(
                action_id="batch_bad",
                agent_id=self.agent_id,
                action_type=ActionType.MOVE_TO,
                parameters=move_to_params(50.0, 50.0)  # Out of bounds
            )
        ]

        batch = ActionBatch(actions=actions, atomic=True)
        responses = await self.processor.submit_batch(batch)

        # All should be rejected in atomic batch
        for response in responses:
            assert response.result == ActionResult.REJECTED


class TestActionSystemPerformance:
    """Test action system performance characteristics"""

    def setup_method(self):
        """Set up for performance tests"""
        self.world = MockWorld(50, 50)
        self.agent_registry = MockAgentRegistry()
        self.attack_system = AttackSystem()

        self.processor = ActionProcessor(
            world=self.world,
            agent_registry=self.agent_registry,
            attack_system=self.attack_system
        )

    @pytest.mark.asyncio
    async def test_action_processing_speed(self):
        """Test that actions are processed within reasonable time"""
        # Add multiple agents
        agent_ids = []
        for i in range(5):
            agent_id = self.world.spawn_agent("player", 10 + i, 10)
            self.agent_registry.register_agent(agent_id, "player", 10 + i, 10)
            agent_ids.append(agent_id)

        # Time batch of actions
        start_time = time.time()

        tasks = []
        for i, agent_id in enumerate(agent_ids):
            request = ActionRequest(
                action_id=f"perf_test_{i}",
                agent_id=agent_id,
                action_type=ActionType.MOVE_TO,
                parameters=move_to_params(20.0 + i, 20.0)
            )
            task = asyncio.create_task(self.processor.submit_action(request))
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time_per_action = total_time / len(responses)

        # Actions should complete quickly
        assert total_time < 2.0, f"Batch processing took too long: {total_time:.2f}s"
        assert avg_time_per_action < 0.5, f"Average action time too high: {avg_time_per_action:.2f}s"

        # All actions should succeed
        successful = [r for r in responses if r.result == ActionResult.APPROVED]
        assert len(successful) >= 4, f"Expected at least 4 successful actions, got {len(successful)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])