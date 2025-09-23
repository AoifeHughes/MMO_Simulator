# MMO Simulator Testing Framework

The MMO simulator now includes a comprehensive pytest testing framework for validating agent behavior and system performance.

## Installation Requirements

```bash
pip install pytest pytest-asyncio
```

## Test Structure

The test suite is organized into several categories:

### Agent Behavior Tests
- `test_explorer_agents.py` - Tests for explorer agent behavior patterns
- `test_npc_agents.py` - Tests for NPC wandering and idle behavior
- `test_enemy_agents.py` - Tests for enemy patrol, chase, and attack behavior

### Integration Tests
- `test_scenarios.py` - End-to-end scenario testing
- `test_network.py` - Network communication and synchronization tests
- `test_debug_output.py` - Debug information and metrics collection tests

## Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Run only agent behavior tests
python -m pytest tests/ -m agent -v

# Run only integration tests
python -m pytest tests/ -m integration -v

# Run only network tests
python -m pytest tests/ -m network -v

# Skip slow tests
python -m pytest tests/ -m "not slow" -v
```

### Run Individual Test Files
```bash
# Test explorer agents only
python -m pytest tests/test_explorer_agents.py -v

# Test with detailed output
python -m pytest tests/test_explorer_agents.py -v -s
```

## Debug Information

The testing framework provides extensive debug information:

### Agent Tracking
- Position tracking over time
- Movement distance calculations
- Area coverage analysis
- Speed and directional bias metrics

### Behavior Metrics
- State transition tracking
- Interaction recording between agents
- Performance monitoring
- Efficiency calculations

### Debug Output Example
```bash
python -m pytest tests/test_explorer_agents.py::TestExplorerAgents::test_explorer_movement -v -s
```

This will show detailed logs including:
- Server startup/shutdown
- Agent connections
- Position updates
- Movement analysis
- Test assertions

## Custom Assertions

The framework includes specialized assertions for different agent types:

### AgentAssertions
- `assert_agent_moved()` - Verify minimum movement distance
- `assert_agent_explored_area()` - Check area coverage
- `assert_state_transitions()` - Validate state changes
- `assert_performance_acceptable()` - Check system performance

### ExplorerAssertions
- `assert_exploration_efficiency()` - Measure exploration effectiveness
- `assert_spiral_pattern()` - Validate spiral exploration
- `assert_frontier_exploration()` - Check frontier-based exploration

### NPCAssertions
- `assert_wandering_behavior()` - Verify NPC stays near home
- `assert_idle_wander_cycle()` - Check state transitions

### EnemyAssertions
- `assert_patrol_behavior()` - Validate patrol patterns
- `assert_chase_behavior()` - Check player detection and chase
- `assert_attack_behavior()` - Verify combat engagement

## Metrics Collection

The BehaviorMetrics class provides comprehensive analysis:

```python
# Example usage in tests
metrics = BehaviorMetrics()

# Record agent positions over time
metrics.record_agent_position(agent_id, agent_type, position, timestamp)

# Record state transitions
metrics.record_state_transition(agent_id, new_state, timestamp)

# Record interactions between agents
metrics.record_interaction(agent1_id, agent2_id, interaction_type, timestamp)

# Generate analysis reports
explorer_analysis = metrics.analyze_explorer_behavior()
npc_analysis = metrics.analyze_npc_behavior()
enemy_analysis = metrics.analyze_enemy_behavior()

# Generate comprehensive report
full_report = metrics.generate_report()
```

## Configuration

Test configuration is managed through `pytest.ini`:

```ini
[tool:pytest]
testpaths = tests
asyncio_mode = auto
timeout = 30
log_cli = true
log_cli_level = INFO
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    agent: marks tests for specific agent behavior
    network: marks tests for network functionality
    timeout: marks tests with timeout requirements
```

## Performance Testing

The framework includes performance monitoring:

- Tick rate measurement
- Agent count scaling tests
- Network latency simulation
- Memory and CPU usage tracking (when available)
- Bandwidth efficiency analysis

Example performance test:
```bash
python -m pytest tests/test_scenarios.py::TestScenarios::test_scenario_performance_stress -v -s
```

## Adding New Tests

To add new agent behavior tests:

1. Create test methods in the appropriate test file
2. Use the provided fixtures: `game_server`, `agent_clients`, `agent_tracker`, `behavior_metrics`
3. Apply appropriate markers: `@pytest.mark.agent`, `@pytest.mark.timeout(seconds)`
4. Use custom assertions for behavior validation
5. Record metrics for analysis

Example test structure:
```python
@pytest.mark.asyncio
@pytest.mark.agent
@pytest.mark.timeout(20)
async def test_new_behavior(self, game_server, agent_clients, agent_tracker, behavior_metrics):
    # Create agent
    agent = await agent_clients("explorer")
    assert agent is not None

    # Run behavior test
    await asyncio.sleep(15)

    # Validate behavior
    AgentAssertions.assert_agent_moved(agent_tracker, agent.agent_id, min_distance=3.0)

    # Print debug info
    agent_tracker.print_debug_info()
```

## Test Results

Tests provide detailed information about:
- Agent spawn success/failure
- Movement patterns and distances
- State transitions and timing
- Interaction frequencies
- Network synchronization quality
- Performance metrics
- Coverage and efficiency statistics

This comprehensive testing framework ensures that all agent behaviors work as expected and provides detailed debugging information to identify and fix issues.
