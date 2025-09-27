# Test Framework Documentation

This directory contains the improved test framework for the MMO Simulator, implementing proper software engineering practices for game testing.

## Architecture Overview

The test framework follows the **Test Pyramid** pattern with three distinct layers:

```
         /\
        /  \
       /    \
      /      \     Scenario Tests (5%)
     /        \    End-to-end, realistic game scenarios
    /          \   ~30-60s each, complex environments
   /____________\
  /              \
 /                \
/                  \  Integration Tests (15%)
\                  /  Real components, lightweight server
 \                /   ~5-10s each, component interactions
  \______________/
 /                \
/                  \  Unit Tests (80%)
\                  /  Fast, isolated, behavioral contracts
 \________________/   ~1s each, single components

```

## Core Components

### 1. WorldBuilder (`world_builder.py`)

Fluent API for creating deterministic test worlds:

```python
# Example: Create world with water obstacle
world = (WorldBuilder(20, 20)
         .with_seed(12345)  # Deterministic
         .add_water_pond(center=(10, 10), radius=3)
         .add_corridor(start=(5, 10), end=(15, 10))
         .add_agent_spawn("explorer", 5, 10)
         .build())
```

**Features:**
- Deterministic world generation with seeds
- Predefined templates for common scenarios
- Fluent API for readable test setup
- Support for terrain, obstacles, resources, spawn points

### 2. Agent Test Harness (`agent_harness.py`)

Behavioral contract testing for agent behaviors:

```python
# Example: Test that agent eventually moves
harness = AgentTestHarness(world)
agent = harness.add_agent("explorer", "test_agent", 5, 5)

harness.run_for_duration(10.0)

expectation = BehaviorExpectation(
    contract=BehaviorContract.EVENTUALLY_MOVES,
    timeout_seconds=10.0,
    tolerance=1.0
)

assert harness.verify_contract("test_agent", expectation)
```

**Contracts Available:**
- `EVENTUALLY_MOVES`: Agent moves from starting position
- `REACHES_TARGET`: Agent reaches specified target
- `AVOIDS_OBSTACLES`: Agent doesn't collide with obstacles
- `MAINTAINS_DISTANCE`: Agents maintain personal space
- `RESPONDS_TO_STIMULUS`: Agent reacts to environment changes

### 3. Test Server (`test_server.py`)

Lightweight in-process server for integration tests:

```python
# Example: Integration test with real server
async with IntegrationTestContext(config, world_builder) as ctx:
    client = await ctx.add_client("explorer", 5, 5)

    # Test real action processing
    action_id = await client.agent.action_manager.request_action(
        ActionType.MOVE_TO, {"target_x": 10, "target_y": 10}
    )

    # Verify server state
    pos = ctx.server.get_agent_position(client.agent_id)
    assert pos is not None
```

**Features:**
- Real game physics and validation
- In-process (no network overhead)
- Time acceleration for fast execution
- Automatic cleanup and lifecycle management

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests focusing on single components:

- **Behavioral Contracts**: Test agent behaviors through outcomes
- **Algorithm Testing**: Pathfinding, collision detection, game logic
- **Component Isolation**: Individual classes and functions
- **Property-Based**: Invariants that must always hold

**Example:**
```python
@pytest.mark.unit
async def test_agent_eventually_moves():
    world_builder = PredefinedWorlds.empty_arena(10)
    harness = create_movement_test(world_builder, "explorer")

    harness.run_for_duration(5.0)

    assert harness.verify_contract("test_agent",
        BehaviorExpectation(BehaviorContract.EVENTUALLY_MOVES, 5.0, 1.0))
```

### Integration Tests (`tests/integration/`)

Tests of component interactions with real implementations:

- **Action System**: Complete request-response flows
- **Client-Server**: Communication and state synchronization
- **Multi-Agent**: Agent interactions and collision avoidance
- **System Validation**: Server authority and movement rejection

**Example:**
```python
@pytest.mark.integration
async def test_movement_action_with_validation():
    async with IntegrationTestContext() as ctx:
        client = await ctx.add_client("player", 2, 2)

        await client.agent.action_manager.request_action(
            ActionType.MOVE_TO, {"target_x": 5, "target_y": 5}
        )

        # Verify real server processed action
        pos = ctx.server.get_agent_position(client.agent_id)
        assert pos != (2, 2)  # Agent moved
```

### Scenario Tests (`tests/scenarios/`)

End-to-end tests of realistic game scenarios:

- **Exploration Scenarios**: Complete exploration behaviors
- **Combat Scenarios**: Fighting and targeting systems
- **Resource Gathering**: Harvesting and inventory management
- **Multi-Player**: Complex multi-agent interactions

**Example:**
```python
@pytest.mark.scenario
async def test_explorer_discovers_complex_environment():
    world_builder = PredefinedWorlds.resource_gathering_area()

    async with IntegrationTestContext(world_builder=world_builder) as ctx:
        explorer = await ctx.add_client("explorer", 5, 5)

        # Run complete exploration scenario
        for _ in range(100):
            explorer.update(0.1)
            await asyncio.sleep(0.01)

        # Verify exploration outcomes
        assert explorer_made_progress()
        assert explorer_found_resources()
        assert explorer_avoided_obstacles()
```

## Key Principles

### 1. Behavioral Contracts Over Implementation Details

**❌ Bad (Implementation-focused):**
```python
assert agent.velocity_x > 0.01  # Testing implementation
assert len(agent.path) > 5      # Testing internal state
```

