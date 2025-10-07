Getting Started Tutorial
========================

Welcome to the MMO Simulator! This step-by-step tutorial will guide you through creating your first simulation from scratch. By the end, you'll understand how to set up agents, configure the simulation, and analyze the results.

What You'll Build
-----------------

In this tutorial, you'll create a small simulation with:

- A procedurally-generated world
- 5 agents with different personalities and classes
- 3 hostile NPCs (enemies)
- Resource gathering and exploration
- Combat interactions
- Database logging for analysis

Prerequisites
-------------

Make sure you have:

- Python 3.8 or higher
- MMO Simulator installed (``pip install -r requirements.txt``)
- Basic Python knowledge

Step 1: Understanding the Simulation Flow
------------------------------------------

Before we start coding, let's understand how a simulation works:

.. mermaid::

   graph TB
       A[Create Simulation Config] --> B[Initialize Simulation]
       B --> C[Generate World]
       C --> D[Create & Add Agents]
       D --> E[Create & Add NPCs]
       E --> F{Run Simulation Loop}
       F -->|Each Tick| G[Agent Perception]
       G --> H[Agent Decision]
       H --> I[Execute Actions]
       I --> J[Update Systems]
       J --> K[Log to Database]
       K -->|Continue?| F
       F -->|Complete| L[Analyze Results]

The simulation runs in discrete time steps called **ticks**. Each tick represents a unit of simulation time where:

1. Agents perceive their surroundings
2. Agents decide what to do based on their goals
3. Actions are executed
4. Game systems (trading, respawns) update
5. Data is logged to the database

Step 2: Create Your First Simulation
-------------------------------------

Create a new file called ``my_first_simulation.py``:

.. code-block:: python

   #!/usr/bin/env python3
   """
   My First MMO Simulation

   A simple simulation demonstrating basic agent behavior,
   exploration, gathering, and combat.
   """

   import os
   import sys

   # Add simulation framework to path
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

   from simulation_framework.src.core.simulation import Simulation
   from simulation_framework.src.core.config import SimulationConfig
   from simulation_framework.src.entities.agent import create_agent_with_archetype
   from simulation_framework.src.entities.npc import create_basic_goblin, create_forest_wolf
   from simulation_framework.src.ai.goal import GatherResourceGoal, ExploreGoal

   # Create simulation configuration
   config = SimulationConfig(
       world_width=40,              # 40x40 world
       world_height=40,
       world_seed=12345,            # Reproducible world
       max_ticks=600,               # Run for 600 ticks (10 minutes)
       database_path="my_simulation.db",
       save_interval=60,            # Save every 60 ticks (1 minute)
       enable_visualizer=True,      # Enable pygame visualization
       visualizer_width=1200,
       visualizer_height=800,
       tick_rate=10,                # 10 ticks per second
   )

   # Initialize simulation
   sim = Simulation(config)
   sim.initialize_simulation(
       name="My First Simulation",
       description="Learning the basics of agent behavior and simulation"
   )

   print("Simulation initialized successfully!")
   print(f"Simulation ID: {sim.simulation_id}")
   print(f"World size: {config.world_width}x{config.world_height}")

Step 3: Understanding Agent Personalities
------------------------------------------

Agents in MMO Simulator have **personalities** that influence their behavior. Let's understand the personality traits:

.. mermaid::

   graph LR
       P[Agent Personality] --> C[Curiosity]
       P --> B[Bravery]
       P --> S[Sociability]
       P --> G[Greed]
       P --> PAT[Patience]
       P --> A[Aggression]
       P --> I[Industriousness]
       P --> CAU[Caution]

       C -->|High| EX[Explores More]
       B -->|High| CO[Engages Combat]
       S -->|High| TR[Trades Often]
       G -->|High| GA[Gathers Resources]
       I -->|High| CR[Crafts Items]

Each personality trait ranges from 0.0 to 1.0:

- **Curiosity** (0.0-1.0): How much the agent explores unknown areas
- **Bravery** (0.0-1.0): Willingness to engage in combat
- **Sociability** (0.0-1.0): Interest in trading with others
- **Greed** (0.0-1.0): Focus on accumulating resources
- **Patience** (0.0-1.0): How long they stick with goals
- **Aggression** (0.0-1.0): Tendency to initiate combat
- **Industriousness** (0.0-1.0): Focus on gathering/crafting
- **Caution** (0.0-1.0): Risk aversion in dangerous situations

Step 4: Create Your Agents
---------------------------

Now let's add agents with different personality archetypes. Add this code to your file:

