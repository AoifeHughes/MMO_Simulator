# Server Module

The server module contains the game server implementation, world simulation, and server-side game logic.

## Structure

```
server/
├── server.py            # Main game server with TCP/UDP networking
├── game_loop.py         # Core game loop and timing
├── world.py             # World state management and agent simulation
└── visualization/       # Optional integrated visualization
    ├── __init__.py
    └── integrated_visualizer.py
```

## Key Components

### GameServer (`server.py`)
- TCP/UDP networking for client connections
- Client session management and authentication
- Message routing and protocol handling
- Connection lifecycle management

### GameLoop (`game_loop.py`)
- Fixed timestep game loop at 30 TPS (ticks per second)
- World state updates and physics simulation
- Agent behavior processing
- Network message broadcasting

### World (`world.py`)
- World state management and persistence
- Agent spawning, respawning, and lifecycle
- Combat system with damage and health
- Movement validation and boundary enforcement
- Vision and entity discovery system

## Network Protocol

- **TCP**: Reliable messaging for important game events
  - Agent actions, combat, spawning, world state
- **UDP**: Fast updates for real-time data
  - Movement updates, position synchronization

## Game Loop

The server runs at a fixed 30 TPS (33ms per tick):
1. Process incoming client messages
2. Update agent AI and physics
3. Handle combat and interactions
4. Broadcast world state to clients
5. Send individual entity updates

## Features

- **Multi-client Support**: Handle dozens of concurrent connections
- **Real-time Combat**: Damage, health, death, and respawn systems
- **Vision System**: Agents only see entities within vision cones
- **Movement Validation**: Server-authoritative position validation
- **Scalable Architecture**: Async/await for high concurrency
