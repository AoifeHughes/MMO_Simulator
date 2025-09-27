#!/usr/bin/env python3
"""
Quick test to verify the floating point precision fix for action validation.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from unittest.mock import Mock

from client.behavior_tree.nodes.two_phase_action import ResourceActionNode
from world.tiles import TileType


def test_precision_issue():
    """Test the specific case that was failing"""

    print("🧪 Testing precision issue fix...")

    # Create a test action
    class TestAction(ResourceActionNode):
        def execute_action(self, agent, target_pos):
            return True

        def get_action_name(self):
            return "test"

        def get_resource_type(self):
            return "test"

    action = TestAction("TestAction", TileType.WATER, 5.0)

    # Set up the exact scenario from the logs
    action.target_position = (10.5, 12.5)  # Original target
    action.required_distance = 1.0  # Default from ResourceActionNode

    # Create mock agent at the calculated optimal position
    mock_agent = Mock()
    mock_agent.id = "test_agent_12345678"
    mock_agent.x = 11.27  # From log: optimal position
    mock_agent.y = 11.87  # From log: optimal position

    print(f"Target: ({action.target_position[0]}, {action.target_position[1]})")
    print(f"Agent:  ({mock_agent.x}, {mock_agent.y})")

    # Calculate actual distance
    distance = action._distance((mock_agent.x, mock_agent.y), action.target_position)
    print(f"Distance: {distance:.6f}")
    print(f"Required: {action.required_distance:.6f}")
    print(f"With buffer: {action.required_distance + action.validation_buffer:.6f}")

    # Test validation
    is_valid = action._validate_action_position(mock_agent)

    print(f"Validation result: {'✅ PASS' if is_valid else '❌ FAIL'}")

    # Test with the new safe distance calculation
    safe_distance = action.required_distance - 0.02
    safe_position_distance = (
        (action.target_position[0] - (action.target_position[0] + safe_distance)) ** 2
        + (action.target_position[1] - action.target_position[1]) ** 2
    ) ** 0.5

    print(f"\n🔧 With new safe distance calculation:")
    print(f"Safe distance: {safe_distance:.6f}")
    print(f"Safe position would be at distance: {safe_distance:.6f} from target")
    print(
        f"This should always pass validation: {safe_distance <= (action.required_distance + action.validation_buffer)}"
    )

    return is_valid


if __name__ == "__main__":
    success = test_precision_issue()
    if success:
        print("\n✅ Precision fix successful!")
    else:
        print("\n❌ Fix needs more work")
        sys.exit(1)