.. code-block:: python

   # Create agents with different archetypes

   # 1. Explorer - loves discovering new areas
   explorer = create_agent_with_archetype(
       position=(10, 10),
       archetype="explorer",
       name="Explorer Alice"
   )
   explorer.current_goals.append(ExploreGoal(priority=8))
   sim.add_agent(explorer)
   print(f"Added {explorer.name} - Class: {explorer.character_class.name}")

   # 2. Warrior - brave and aggressive, seeks combat
   warrior = create_agent_with_archetype(
       position=(30, 10),
       archetype="warrior",
       name="Warrior Bob"
   )
   warrior.current_goals.append(ExploreGoal(priority=6))
   sim.add_agent(warrior)
   print(f"Added {warrior.name} - Class: {warrior.character_class.name}")

   # 3. Gatherer - industrious, collects resources
   gatherer = create_agent_with_archetype(
       position=(10, 30),
       archetype="crafter",
       name="Gatherer Carol"
   )
   gatherer.current_goals.append(GatherResourceGoal("wood", target_amount=15, priority=7))
   sim.add_agent(gatherer)
   print(f"Added {gatherer.name} - Class: {gatherer.character_class.name}")

   # 4. Trader - social, likes to trade with others
   trader = create_agent_with_archetype(
       position=(30, 30),
       archetype="trader",
       name="Trader Diana"
   )
   trader.current_goals.append(GatherResourceGoal("herbs", target_amount=10, priority=5))
   sim.add_agent(trader)
   print(f"Added {trader.name} - Class: {trader.character_class.name}")

   # 5. Hermit - cautious, avoids danger
   hermit = create_agent_with_archetype(
       position=(20, 20),
       archetype="hermit",
       name="Hermit Eric"
   )
   hermit.current_goals.append(GatherResourceGoal("berries", target_amount=20, priority=6))
   sim.add_agent(hermit)
   print(f"Added {hermit.name} - Class: {hermit.character_class.name}")

Understanding Agent Archetypes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The framework provides several pre-defined archetypes:

- **explorer**: High curiosity, moderate bravery, low sociability
- **warrior**: High bravery & aggression, low caution
- **trader**: High sociability & greed, moderate patience
- **crafter**: High patience & industriousness, low aggression
- **hermit**: Low sociability & aggression, high caution
- **bandit**: High aggression & greed, low caution

Step 5: Add NPCs (Enemies)
---------------------------

NPCs provide challenges for your agents. Add these NPCs:

.. code-block:: python

   # Add hostile NPCs

   # Goblins - moderate difficulty enemies
   goblin1 = create_basic_goblin((15, 15))
   goblin1.name = "Goblin Raider"
   sim.add_npc(goblin1)
   print(f"Added {goblin1.name} - HP: {goblin1.stats.max_health}, ATK: {goblin1.stats.attack_power}")

   # Wolves - fast, aggressive enemies
   wolf1 = create_forest_wolf((25, 25))
   wolf1.name = "Forest Wolf"
   sim.add_npc(wolf1)
   print(f"Added {wolf1.name} - HP: {wolf1.stats.max_health}, ATK: {wolf1.stats.attack_power}")

   wolf2 = create_forest_wolf((35, 15))
   wolf2.name = "Alpha Wolf"
   sim.add_npc(wolf2)
   print(f"Added {wolf2.name} - HP: {wolf2.stats.max_health}, ATK: {wolf2.stats.attack_power}")

NPC Behavior
~~~~~~~~~~~~

NPCs have simple behavior patterns:

- **Aggro Range**: Distance at which they notice and attack agents
- **Tether Range**: Maximum distance from spawn point
- **Loot Tables**: Items dropped when defeated
- **Respawn**: Automatically respawn after being defeated

Step 6: Understanding the Agent AI Loop
----------------------------------------

Before running the simulation, let's understand how agents make decisions:

.. mermaid::

   graph TB
       A[Start Tick] --> B[Perceive Environment]
       B --> C{Scan for Entities}
       C --> D[Update Fog of War]
       C --> E[Detect Resources]
       C --> F[Find Enemies/Threats]

       D --> G[Decision Phase]
       E --> G
       F --> G

       G --> H{Evaluate Goals}
       H --> I[Calculate Utility]
       I --> J{Select Best Goal}

       J --> K[Explore Goal?]
       J --> L[Gather Goal?]
       J --> M[Attack Goal?]
       J --> N[Trade Goal?]

       K --> O[Generate Action]
       L --> O
       M --> O
       N --> O

       O --> P[Execute Action]
       P --> Q{Action Complete?}
       Q -->|No| R[Continue Next Tick]
       Q -->|Yes| S[Update Goal Progress]
       S --> T[End Tick]

