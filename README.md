# MMO Simulator

A multi-agent simulation framework for studying emergent behavior and economic patterns in autonomous agent systems.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-sphinx-blue.svg)](https://aoifehughes.github.io/mmo-simulator/)

## Overview

MMO Simulator is a research framework inspired by games like Dwarf Fortress, designed to simulate autonomous agents that explore, gather resources, craft items, fight NPCs, and trade with each other in procedurally-generated 2D worlds.

### Key Features

- 🗺️ **Procedural World Generation**: Perlin noise-based terrain with forests, mountains, water, and resources
- 🤖 **Autonomous Agents**: Personality-driven AI with utility-based goal selection
- ⚔️ **Combat System**: Agents fight hostile NPCs, collect loot, and respawn
- 🛠️ **Crafting & Gathering**: Resource extraction and item creation from recipes
- 💰 **Emergent Economy**: Non-blocking trading system and market dynamics
- 📊 **Comprehensive Analytics**: All data logged to SQLite for research analysis
- 🎮 **Real-time Visualization**: Optional Pygame-based visualization

## Quick Start

### Installation

```bash
git clone https://github.com/AoifeHughes/MMO_Simulator.git
cd MMO_Simulator
pip install -r requirements.txt
```

### Run Your First Simulation

```bash
python examples/complex_simulation.py --agents 10 --npcs 5 --ticks 180
```

This will:
- Generate a 60x60 world
- Spawn 10 agents with different personalities
- Spawn 5 hostile NPCs
- Run for 180 ticks (~3 simulation minutes)
- Display real-time visualization
- Save all data to `complex_simulation.db`

## Documentation

**Full documentation available at: https://aoifehughes.github.io/mmo-simulator/**

- [Installation Guide](https://aoifehughes.github.io/mmo-simulator/getting-started/installation.html)
- [Quick Start](https://aoifehughes.github.io/mmo-simulator/getting-started/quickstart.html)
- [User Guide](https://aoifehughes.github.io/mmo-simulator/user-guide/simulation-config.html)
- [API Reference](https://aoifehughes.github.io/mmo-simulator/api/core.html)
- [Tutorials](https://aoifehughes.github.io/mmo-simulator/tutorials/custom-agents.html)

## Project Structure

```
MMO_Simulator/
├── simulation_framework/src/
│   ├── core/           # Simulation orchestration, world management
│   ├── entities/       # Agents, NPCs, stats, inventory
│   ├── actions/        # Movement, combat, gathering, crafting
│   ├── ai/             # Personality, goals, decision-making
│   ├── systems/        # Fog of war, trading, combat, respawns
│   ├── world/          # Terrain generation, tiles, resources
│   ├── items/          # Items, weapons, tools, loot tables
│   └── database/       # Persistence, logging, analytics
├── examples/           # Example simulations
├── tests/              # Unit and integration tests
├── docs/               # Sphinx documentation
└── visualizer/         # Pygame visualization
```

## Research Applications

This framework is designed for research into:

- **Emergent Economics**: Market prices, trade networks, resource distribution
- **Behavioral Adaptation**: How agents with different personalities specialize over time
- **Social Dynamics**: Relationship patterns and cooperation strategies
- **Resource Management**: Efficiency of resource discovery and utilization

## Example: Creating a Custom Simulation

```python
from simulation_framework.src.core.simulation import Simulation
from simulation_framework.src.core.config import SimulationConfig
from simulation_framework.src.entities.agent import create_random_agent

# Configure simulation
config = SimulationConfig(
    world_width=40,
    world_height=40,
    max_ticks=500,
    database_path="my_sim.db"
)

# Create and initialize
sim = Simulation(config)
sim.initialize_simulation("My Research Simulation")

# Add agents
for i in range(10):
    agent = create_random_agent((5 + i*3, 5 + i*3))
    sim.add_agent(agent)

# Run simulation
sim.run(num_ticks=500)

# Analyze results
stats = sim.get_statistics()
print(f"Completed: {stats['current_tick']} ticks")
```

## Analyzing Results

All simulation data is logged to SQLite:

```bash
sqlite3 simulation.db

# Example queries
SELECT action_type, COUNT(*) FROM action_logs GROUP BY action_type;
SELECT * FROM combat_logs WHERE target_died = 1;
SELECT * FROM trade_logs WHERE completed = 1;
```

Or use the built-in analysis script:

```bash
python analyze_simulation_results.py simulation.db
```

## Development

### Running Tests

```bash
pytest
```

### Building Documentation

```bash
cd docs
pip install -r requirements.txt
make html
```

### Contributing

Contributions are welcome! Please check the [documentation](https://aoifehughes.github.io/mmo-simulator/) for architecture details and contribution guidelines.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use this framework in your research, please cite:

```bibtex
@software{mmo_simulator,
  author = {Hughes, Aoife},
  title = {MMO Simulator: A Multi-Agent Framework for Emergent Behavior Research},
  year = {2024},
  url = {https://github.com/AoifeHughes/MMO_Simulator}
}
```

## Acknowledgments

Inspired by games like Dwarf Fortress and research in multi-agent systems, emergent behavior, and agent-based computational economics.

---

**📚 [Read the full documentation](https://aoifehughes.github.io/mmo-simulator/)** | **🐛 [Report issues](https://github.com/AoifeHughes/MMO_Simulator/issues)** | **⭐ [Star this repo](https://github.com/AoifeHughes/MMO_Simulator)**
