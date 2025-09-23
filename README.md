# MMO Simulator

A multi-agent simulation environment featuring intelligent AI agents with behavior trees, pathfinding, combat, and exploration capabilities.

## Features

- **Intelligent AI Agents**: Player, Enemy, NPC, and Explorer agents with sophisticated behavior trees
- **Real-time Combat**: Dynamic combat system with health, damage, and respawn mechanics
- **Advanced Pathfinding**: A* pathfinding with obstacle avoidance and frontier exploration
- **Multiple Scenarios**: Pre-built scenarios for testing different agent behaviors
- **Visual Interface**: Real-time visualization with zoom, pan, and debug modes
- **Network Architecture**: TCP/UDP client-server architecture for scalable multiplayer

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run a basic combat scenario
python main.py --scenario basic_combat

# List available scenarios
python main.py --list-scenarios

# Run without visualization (headless)
python main.py --scenario basic_combat --no-viz
```

## Available Scenarios

- **basic_combat**: Intense combat between players and enemies
- **exploration_demo**: Explorer agents mapping the world with different strategies
- **peaceful_village**: Peaceful NPCs wandering around
- **pathfinding_demo**: Demonstrates pathfinding with predetermined waypoints
- **simple_duel**: 1v1 combat scenario

## Project Structure

```
├── client/           # AI agent implementations and behavior trees
├── server/           # Game server and world simulation
├── scenarios/        # Pre-configured simulation scenarios
├── shared/           # Shared utilities and constants
├── visualizer/       # Real-time visualization renderer
├── world/           # World map, tiles, and terrain system
├── tests/           # Test suite
└── examples/        # Example scripts and demos
```

## Controls

- **D**: Toggle debug mode
- **V**: Toggle vision cones
- **F**: Toggle follow mode
- **+/-**: Zoom in/out
- **Mouse**: Pan camera (right/middle click)
- **ESC**: Quit

## Architecture

The simulator uses a client-server architecture where each AI agent runs as a separate client, enabling distributed simulation and easy scaling.

## Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_scenarios.py
pytest tests/test_pathfinding.py
```

See [TESTING.md](TESTING.md) for detailed testing information.
