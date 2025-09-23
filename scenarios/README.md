# Scenarios Module

Pre-configured simulation scenarios for testing different agent behaviors and interactions.

## Available Scenarios

### basic_combat
Intense combat arena with players vs enemies in close quarters.
- 2 Player agents vs 4 Enemy agents
- Close formation spawning for guaranteed engagement
- Demonstrates combat mechanics, damage, death, and respawn

### exploration_demo
Multiple explorer agents with different mapping strategies.
- 5 Explorer agents using various exploration modes
- 3 NPCs and 2 Enemies for interaction variety
- Showcases pathfinding and world mapping capabilities

### peaceful_village
Social simulation with peaceful NPCs.
- Multiple NPC agents wandering and interacting
- No combat, focus on social behaviors
- Demonstrates basic agent interactions

### pathfinding_demo
Single agent following predetermined waypoints.
- 1 PathfindingTest agent with fixed route
- Tests A* pathfinding and navigation
- Useful for debugging movement systems

### simple_duel
Minimal 1v1 combat scenario.
- 1 Player vs 1 Enemy
- Simple combat testing environment
- Quick scenario for basic combat validation

## Usage

```bash
# Run a specific scenario
python main.py --scenario basic_combat

# List all available scenarios
python main.py --list-scenarios

# Run scenario without visualization
python main.py --scenario exploration_demo --no-viz
```

## Creating New Scenarios

1. Inherit from `BaseScenario`
2. Implement `setup()` and `spawn_agents()` methods
3. Register in `ScenarioManager`
4. Add to command-line help

Example:
```python
class CustomScenario(BaseScenario):
    def __init__(self):
        super().__init__(
            name="Custom Scenario",
            description="Your scenario description"
        )

    async def setup(self, server):
        self.server = server

    async def spawn_agents(self):
        # Spawn your agents here
        return agent_configs
```
