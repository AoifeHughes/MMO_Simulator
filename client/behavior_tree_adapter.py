"""
Behavior Tree Adapter for Simplified Architecture

This adapts the existing behavior tree system to work with the simplified
client-server architecture while preserving all the decision-making logic.

Key changes:
- Action execution goes through simplified action callback
- Removes complex action managers and prediction systems
- Maintains all behavior tree logic and decision making
- Simple, direct action-to-server communication
"""

import logging
from typing import Any, Dict, Optional

from client.behavior_tree.nodes.base import ActionNode, ConditionNode
from shared.simple_messages import SimpleActionType

logger = logging.getLogger(__name__)


class SimplifiedActionNode(ActionNode):
    """
    Base action node that works with simplified client architecture
    """

    def __init__(self, name: str):
        super().__init__(name)
        self.last_action_time = 0.0
        self.action_cooldown = 1.0  # 1 second default cooldown
        self.action_sent = False

    def start_action(self, agent) -> bool:
        """Start the action using simplified callback"""
        import time

        # Check cooldown
        current_time = time.time()
        if (current_time - self.last_action_time) < self.action_cooldown:
            return False

        # Get action parameters
        action_type, parameters = self.get_action_data(agent)
        if not action_type:
            return False

        # Send action through simplified callback
        if hasattr(agent, "simplified_action_callback"):
            import asyncio

            try:
                # Create task for async action
                asyncio.create_task(
                    agent.simplified_action_callback(action_type, parameters)
                )
                self.last_action_time = current_time
                self.action_sent = True
                logger.debug(
                    f"SimplifiedActionNode: Sent {action_type} action for agent {agent.id[:8]}"
                )
                return True
            except Exception as e:
                logger.error(f"Error sending simplified action: {e}")
                return False
        else:
            logger.warning(f"Agent {agent.id[:8]} has no simplified_action_callback")
            return False

    def update_action(self, agent, delta_time: float):
        """Update the running action"""
        from client.behavior_tree.nodes.base import NodeStatus

        # For simplified actions, we just return success after sending
        if self.action_sent:
            self.action_sent = False
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING

    def stop_action(self, agent):
        """Stop/cleanup the action"""
        self.action_sent = False

    def get_action_data(self, agent) -> tuple:
        """Override in subclasses to provide action type and parameters"""
        return None, {}


class SimplifiedMoveToNode(SimplifiedActionNode):
    """Move to target action using simplified system"""

    def __init__(self, target_x: float = None, target_y: float = None):
        super().__init__("SimplifiedMoveTo")
        self.target_x = target_x
        self.target_y = target_y
        self.action_cooldown = 0.1  # Fast movement updates

    def get_action_data(self, agent):
        """Get move action data"""
        if self.target_x is not None and self.target_y is not None:
            target_x, target_y = self.target_x, self.target_y
        elif hasattr(agent, "current_target") and agent.current_target:
            target_x, target_y = agent.current_target
        else:
            return None, {}

        return SimpleActionType.MOVE_TO, {"target_x": target_x, "target_y": target_y}


class SimplifiedFishNode(SimplifiedActionNode):
    """Fishing action using simplified system"""

    def __init__(self):
        super().__init__("SimplifiedFish")
        self.action_cooldown = 3.0  # Fishing takes time

    def get_action_data(self, agent):
        """Get fishing action data"""
        return SimpleActionType.FISH, {}


class SimplifiedHarvestWoodNode(SimplifiedActionNode):
    """Wood harvesting action using simplified system"""

    def __init__(self):
        super().__init__("SimplifiedHarvestWood")
        self.action_cooldown = 2.5  # Harvesting takes time

    def get_action_data(self, agent):
        """Get wood harvesting action data"""
        return SimpleActionType.HARVEST_WOOD, {}


class SimplifiedAttackNode(SimplifiedActionNode):
    """Attack action using simplified system"""

    def __init__(self, target_id: str = None):
        super().__init__("SimplifiedAttack")
        self.target_id = target_id
        self.action_cooldown = 1.5  # Attack cooldown

    def get_action_data(self, agent):
        """Get attack action data"""
        target_id = self.target_id

        # If no specific target, find nearest enemy
        if not target_id:
            nearest_enemy = agent.get_nearest_entity_of_type(["enemy", "player"])
            if nearest_enemy:
                target_id = nearest_enemy.get("id")

        if not target_id:
            return None, {}

        return SimpleActionType.ATTACK, {"target_id": target_id}


class SimplifiedStopNode(SimplifiedActionNode):
    """Stop movement action using simplified system"""

    def __init__(self):
        super().__init__("SimplifiedStop")
        self.action_cooldown = 0.1  # Can stop frequently

    def get_action_data(self, agent):
        """Get stop action data"""
        return SimpleActionType.STOP, {}


