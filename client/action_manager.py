"""
Client-Side Action Manager

This module handles action requests from client agents and manages:
- Action request queuing and sending to server
- Client-side prediction for responsive gameplay
- Rollback when server rejects predicted actions
- Action retry logic and error handling
- Response caching to reduce server load
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from shared.actions import (
    ActionBatch,
    ActionPriority,
    ActionRequest,
    ActionResponse,
    ActionResult,
    ActionType,
)
from shared.messages import Message, MessageType

logger = logging.getLogger(__name__)


class PredictionState:
    """Tracks the state of a predicted action"""

    def __init__(self, request: ActionRequest, predicted_state: Dict[str, Any]):
        self.request = request
        self.predicted_state = predicted_state
        self.timestamp = time.time()
        self.confirmed = False
        self.rollback_applied = False


class ActionManager:
    """Manages client-side action requests, predictions, and responses"""

    def __init__(self, agent_id: str, send_message_callback: Callable):
        self.agent_id = agent_id
        self.send_message = send_message_callback

        # Request tracking
        self.pending_requests: Dict[str, ActionRequest] = {}
        self.request_sequence = 0

        # Prediction system
        self.predictions: Dict[str, PredictionState] = {}
        self.prediction_timeout = 5.0  # Max time to wait for server confirmation

        # Response caching
        self.response_cache: Dict[str, ActionResponse] = {}
        self.cache_timeout = 30.0

        # Retry system
        self.retry_queue: deque = deque()
        self.retry_delays = [0.1, 0.25, 0.5, 1.0, 2.0]  # Exponential backoff

        # Statistics
        self.stats = {
            "requests_sent": 0,
            "responses_received": 0,
            "predictions_made": 0,
            "rollbacks_applied": 0,
            "cache_hits": 0,
            "errors": 0,
        }

        # Event callbacks
        self.action_callbacks: Dict[ActionType, List[Callable]] = defaultdict(list)
        self.prediction_callbacks: List[Callable] = []
        self.rollback_callbacks: List[Callable] = []

    async def request_action(
        self,
        action_type: ActionType,
        parameters: Dict[str, Any],
        priority: ActionPriority = ActionPriority.NORMAL,
        predict: bool = True,
    ) -> str:
        """
        Request an action from the server.

        Args:
            action_type: Type of action to perform
            parameters: Action-specific parameters
            priority: Request priority for server processing
            predict: Whether to apply optimistic prediction

        Returns:
            action_id for tracking the request
        """
        # Create request
        request = ActionRequest(
            agent_id=self.agent_id,
            action_type=action_type,
            parameters=parameters.copy(),
            client_sequence=self._get_next_sequence(),
            priority=priority,
        )

        # Apply client-side prediction if enabled
        if predict and self._can_predict_action(action_type):
            predicted_state = await self._apply_prediction(request)
            if predicted_state:
                self.predictions[request.action_id] = PredictionState(request, predicted_state)
                self.stats["predictions_made"] += 1

                # Notify prediction callbacks
                for callback in self.prediction_callbacks:
                    try:
                        await callback(request, predicted_state)
                    except Exception as e:
                        logger.error(f"Error in prediction callback: {e}")

        # Send request to server
        await self._send_action_request(request)

        # Track pending request
        self.pending_requests[request.action_id] = request
        self.stats["requests_sent"] += 1

        return request.action_id

    async def request_batch(
        self,
        actions: List[Tuple[ActionType, Dict[str, Any]]],
        atomic: bool = False,
        priority: ActionPriority = ActionPriority.NORMAL,
    ) -> str:
        """
        Request multiple actions in a batch.

        Args:
            actions: List of (action_type, parameters) tuples
            atomic: Whether all actions must succeed or all fail
            priority: Batch priority for server processing

        Returns:
            batch_id for tracking
        """
        # Create action requests
        requests = []
        for action_type, parameters in actions:
            request = ActionRequest(
                agent_id=self.agent_id,
                action_type=action_type,
                parameters=parameters.copy(),
                client_sequence=self._get_next_sequence(),
                priority=priority,
            )
            requests.append(request)
            self.pending_requests[request.action_id] = request

        # Create batch
        batch = ActionBatch(
            agent_id=self.agent_id,
            actions=requests,
            atomic=atomic,
        )

        # Send batch to server
        await self._send_action_batch(batch)

        self.stats["requests_sent"] += len(requests)
        return batch.batch_id

    async def handle_response(self, response: ActionResponse):
        """Handle action response from server"""
        self.stats["responses_received"] += 1

        # Find the original request
        request = self.pending_requests.pop(response.action_id, None)
        if not request:
            logger.warning(f"Received response for unknown action {response.action_id}")
            return

        # Check if we made a prediction for this action
        prediction = self.predictions.pop(response.action_id, None)

        if response.result == ActionResult.APPROVED:
            await self._handle_approved_action(request, response, prediction)
        elif response.result == ActionResult.MODIFIED:
            await self._handle_modified_action(request, response, prediction)
        elif response.result == ActionResult.REJECTED:
            await self._handle_rejected_action(request, response, prediction)
        else:  # ERROR
            await self._handle_error_action(request, response, prediction)

        # Cache successful responses
        if response.result in (ActionResult.APPROVED, ActionResult.MODIFIED):
            cache_key = self._get_cache_key(request)
            if cache_key:
                self.response_cache[cache_key] = response

        # Trigger action callbacks
        callbacks = self.action_callbacks.get(request.action_type, [])
        for callback in callbacks:
            try:
                await callback(request, response, prediction)
            except Exception as e:
                logger.error(f"Error in action callback: {e}")

    async def handle_batch_response(self, responses: List[ActionResponse]):
        """Handle batch action response from server"""
        for response in responses:
            await self.handle_response(response)

    def register_action_callback(self, action_type: ActionType, callback: Callable):
        """Register callback for when specific action type completes"""
        self.action_callbacks[action_type].append(callback)

    def register_prediction_callback(self, callback: Callable):
        """Register callback for when predictions are applied"""
        self.prediction_callbacks.append(callback)

    def register_rollback_callback(self, callback: Callable):
        """Register callback for when rollbacks occur"""
        self.rollback_callbacks.append(callback)

    async def _send_action_request(self, request: ActionRequest):
        """Send action request to server"""
        message = Message(
            type=MessageType.ACTION_REQUEST,
            payload=request.to_dict(),
            timestamp=time.time(),
        )
        await self.send_message(message)

    async def _send_action_batch(self, batch: ActionBatch):
        """Send action batch to server"""
        message = Message(
            type=MessageType.ACTION_BATCH,
            payload=batch.to_dict(),
            timestamp=time.time(),
        )
        await self.send_message(message)

    def _can_predict_action(self, action_type: ActionType) -> bool:
        """Check if we can safely predict this action type client-side"""
        # Movement actions are generally safe to predict
        safe_predictions = {
            ActionType.MOVE_TO,
            ActionType.MOVE_DIRECTION,
            ActionType.STOP_MOVEMENT,
        }
        return action_type in safe_predictions

    async def _apply_prediction(self, request: ActionRequest) -> Optional[Dict[str, Any]]:
        """Apply optimistic client-side prediction"""
        if request.action_type == ActionType.MOVE_TO:
            return await self._predict_move_to(request)
        elif request.action_type == ActionType.STOP_MOVEMENT:
            return await self._predict_stop_movement(request)
        else:
            return None

    async def _predict_move_to(self, request: ActionRequest) -> Optional[Dict[str, Any]]:
        """Predict MOVE_TO action client-side"""
        params = request.parameters
        target_x = params.get("target_x")
        target_y = params.get("target_y")

        if target_x is None or target_y is None:
            return None

        # Store current state for potential rollback
        # This would need access to the agent object - simplified for now
        return {
            "action_type": "move_prediction",
            "target_x": target_x,
            "target_y": target_y,
            "predicted_time": time.time(),
        }

    async def _predict_stop_movement(self, request: ActionRequest) -> Optional[Dict[str, Any]]:
        """Predict STOP_MOVEMENT action client-side"""
        return {
            "action_type": "stop_prediction",
            "predicted_time": time.time(),
        }

    async def _handle_approved_action(
        self, request: ActionRequest, response: ActionResponse, prediction: Optional[PredictionState]
    ):
        """Handle server approval of action"""
        if prediction:
            prediction.confirmed = True
            logger.debug(f"Prediction confirmed for action {request.action_id}")

    async def _handle_modified_action(
        self, request: ActionRequest, response: ActionResponse, prediction: Optional[PredictionState]
    ):
        """Handle server modification of action"""
        if prediction and not prediction.rollback_applied:
            # Server modified our action, need to adjust prediction
            await self._apply_rollback(prediction)
            logger.debug(f"Prediction adjusted for modified action {request.action_id}")

        # Apply the server's modified version
        if response.approved_parameters:
            logger.debug(f"Applying server modifications for action {request.action_id}")

    async def _handle_rejected_action(
        self, request: ActionRequest, response: ActionResponse, prediction: Optional[PredictionState]
    ):
        """Handle server rejection of action"""
        if prediction and not prediction.rollback_applied:
            await self._apply_rollback(prediction)
            logger.debug(f"Rolled back prediction for rejected action {request.action_id}")

        # Check if we should retry
        if request.retry_count < request.max_retries and self._should_retry(response):
            request.retry_count += 1
            delay = self.retry_delays[min(request.retry_count - 1, len(self.retry_delays) - 1)]
            asyncio.create_task(self._retry_after_delay(request, delay))
            logger.debug(f"Scheduling retry {request.retry_count} for action {request.action_id}")

    async def _handle_error_action(
        self, request: ActionRequest, response: ActionResponse, prediction: Optional[PredictionState]
    ):
        """Handle server error processing action"""
        self.stats["errors"] += 1

        if prediction and not prediction.rollback_applied:
            await self._apply_rollback(prediction)
            logger.debug(f"Rolled back prediction due to server error for action {request.action_id}")

        logger.error(f"Server error for action {request.action_id}: {response.message}")

    async def _apply_rollback(self, prediction: PredictionState):
        """Rollback a client prediction"""
        if prediction.rollback_applied:
            return

        prediction.rollback_applied = True
        self.stats["rollbacks_applied"] += 1

        # Notify rollback callbacks
        for callback in self.rollback_callbacks:
            try:
                await callback(prediction.request, prediction.predicted_state)
            except Exception as e:
                logger.error(f"Error in rollback callback: {e}")

    def _should_retry(self, response: ActionResponse) -> bool:
        """Determine if an action should be retried based on the response"""
        # Retry on certain error conditions
        retry_conditions = {
            "Rate limit exceeded",
            "Action on cooldown",
            "Server temporarily unavailable",
        }
        return any(condition in response.message for condition in retry_conditions)

    async def _retry_after_delay(self, request: ActionRequest, delay: float):
        """Retry an action after a delay"""
        await asyncio.sleep(delay)

        # Check if we should still retry
        if request.retry_count <= request.max_retries:
            await self._send_action_request(request)
            self.pending_requests[request.action_id] = request

    def _get_next_sequence(self) -> int:
        """Get next sequence number for ordering"""
        self.request_sequence += 1
        return self.request_sequence

    def _get_cache_key(self, request: ActionRequest) -> Optional[str]:
        """Generate cache key for request (if cacheable)"""
        # Only cache certain types of requests
        if request.action_type in {ActionType.PING, ActionType.HEARTBEAT}:
            return f"{request.action_type.value}:{request.agent_id}"
        return None

    async def cleanup_old_predictions(self):
        """Clean up old predictions that haven't been confirmed"""
        now = time.time()
        expired_predictions = []

        for action_id, prediction in self.predictions.items():
            if (now - prediction.timestamp) > self.prediction_timeout:
                expired_predictions.append(action_id)

        for action_id in expired_predictions:
            prediction = self.predictions.pop(action_id, None)
            if prediction and not prediction.confirmed and not prediction.rollback_applied:
                await self._apply_rollback(prediction)
                logger.warning(f"Rolled back expired prediction for action {action_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get action manager statistics"""
        return {
            **self.stats,
            "pending_requests": len(self.pending_requests),
            "active_predictions": len(self.predictions),
            "cached_responses": len(self.response_cache),
            "retry_queue_size": len(self.retry_queue),
        }