Each agent independently:

1. **Perceives** - Updates their knowledge of the world
2. **Decides** - Selects the best goal based on personality and situation
3. **Acts** - Executes actions to achieve their current goal

Step 7: Run the Simulation
---------------------------

Add the code to run your simulation:

.. code-block:: python

   # Run the simulation with visualization
   print("\n" + "="*60)
   print("STARTING SIMULATION")
   print("="*60)
   print("Controls:")
   print("  • Left Click + Drag: Pan map")
   print("  • Mouse Wheel: Zoom in/out")
   print("  • Click Agent: View details")
   print("  • ESC: Deselect agent")
   print("  • Close window: Stop simulation")
   print("="*60 + "\n")

   try:
       # Run with visualization
       sim.run_with_visualizer(num_ticks=600)
   except ImportError:
       # Fall back to headless if pygame not available
       print("Visualization not available, running headless...")
       sim.run(num_ticks=600)

   # Print final statistics
   stats = sim.get_statistics()
   print("\n" + "="*60)
   print("SIMULATION COMPLETE")
   print("="*60)
   print(f"Final Tick: {stats['current_tick']}")
   print(f"Agents: {stats['active_agents']}/{stats['total_agents']} alive")
   print(f"NPCs: {stats['active_npcs']}/{stats['total_npcs']} alive")
   print(f"Average tick time: {stats['average_tick_time']:.4f}s")
   print(f"Database: {os.path.abspath(config.database_path)}")
   print("="*60)

Complete Program
~~~~~~~~~~~~~~~~

Save your complete ``my_first_simulation.py`` file with all the code above, then run it:

.. code-block:: bash

   python my_first_simulation.py

You should see:

1. Initialization messages showing agents and NPCs being created
2. A pygame window with the simulation visualization
3. Agents moving around, gathering resources, and fighting NPCs
4. Final statistics when complete

Step 8: Analyzing the Results
------------------------------

After the simulation completes, you'll have a database file ``my_simulation.db``. Let's analyze it!

Using SQLite Directly
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   sqlite3 my_simulation.db

Try these queries:

.. code-block:: sql

   -- See all tables
   .tables

   -- View agent activity summary
   SELECT
       agent_id,
       action_type,
       COUNT(*) as count,
       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
   FROM action_logs
   GROUP BY agent_id, action_type
   ORDER BY agent_id, count DESC;

   -- View combat events
   SELECT
       tick,
       attacker_id,
       target_id,
       damage_dealt,
       was_critical,
       target_died
   FROM combat_logs
   ORDER BY tick;

   -- Agent positions over time
   SELECT
       tick,
       name,
       position_x,
       position_y,
       health,
       max_health
   FROM agent_snapshots
   WHERE agent_id = 1  -- Change to different agent IDs
   ORDER BY tick;

Using the Analysis Script
~~~~~~~~~~~~~~~~~~~~~~~~~~

MMO Simulator includes a built-in analysis script:

.. code-block:: bash

   python analyze_simulation_results.py my_simulation.db

This will show:

- Total actions performed
- Action success rates
- Combat statistics (damage, kills, deaths)
- Agent efficiency metrics
- Resource gathering trends

Step 9: Customizing Agent Behavior
-----------------------------------

Now let's create agents with custom personalities and goals!

Custom Personality Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from simulation_framework.src.ai.personality import Personality
   from simulation_framework.src.entities.agent import Agent
   from simulation_framework.src.ai.character_class import get_character_class

   # Create a custom personality
   brave_explorer = Personality(
       curiosity=0.9,      # Very curious
       bravery=0.8,        # Very brave
       sociability=0.3,    # Mostly solo
       greed=0.4,          # Moderate resource focus
       patience=0.6,       # Moderate patience
       aggression=0.5,     # Moderate aggression
       industriousness=0.5,  # Moderate gathering
       caution=0.2         # Low caution
   )

   # Create agent with custom personality
   custom_agent = Agent(
       position=(20, 15),
       name="Custom Explorer",
       personality=brave_explorer,
       character_class=get_character_class("Explorer")
   )

   # Add specific goals
   from simulation_framework.src.ai.goal import ExploreGoal, AttackEnemyGoal

   custom_agent.current_goals.append(ExploreGoal(priority=9))
   custom_agent.current_goals.append(AttackEnemyGoal(priority=7))

   sim.add_agent(custom_agent)

Character Classes
~~~~~~~~~~~~~~~~~

