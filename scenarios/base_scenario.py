from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class BaseScenario(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.agents = []
        self.server = None
        self.visualization_enabled = True

    @abstractmethod
    async def setup(self, server):
        """Setup the scenario with initial agents and world state"""
        pass

    @abstractmethod
    async def spawn_agents(self) -> List[Dict[str, Any]]:
        """Spawn and return list of agent configurations"""
        pass

    async def initialize(self, server):
        """Initialize scenario with server instance"""
        self.server = server
        logger.info(f"Initializing scenario: {self.name}")
        logger.info(f"Description: {self.description}")
        await self.setup(server)
        agent_configs = await self.spawn_agents()
        return agent_configs

    def get_info(self) -> Dict[str, Any]:
        """Get scenario information"""
        return {
            'name': self.name,
            'description': self.description,
            'agent_count': len(self.agents),
            'visualization': self.visualization_enabled
        }