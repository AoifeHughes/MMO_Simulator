# Client Module

The client module contains AI agent implementations, behavior trees, and client-side game logic.

## Structure

```
client/
├── agent.py              # Base agent class with pathfinding and behavior
├── client.py             # Game client for connecting to server
├── agent_map.py          # Agent personal mapping system
├── agent_types/          # Specific agent implementations
│   ├── player.py         # Player agent with combat behavior
│   ├── enemy.py          # Enemy agent with hunting behavior
│   ├── npc.py            # NPC agent with social behavior
│   ├── explorer.py       # Explorer agent with mapping behavior
│   └── pathfinding_test.py # Test agent for pathfinding demos
└── behavior_tree/        # Behavior tree system
    ├── tree.py           # Core behavior tree implementation
    ├── tree_configs.py   # Pre-configured trees for each agent type
    └── nodes/            # Behavior tree node types
        ├── base.py       # Base node classes
        ├── composite.py  # Selector, sequence, parallel nodes
        ├── decorator.py  # Timer, cooldown decorators
        ├── condition.py  # Condition checking nodes
        ├── action.py     # Basic movement and interaction actions
        └── combat_action.py # Combat-specific actions
```

## Key Components

### BaseAgent (`agent.py`)
- Core agent functionality with movement, pathfinding, and vision
- Intention cooldown system (3-second minimum between major behavior changes)
- Personal mapping system for world discovery
- Behavior tree integration

### GameClient (`client.py`)
- Handles TCP/UDP communication with server
- Manages agent state synchronization
- Processes world updates and visible entity information

### Behavior Trees
- Hierarchical AI system for complex decision making
- Cooldown and timer decorators prevent jittering
- Specialized action nodes for movement, combat, and exploration
- Pre-configured trees for each agent type

## Agent Types

- **Player**: Combat-focused with patrol and enemy engagement
- **Enemy**: Aggressive hunter that seeks and attacks players
- **NPC**: Social agent that reacts to nearby players
- **Explorer**: Mapping agent that discovers unknown terrain
- **PathfindingTest**: Demonstrates pathfinding with fixed waypoints

## Behavior Tree Features

- **Stability**: Cooldown systems prevent rapid behavior changes
- **Modularity**: Reusable nodes for different behaviors
- **Debugging**: Comprehensive logging and debug information
- **Performance**: Efficient update cycles with minimal overhead
