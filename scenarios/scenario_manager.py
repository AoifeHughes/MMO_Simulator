import logging
from typing import Any, Dict, List, Optional

from scenarios.base_scenario import BaseScenario
from scenarios.basic_combat import BasicCombatScenario
from scenarios.dual_weapon_combat import DualWeaponCombatScenario
from scenarios.duel_test import DuelTestScenario
from scenarios.exploration_demo import ExplorationDemoScenario
from scenarios.fishing_exploration import FishingExplorationScenario
from scenarios.forest_fisher_cooperation import ForestFisherCooperationScenario
from scenarios.pathfinding_demo import PathfindingDemoScenario
from scenarios.peaceful_village import PeacefulVillageScenario
from scenarios.simple_duel import SimpleDuelScenario
from scenarios.test_combat_simple import TestCombatSimpleScenario
from scenarios.test_fishing_simple import TestFishingSimpleScenario

logger = logging.getLogger(__name__)


class ScenarioManager:
    def __init__(self):
        self.scenarios: Dict[str, BaseScenario] = {}
        self.register_scenarios()
        self.active_scenario: Optional[BaseScenario] = None

    def register_scenarios(self):
        """Register all available scenarios"""
        scenarios = [
            ExplorationDemoScenario(),
            BasicCombatScenario(),
            DuelTestScenario(),
            PeacefulVillageScenario(),
            PathfindingDemoScenario(),
            SimpleDuelScenario(),
            FishingExplorationScenario(),
            ForestFisherCooperationScenario(),
            DualWeaponCombatScenario(),
            TestCombatSimpleScenario(),
            TestFishingSimpleScenario(),
        ]

        for scenario in scenarios:
            self.scenarios[scenario.name.lower().replace(" ", "_")] = scenario
            logger.info(f"Registered scenario: {scenario.name}")

    def list_scenarios(self) -> List[str]:
        """Get list of available scenario names"""
        return list(self.scenarios.keys())

    def get_scenario(self, name: str) -> Optional[BaseScenario]:
        """Get scenario by name"""
        return self.scenarios.get(name.lower())

    async def load_scenario(self, name: str, server) -> Optional[BaseScenario]:
        """Load and initialize a scenario"""
        scenario = self.get_scenario(name)
        if scenario:
            self.active_scenario = scenario
            agent_configs = await scenario.initialize(server)
            logger.info(f"Loaded scenario: {scenario.name}")
            return scenario
        else:
            logger.error(f"Scenario not found: {name}")
            available = ", ".join(self.list_scenarios())
            logger.info(f"Available scenarios: {available}")
            return None

    def get_active_scenario(self) -> Optional[BaseScenario]:
        """Get currently active scenario"""
        return self.active_scenario
