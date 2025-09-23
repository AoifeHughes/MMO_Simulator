# Shared Module

Common utilities, constants, and components used by both client and server.

## Structure

```
shared/
├── constants.py      # Game configuration and constants
├── messages.py       # Network message protocol
├── math_utils.py     # Mathematical utilities
├── collision.py      # Collision detection system
└── pathfinding.py    # A* pathfinding algorithm
```

## Key Components

### Constants (`constants.py`)
- Game configuration values
- Network ports and timeouts
- Agent default values (speed, vision, health)
- World dimensions and tile sizes

### Messages (`messages.py`)
- Network message protocol definitions
- MessageType enum for all communication
- Message serialization/deserialization
- Protocol versioning support

### Math Utils (`math_utils.py`)
- Vector mathematics
- Angle normalization and calculations
- Distance and geometric utilities
- Cone and circle intersection tests

### Collision Detection (`collision.py`)
- Boundary collision detection
- Movement validation
- World bounds enforcement
- Obstacle avoidance utilities

### Pathfinding (`pathfinding.py`)
- A* algorithm implementation
- Path simplification and optimization
- Frontier exploration for mapping
- Waypoint navigation utilities

## Usage

Import shared utilities in both client and server code:

```python
from shared.constants import DEFAULT_AGENT_SPEED
from shared.messages import Message, MessageType
from shared.math_utils import normalize_angle, distance
from shared.pathfinding import Pathfinder
```

## Design Principles

- **Stateless**: No shared state between client and server
- **Pure Functions**: Most utilities are pure mathematical functions
- **Performance**: Optimized for real-time game loops
- **Consistency**: Ensures identical behavior on client and server
