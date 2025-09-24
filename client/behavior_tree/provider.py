"""
Behavior tree provider interfaces and implementations.

This module provides a clean abstraction layer for behavior tree selection,
allowing scenarios to provide custom trees while maintaining backward compatibility
with the default TreeFactory system.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Protocol

from .tree import BehaviorTree

logger = logging.getLogger(__name__)


class BehaviorTreeProvider(Protocol):
    """
    Protocol for behavior tree providers.

    Any class that can provide behavior trees for agents should implement this protocol.
    This includes scenarios with custom trees and the TreeFactory for default behavior.
    """

    def get_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float, **kwargs) -> Optional[BehaviorTree]:
        """
        Get behavior tree for the specified agent type and position.

        Args:
            agent_type: Type of agent ("explorer", "player", etc.)
            agent_x: Agent's spawn X position
            agent_y: Agent's spawn Y position
            **kwargs: Additional parameters for tree creation

        Returns:
            BehaviorTree instance or None if no tree available
        """
        ...


class BehaviorTreeInjector:
    """
    Central service that coordinates behavior tree selection and injection.

    This class implements the strategy pattern for tree selection:
    1. Try scenario-provided custom tree first
    2. Fall back to TreeFactory default
    3. Provide comprehensive logging of decisions
    """

    def __init__(self, scenario_provider: Optional[BehaviorTreeProvider] = None):
        """
        Initialize behavior tree injector.

        Args:
            scenario_provider: Optional scenario that provides custom trees
        """
        self.scenario_provider = scenario_provider
        self.tree_selections = {}  # Track which trees were selected for logging

    def get_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float, **kwargs) -> Optional[BehaviorTree]:
        """
        Get behavior tree using priority-based selection.

        Args:
            agent_type: Type of agent
            agent_x: Agent's spawn X position
            agent_y: Agent's spawn Y position
            **kwargs: Additional parameters for tree creation

        Returns:
            BehaviorTree instance or None if no tree available
        """
        tree = None
        selection_source = "none"

        # Try scenario custom tree first
        if self.scenario_provider:
            try:
                tree = self.scenario_provider.get_behavior_tree(agent_type, agent_x, agent_y, **kwargs)
                if tree:
                    selection_source = "scenario"
                    logger.info(f"Using custom behavior tree from scenario for {agent_type}")
            except Exception as e:
                logger.warning(f"Failed to get custom tree from scenario for {agent_type}: {e}")

        # Fall back to TreeFactory default
        if tree is None:
            from .tree_configs import TreeFactory
            tree = TreeFactory.create_tree_for_agent_type(agent_type, agent_x, agent_y, **kwargs)
            if tree:
                selection_source = "factory"
                logger.debug(f"Using default TreeFactory behavior tree for {agent_type}")

        # Record selection for debugging
        self.tree_selections[agent_type] = selection_source

        if tree is None:
            logger.error(f"No behavior tree available for agent type: {agent_type}")

        return tree

    def set_scenario_provider(self, provider: Optional[BehaviorTreeProvider]):
        """
        Update the scenario provider.

        Args:
            provider: New scenario provider or None
        """
        self.scenario_provider = provider
        logger.debug(f"Updated scenario provider: {provider is not None}")

    def get_selection_info(self) -> dict:
        """
        Get information about tree selections made.

        Returns:
            Dictionary mapping agent types to selection sources
        """
        return self.tree_selections.copy()

    def log_tree_usage_summary(self):
        """Log a summary of all behavior tree selections made."""
        if not self.tree_selections:
            logger.info("[TREE SELECTION SUMMARY] No behavior trees have been requested yet")
            return

        logger.info("[TREE SELECTION SUMMARY] Behavior tree usage:")
        for agent_type, source in self.tree_selections.items():
            logger.info(f"  - {agent_type}: {source}")

        scenario_count = sum(1 for source in self.tree_selections.values() if source == "scenario")
        factory_count = sum(1 for source in self.tree_selections.values() if source == "factory")
        failed_count = sum(1 for source in self.tree_selections.values() if source == "none")

        logger.info(f"[TREE SELECTION SUMMARY] Total: {len(self.tree_selections)} agents")
        logger.info(f"[TREE SELECTION SUMMARY] Scenario custom: {scenario_count}")
        logger.info(f"[TREE SELECTION SUMMARY] TreeFactory default: {factory_count}")
        logger.info(f"[TREE SELECTION SUMMARY] Failed: {failed_count}")


class DefaultTreeFactoryProvider:
    """
    Adapter that makes TreeFactory conform to BehaviorTreeProvider protocol.

    This allows TreeFactory to be used as a provider in the new system
    while maintaining backward compatibility.
    """

    def get_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float, **kwargs) -> Optional[BehaviorTree]:
        """Get behavior tree from TreeFactory."""
        from .tree_configs import TreeFactory
        return TreeFactory.create_tree_for_agent_type(agent_type, agent_x, agent_y, **kwargs)


class ScenarioTreeProvider:
    """
    Adapter that makes scenarios conform to BehaviorTreeProvider protocol.

    This allows scenarios with custom behavior trees to be used as providers
    in the new injection system.
    """

    def __init__(self, scenario: "BaseScenario"):
        """
        Initialize scenario tree provider.

        Args:
            scenario: Scenario instance that provides custom trees
        """
        self.scenario = scenario

    def get_behavior_tree(self, agent_type: str, agent_x: float, agent_y: float, **kwargs) -> Optional[BehaviorTree]:
        """Get behavior tree from scenario."""
        if hasattr(self.scenario, 'get_custom_behavior_tree'):
            return self.scenario.get_custom_behavior_tree(agent_type, agent_x, agent_y)
        return None