**✅ Good (Behavior-focused):**
```python
assert harness.verify_contract(agent, BehaviorContract.EVENTUALLY_MOVES)
assert harness.verify_contract(agent, BehaviorContract.REACHES_TARGET)
```

### 2. Deterministic and Reproducible

- Use seeds for random generation
- Predefined world templates
- Controlled time stepping
- Isolated test environments

### 3. Fast Execution

- Time acceleration for integration tests
- Minimal logging during tests
- In-process server (no network)
- Parallel test execution where possible

### 4. Realistic Testing

- Real game physics and collision detection
- Actual pathfinding algorithms
- Server authority and validation
- Proper action system integration

## Usage Examples

### Quick Start - Unit Test

```python
import pytest
from tests.framework.world_builder import PredefinedWorlds
from tests.framework.agent_harness import (
    create_movement_test, BehaviorContract, BehaviorExpectation
)

@pytest.mark.unit
async def test_my_behavior():
    # Arrange
    world_builder = PredefinedWorlds.empty_arena(15)
    harness = create_movement_test(world_builder, "explorer")

    # Act
    harness.run_for_duration(10.0)

    # Assert
    expectation = BehaviorExpectation(
        contract=BehaviorContract.EVENTUALLY_MOVES,
        timeout_seconds=10.0,
        tolerance=2.0
    )
    assert harness.verify_contract("test_agent", expectation)
```

### Integration Test

```python
@pytest.mark.integration
async def test_my_integration():
    config = ServerConfig(time_acceleration=5.0)
    world_builder = PredefinedWorlds.water_navigation_test()

    async with IntegrationTestContext(config, world_builder) as ctx:
        client = await ctx.add_client("explorer", 5, 10)

        # Test real action processing
        await client.agent.action_manager.request_action(...)

        # Verify server state
        assert ctx.server.get_agent_position(client.agent_id) == expected_pos
```

### Complex Scenario Test

```python
@pytest.mark.scenario
async def test_multi_agent_scenario():
    world_builder = (WorldBuilder(30, 30)
                    .add_multiple_rooms()
                    .add_resources()
                    .add_obstacles())

    async with IntegrationTestContext(world_builder=world_builder) as ctx:
        # Add multiple agents
        agents = []
        for i in range(5):
            agent = await ctx.add_client("explorer", start_positions[i])
            agents.append(agent)

        # Run scenario
        await run_scenario_for_duration(60.0, agents)

        # Verify scenario outcomes
        assert all_agents_completed_objectives(agents)
        assert no_agent_conflicts_occurred(agents)
```

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Only Fast Tests (Unit)
```bash
pytest tests/ --fast-only
```

### Run Only Integration Tests
```bash
pytest tests/ --integration-only
```

### Run By Category
```bash
pytest tests/ -m unit        # Unit tests only
pytest tests/ -m integration # Integration tests only
pytest tests/ -m scenario    # Scenario tests only
pytest tests/ -m pathfinding # Pathfinding-related tests
```

### Run Parallel (Fast)
```bash
pytest tests/ -n auto        # Use all CPU cores
```

### Performance Testing
```bash
pytest tests/ -m performance --capture=no
```

## Best Practices

### 1. Test Naming

- Use descriptive names that explain the behavior being tested
- Follow pattern: `test_[component]_[behavior]_[condition]`
- Examples:
  - `test_explorer_navigates_around_water_obstacles()`
  - `test_server_rejects_invalid_movement_requests()`
  - `test_multiple_agents_maintain_personal_space()`

### 2. Test Organization

- Group related tests in classes
- Use fixtures for common setup
- Keep tests independent (no shared state)
- Use parameterized tests for multiple scenarios

### 3. Assertions

- Focus on observable outcomes, not implementation
- Use meaningful assertion messages
- Test positive and negative cases
- Verify both success and failure paths

### 4. Performance

- Use time acceleration for faster execution
- Mock only external dependencies
- Use real components for core game logic
- Measure test execution time and optimize slow tests

## Migration Guide

To migrate existing tests to the new framework:

1. **Identify Test Type**: Determine if test is unit, integration, or scenario
2. **Replace Mocks**: Use real components where appropriate
3. **Use Contracts**: Replace implementation assertions with behavioral contracts
4. **Use Builders**: Replace manual world setup with WorldBuilder
5. **Add Proper Markers**: Ensure tests have correct pytest markers

### Example Migration

**Old Test (Over-mocked):**
```python
def test_explorer_movement():
    mock_world = MockWorld()
    mock_agent = MockAgent()
    mock_agent.update()
    assert mock_agent.x != initial_x  # Implementation detail
```

**New Test (Contract-based):**
```python
@pytest.mark.unit
async def test_explorer_movement():
    world_builder = PredefinedWorlds.empty_arena(10)
    harness = create_movement_test(world_builder, "explorer")

    harness.run_for_duration(5.0)

    assert harness.verify_contract("test_agent",
        BehaviorExpectation(BehaviorContract.EVENTUALLY_MOVES, 5.0))
```

## Extending the Framework

### Adding New Behavioral Contracts

1. Add contract to `BehaviorContract` enum
2. Implement verification logic in `AgentTestHarness._verify_*`
3. Add documentation and examples
4. Write tests for the contract itself

### Adding New World Templates

1. Add static method to `PredefinedWorlds`
2. Use deterministic seeds
3. Document the template's purpose
4. Provide usage examples

### Adding New Test Utilities

1. Add to appropriate framework module
2. Follow existing patterns and naming
3. Add comprehensive documentation
4. Include usage examples in tests