Available character classes and their strengths:

=============  ==================  ====================  ==================
Class          Primary Strength    Starting Equipment    Best For
=============  ==================  ====================  ==================
Warrior        Combat              Iron Sword, Shield    Fighting NPCs
Hunter         Gathering           Bow, Axe, Fishing Rod Resource collection
Mage           Magic               Staff                 Special abilities
Alchemist      Crafting            Herbs, Potion Kit     Making items
Blacksmith     Crafting            Hammer, Pickaxe       Tool/weapon making
Trader         Trading             Gold, Ledger          Economy interactions
Explorer       Exploration         Map, Compass          Discovery
Farmer         Gathering           Hoe, Seeds            Food production
=============  ==================  ====================  ==================

Step 10: Advanced Configuration
--------------------------------

Customize your simulation further with config options:

.. code-block:: python

   config = SimulationConfig(
       # World settings
       world_width=80,
       world_height=80,
       world_seed=42,  # Use same seed for reproducible worlds

       # Simulation limits
       max_ticks=2000,
       tick_rate=15,  # Faster ticks per second

       # Database and logging
       database_path="advanced_sim.db",
       save_interval=100,  # Save less frequently
       analytics_interval=50,

       # Agent vision
       default_agent_vision_range=10,  # Agents see further
       fog_of_war_enabled=True,

       # Visualization
       enable_visualizer=True,
       visualizer_width=1600,
       visualizer_height=1000,
       visualizer_tile_size=20,

       # Economy
       starting_gold=100,
       trade_cooldown=5,  # Faster trading

       # Performance
       enable_pathfinding_cache=True,
       max_pathfinding_distance=50,
   )

Common Configuration Scenarios
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Large World Exploration**

.. code-block:: python

   config = SimulationConfig(
       world_width=100,
       world_height=100,
       default_agent_vision_range=12,
       max_ticks=3000
   )

**Combat Arena**

.. code-block:: python

   config = SimulationConfig(
       world_width=40,
       world_height=40,
       tick_rate=20,  # Fast-paced action
       max_ticks=1000
   )

**Economic Simulation**

.. code-block:: python

   config = SimulationConfig(
       starting_gold=500,
       trade_cooldown=2,  # Frequent trading
       max_ticks=5000,
       analytics_interval=25  # More frequent analytics
   )

Next Steps
----------

Congratulations! You've created your first MMO Simulator simulation. Here's what to explore next:

1. **Learn More About Agents**

   - :doc:`custom-agents` - Create specialized agent types
   - :doc:`../user-guide/creating-agents` - Detailed agent creation guide

2. **Understand the World**

   - :doc:`../user-guide/world-generation` - World generation details
   - :doc:`../getting-started/basic-concepts` - Core concepts

3. **Analyze Results**

   - :doc:`analyzing-results` - Advanced data analysis techniques
   - :doc:`../architecture/database-schema` - Database structure

4. **Dive Deeper**

   - :doc:`custom-actions` - Create new action types
   - :doc:`../architecture/simulation-loop` - Understanding the simulation loop
   - :doc:`../api/core` - API reference

Troubleshooting
---------------

Simulation runs but nothing happens?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Check that agents have goals assigned: ``agent.current_goals.append(...)``
- Verify agents are spawned in passable terrain (not in water or mountains)
- Make sure NPCs are within agent vision range

Visualization window doesn't open?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Install pygame: ``pip install pygame>=2.0.0``
- Try running headless: Set ``enable_visualizer=False`` in config

Database file is empty?
~~~~~~~~~~~~~~~~~~~~~~~~

- Ensure ``save_interval`` is less than ``max_ticks``
- Check that simulation runs for at least one save interval
- Verify database path is writable

Agents aren't gathering resources?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Resources must match terrain type (wood in forests, stone in mountains)
- Agents need appropriate tools (axe for wood, pickaxe for stone)
- Check agent has a ``GatherResourceGoal`` with the right resource type

Further Reading
---------------

- **GitHub Repository**: https://github.com/AoifeHughes/MMO_Simulator
- **Full Documentation**: https://aoifehughes.github.io/mmo-simulator/
- **Report Issues**: https://github.com/AoifeHughes/MMO_Simulator/issues

Tips for Success
-----------------

- Start small (5-10 agents) and scale up
- Use ``world_seed`` for reproducible experiments
- Save frequently during long simulations
- Use the visualizer to debug agent behavior
- Analyze the database after each run to understand patterns
- Experiment with different personality combinations
- Try different world sizes to see how it affects behavior

Happy simulating! 🎮