# Condition nodes for decision making (unchanged logic)
class NearWaterCondition(ConditionNode):
    """Check if agent is near water for fishing"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("NearWater")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if water is nearby"""
        # This would need access to terrain data
        # For now, return True to allow fishing attempts
        return True


class NearWoodCondition(ConditionNode):
    """Check if agent is near wood for harvesting"""

    def __init__(self, max_distance: float = 5.0):
        super().__init__("NearWood")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if wood is nearby"""
        # This would need access to terrain data
        # For now, return True to allow harvesting attempts
        return True


class EnemyInRangeCondition(ConditionNode):
    """Check if enemy is in attack range"""

    def __init__(self, max_distance: float = 3.0):
        super().__init__("EnemyInRange")
        self.max_distance = max_distance

    def check_condition(self, agent) -> bool:
        """Check if any enemy is in range"""
        enemies = agent.find_entities_by_type(["enemy", "player"])
        for enemy in enemies:
            if enemy.get("id") != agent.id:  # Don't attack self
                distance = (
                    (enemy["x"] - agent.x) ** 2 + (enemy["y"] - agent.y) ** 2
                ) ** 0.5
                if distance <= self.max_distance:
                    return True
        return False


class HealthLowCondition(ConditionNode):
    """Check if agent health is low"""

    def __init__(self, threshold: float = 30.0):
        super().__init__("HealthLow")
        self.threshold = threshold

    def check_condition(self, agent) -> bool:
        """Check if health is below threshold"""
        return agent.health < self.threshold


def create_simple_explorer_tree():
    """Create a simple behavior tree for explorer agents using simplified actions"""
    from client.behavior_tree.nodes.composite import PrioritySelector, Sequence
    from client.behavior_tree.tree import BehaviorTree

    # Create behavior tree with simplified actions
    root = PrioritySelector("ExplorerRoot")

    # Fishing behavior
    fishing_sequence = Sequence("FishingSequence")
    fishing_sequence.add_child(NearWaterCondition())
    fishing_sequence.add_child(SimplifiedFishNode())

    # Wood harvesting behavior
    harvesting_sequence = Sequence("HarvestingSequence")
    harvesting_sequence.add_child(NearWoodCondition())
    harvesting_sequence.add_child(SimplifiedHarvestWoodNode())

    # Exploration behavior (move to random location)
    exploration_sequence = Sequence("ExplorationSequence")
    exploration_sequence.add_child(SimplifiedMoveToNode(50.0, 50.0))  # Simple target

    # Add behaviors to root
    root.add_child(fishing_sequence)
    root.add_child(harvesting_sequence)
    root.add_child(exploration_sequence)

    return BehaviorTree("SimpleExplorer", root)


def create_simple_combat_tree():
    """Create a simple behavior tree for combat agents using simplified actions"""
    from client.behavior_tree.nodes.composite import PrioritySelector, Sequence
    from client.behavior_tree.tree import BehaviorTree

    root = PrioritySelector("CombatRoot")

    # Flee when health is low
    flee_sequence = Sequence("FleeSequence")
    flee_sequence.add_child(HealthLowCondition())
    flee_sequence.add_child(SimplifiedMoveToNode(10.0, 10.0))  # Move to corner

    # Attack when enemy in range
    attack_sequence = Sequence("AttackSequence")
    attack_sequence.add_child(EnemyInRangeCondition())
    attack_sequence.add_child(SimplifiedAttackNode())

    # Default exploration
    exploration_sequence = Sequence("ExplorationSequence")
    exploration_sequence.add_child(SimplifiedMoveToNode(75.0, 75.0))

    # Add behaviors to root
    root.add_child(flee_sequence)
    root.add_child(attack_sequence)
    root.add_child(exploration_sequence)

    return BehaviorTree("SimpleCombat", root)


def add_simplified_trees_to_agent(agent):
    """Add simplified behavior trees to existing agents"""
    if agent.agent_type in ["explorer", "fishing_explorer"]:
        tree = create_simple_explorer_tree()
        agent.set_behavior_tree(tree)
        logger.info(f"Added simplified explorer tree to agent {agent.id[:8]}")
    elif agent.agent_type in ["enemy", "npc"]:
        tree = create_simple_combat_tree()
        agent.set_behavior_tree(tree)
        logger.info(f"Added simplified combat tree to agent {agent.id[:8]}")
    else:
        # Default to explorer tree
        tree = create_simple_explorer_tree()
        agent.set_behavior_tree(tree)
        logger.info(f"Added default simplified tree to agent {agent.id[:8]}")
