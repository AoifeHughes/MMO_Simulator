# MMO Simulation System

A comprehensive, configuration-driven MMO simulation system with intelligent AI agents, server-side validation, and real-time visualization.

## 🚀 Quick Start

### One-Command Launch
Start the complete MMO simulation with a single command:

```bash
python start_mmo.py
```

This will:
- ✅ Start the server with configured world
- ✅ Spawn test agents automatically
- ✅ Launch real-time visualization
- ✅ Handle graceful shutdown

### Command Options

```bash
# Run specific test scenario
python start_mmo.py --scenario combat_test

# Override agent count
python start_mmo.py --agents 20

# Server only (no visualization)
python start_mmo.py --server-only

# Custom configuration directory
python start_mmo.py --config-dir ./my_configs

# Auto-shutdown after 5 minutes
python start_mmo.py --auto-shutdown 300

# See all options
python start_mmo.py --help
```

## 📁 Project Structure

```
MMO/
├── config/                      # Configuration files
│   ├── world_config.json       # World, NPCs, enemies, objects
│   ├── agent_config.json       # Agent templates and scenarios
│   └── server_config.json      # Server settings and validation
├── start_mmo.py                # 🎯 Main unified launcher
├── server/                     # Server-side components
│   ├── core/                   # Game state and world server
│   ├── validation/             # Movement and action validation
│   ├── agents/                 # Auto-spawning agent management
│   ├── network/                # Client connections
│   ├── api/                    # Action/query handlers
│   └── persistence/            # Data saving/loading
├── client/                     # Client-side agent framework
│   ├── core/                   # Agent client base classes
│   └── network/                # Server communication
├── examples/                   # Example agent implementations
├── visualization/              # Real-time visualization
└── shared/                     # Shared utilities and constants
```

## ⚙️ Configuration System

The MMO system is fully configurable through JSON files:

### World Configuration (`config/world_config.json`)
- **NPCs**: Merchants, guards, trainers with behaviors
- **Enemies**: Spawn areas, templates, AI behaviors
- **Terrain**: Movement modifiers, visibility effects
- **Objects**: Resource nodes, containers, portals

### Agent Configuration (`config/agent_config.json`)
- **Templates**: Explorer, Warrior, Merchant, Mage
- **Test Scenarios**: Pre-defined agent combinations
- **Spawn Settings**: Safe zones, spawn delays
- **Global Settings**: Max agents, auto-respawn

### Server Configuration (`config/server_config.json`)
- **Network**: Host, port, timeouts
- **Validation**: Movement limits, anti-cheat
- **Game Rules**: Combat, interaction, resources
- **Performance**: Tick rates, save intervals

## 🎮 Features

### Server-Side Authority
- ✅ **Movement Validation**: Speed limits, bounds checking, teleport detection
- ✅ **Action Validation**: Cooldowns, range checks, resource requirements
- ✅ **Anti-Cheat**: Rate limiting, sanity checks
- ✅ **Persistence**: Automatic save/restore of player data

### Intelligent Agent Management
- ✅ **Auto-Spawning**: Configurable agent templates and scenarios
- ✅ **Dynamic Scaling**: Automatic population balancing
- ✅ **Persistent Agents**: Resume from disconnection
- ✅ **Performance Tracking**: Action statistics and metrics

### Real-Time Visualization
- ✅ **Live World View**: Pan, zoom, entity selection
- ✅ **Agent Dashboard**: Connection status, template distribution
- ✅ **Performance Metrics**: FPS, memory, network statistics
- ✅ **Interactive Features**: Entity trails, selection highlights

### AI Agent Framework
- ✅ **Behavior Templates**: Pre-configured personalities and goals
- ✅ **Decision Making**: Autonomous exploration, combat, trading
- ✅ **Learning Capability**: Memory system and knowledge base
- ✅ **Multi-Agent Coordination**: Communication and cooperation

## 🧪 Testing

### Test the Configuration System
```bash
python test_config_system.py
```

### Run Individual Components
```bash
# Server only
python run_server.py

# Agents only (assumes server running)
python examples/simple_agent.py

# Visualization only
python visualization/live_monitor.py
```

### Test Scenarios
The system includes pre-configured test scenarios:

- **basic_exploration**: Mixed agents exploring and interacting
- **combat_test**: Combat-focused agents fighting enemies
- **mixed_gameplay**: Comprehensive gameplay test

## 🔧 Development

### Adding New Agent Types
1. Create template in `config/agent_config.json`
2. Implement agent class in `examples/`
3. Add to scenario configurations

### Customizing World
1. Edit `config/world_config.json`
2. Add new NPCs, enemies, or objects
3. Configure terrain and spawn areas

### Server Validation
1. Modify `config/server_config.json`
2. Adjust validation rules in `server/validation/`
3. Test with `test_config_system.py`

## 📊 Monitoring

### Web API
The server exposes a monitoring API on port 8080:
- `GET /status` - Server health check
- `GET /world` - Complete world state
- `GET /agents` - Agent management statistics

### Visualization Controls
- **Mouse**: Click entities to select, drag to pan
- **Keyboard**:
  - `SPACE` - Reset view
  - `+/-` - Zoom in/out
  - `ESC` - Exit

### Performance Metrics
- Server FPS and memory usage
- Active connections and message rates
- Agent statistics and distribution
- Historical performance charts

## 🚀 Architecture Highlights

### Separation of Concerns
- **Server**: Pure game logic, validation, world state
- **Agents**: Decision-making, goal planning, actions
- **Configuration**: All parameters externalized
- **Visualization**: Real-time monitoring and debugging

### Scalability Features
- Configurable agent limits and spawn rates
- Efficient spatial partitioning for entity queries
- Rate limiting and anti-cheat protection
- Modular component architecture

### Reliability Features
- Automatic data persistence and recovery
- Graceful handling of agent disconnections
- Comprehensive error handling and logging
- Configuration validation and fallbacks

## 📈 Future Enhancements

The system is designed for extensibility:

- **Machine Learning**: Agent behavior optimization
- **Advanced AI**: Cooperative strategies, emergent behaviors
- **World Generation**: Procedural content creation
- **Multiplayer**: Human player integration
- **Analytics**: Detailed behavior analysis and reporting

## 🤝 Contributing

1. Test your changes with `test_config_system.py`
2. Ensure configuration backward compatibility
3. Update documentation for new features
4. Follow the existing code patterns and structure

## 📄 License

This project is designed for educational and research purposes in AI agent simulation and MMO game mechanics.