# Multi-Agent Simulation - Implementation Checklist

## Project Summary
We're building a multi-agent simulation framework in Python, similar to Dwarf Fortress, where autonomous agents explore, gather resources, craft items, fight NPCs, and trade with each other in a procedurally-generated 2D world. The goal is to research emergent economic behavior and long-term adaptation patterns - observing how agents with different personalities and classes (warriors, hunters, alchemists, etc.) naturally specialize, form trade networks, and develop survival strategies over thousands of simulation ticks.
The system uses an object-oriented, component-based architecture where everything (actions, items, entities) inherits from extensible base classes, allowing easy addition of new content through database definitions rather than code changes. Agents have internal "fog of war" maps that fill as they explore, personality traits that drive decision-making, and a non-blocking trading system where they advertise offers while pursuing other goals. We'll validate the mechanics using small test scenarios (5-10 agents/NPCs on tiny maps) before scaling to the target of ~100 agents in a full simulation, with all data logged to SQLite for post-analysis of economic trends, resource distribution, and behavioral patterns.

## Project Structure

```
simulation_framework/
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── simulation.py          # Main simulation loop
│   │   ├── world.py                # World and terrain management
│   │   ├── time_manager.py         # Tick management
│   │   └── config.py               # Global configuration
│   │
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── base.py                 # Entity base class
│   │   ├── agent.py                # Agent class
│   │   ├── npc.py                  # NPC class
│   │   ├── stats.py                # Stats container (health, stamina, etc)
│   │   └── inventory.py            # Inventory management
│   │
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── base.py                 # Action base class
│   │   ├── movement.py             # Move, Pathfind actions
│   │   ├── combat.py               # Melee, Ranged, Magic attacks
│   │   ├── gathering.py            # Fish, Mine, Forage, Woodcut
│   │   ├── crafting.py             # Craft action
│   │   └── trading.py              # Trade action
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── personality.py          # Personality class
│   │   ├── character_class.py      # Character classes
│   │   ├── goal.py                 # Goal base class and implementations
│   │   ├── decision_maker.py       # Utility-based AI system
│   │   └── npc_controller.py       # NPC behavior controller
│   │
│   ├── items/
│   │   ├── __init__.py
│   │   ├── item.py                 # Item base class
│   │   ├── weapon.py               # Weapon subclass
│   │   ├── tool.py                 # Tool subclass
│   │   ├── consumable.py           # Consumable subclass
│   │   ├── loot_table.py           # Loot generation
│   │   └── recipe.py               # Crafting recipes
│   │
│   ├── world/
│   │   ├── __init__.py
│   │   ├── terrain.py              # Terrain types and properties
│   │   ├── generator.py            # Perlin noise world generation
│   │   ├── tile.py                 # Individual tile class
│   │   └── spatial_hash.py         # Spatial partitioning for performance
│   │
│   ├── systems/
│   │   ├── __init__.py
│   │   ├── trade_board.py          # Non-blocking trade system
│   │   ├── respawn_manager.py      # Death and respawn handling
│   │   ├── fog_of_war.py           # Agent internal maps
│   │   ├── pathfinding.py          # A* pathfinding wrapper
│   │   └── combat_resolver.py      # Combat calculation logic
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db_manager.py           # Database connection and saves
│   │   ├── schema.py               # Table definitions
│   │   ├── item_loader.py          # Load items from DB
│   │   └── event_logger.py         # Event logging for analytics
│   │
│   └── utils/
│       ├── __init__.py
│       ├── math_utils.py           # Distance, vectors, etc.
│       ├── random_utils.py         # Seeded random, weighted choice
│       └── serialization.py        # Save/load helpers
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_entities.py
│   │   ├── test_actions.py
│   │   ├── test_items.py
│   │   ├── test_pathfinding.py
│   │   ├── test_combat.py
│   │   ├── test_gathering.py
│   │   ├── test_trading.py
│   │   └── test_world_gen.py
│   │
│   ├── integration/
│   │   ├── test_agent_lifecycle.py
│   │   ├── test_npc_behavior.py
│   │   ├── test_economy.py
│   │   └── test_combat_scenarios.py
│   │
│   ├── scenarios/
│   │   ├── small_world_10x10.py    # Tiny test world
│   │   ├── combat_arena.py         # 5 agents vs 5 NPCs
│   │   ├── gathering_test.py       # Resource gathering validation
│   │   ├── trading_village.py      # Trade system test
│   │   └── exploration_test.py     # Fog of war validation
│   │
│   └── fixtures/
│       ├── test_items.json
│       ├── test_recipes.json
│       └── test_world.pkl
│
├── data/
│   ├── game.db                     # Main SQLite database
│   ├── items/                      # Item definitions
│   │   └── base_items.json
│   ├── recipes/                    # Crafting recipes
│   │   └── base_recipes.json
│   └── terrain/                    # Terrain configurations
│       └── terrain_config.json
│
├── scripts/
│   ├── init_database.py            # Initialize fresh database
│   ├── run_scenario.py             # Run specific test scenario
│   └── analyze_logs.py             # Parse event logs for research
│
├── requirements.txt
├── pytest.ini
├── README.md
└── setup.py
```

---

## Core OOP Architecture Principles

### 1. Entity Hierarchy
```python
Entity (ABC)
├── Agent
│   └── implements: perceive(), decide(), act()
└── NPC
    └── implements: update_routine(), check_tether()
```

### 2. Action Pattern
```python
Action (ABC)
├── can_execute(actor, context) -> bool
├── execute(actor, context) -> ActionResult
├── get_duration() -> int
└── get_cost() -> ResourceCost

# All actions inherit and implement these
MovementAction, CombatAction, GatherAction, CraftAction, TradeAction
```

### 3. Component Composition
```python
# Entities have components, not deep inheritance
Agent:
    - stats: Stats
    - inventory: Inventory
    - personality: Personality
    - character_class: CharacterClass
    - known_map: FogOfWar
    - goal_queue: PriorityQueue[Goal]
```

---

## Implementation Checklist

### Phase 0: Project Setup ⚙️
- [ ] Create project structure as outlined above
- [ ] Set up virtual environment
- [ ] Install dependencies:
  ```
  pytest==7.4.0
  pytest-cov==4.1.0
  opensimplex==0.4.5.1
  pathfinding==1.0.7
  numpy==1.24.3
  ```
- [ ] Initialize git repository with `.gitignore`
- [ ] Create `pytest.ini` with test discovery settings
- [ ] Set up pre-commit hooks for linting (optional: `black`, `flake8`)

---

### Phase 1: Foundation - World & Entities 🌍

#### Task 1.1: World Generation
**Files**: `world/generator.py`, `world/terrain.py`, `world/tile.py`

- [ ] Implement `TerrainType` enum (WATER, GRASS, FOREST, MOUNTAIN, DESERT)
- [ ] Create `TerrainProperties` dataclass with passable, fishable, mineable, harvestable
- [ ] Implement `Tile` class with:
  - [ ] `terrain_type`, `resources`, `spawn_zones`
  - [ ] `can_pass()`, `can_gather()`, `get_resources()`
- [ ] Implement `WorldGenerator`:
  - [ ] `generate_perlin_noise(width, height, octaves, seed)`
  - [ ] `map_noise_to_terrain(noise_array) -> 2D Tile array`
  - [ ] Add moisture and temperature layers for biome diversity
- [ ] Create `World` class:
  - [ ] `get_tile(x, y)`, `is_valid_position(x, y)`, `is_passable(x, y)`
  - [ ] `get_neighbors(x, y)`, `get_entities_at(x, y)`

**Tests**:
- [ ] `test_world_gen.py`:
  - [ ] Test deterministic generation with same seed
  - [ ] Verify all tiles have valid terrain types
  - [ ] Check terrain distribution (at least 10% of each type)
  - [ ] Test boundary conditions (edges of map)
  - [ ] Verify resource assignment to appropriate tiles

**Acceptance Criteria**: Generate 10x10 and 100x100 worlds, visualize terrain types, confirm passability logic works

---

#### Task 1.2: Base Entity System
**Files**: `entities/base.py`, `entities/stats.py`, `entities/inventory.py`

- [ ] Implement `Stats` class:
  - [ ] `health`, `max_health`, `stamina`, `max_stamina`, `magic`, `max_magic`
  - [ ] `take_damage(amount)`, `heal(amount)`, `restore_stamina(amount)`
  - [ ] `is_alive()`, `get_health_percentage()`
- [ ] Implement `Inventory` class:
  - [ ] `items: dict[Item, quantity]`
  - [ ] `add_item(item, qty)`, `remove_item(item, qty)`, `has_item(item, qty)`
  - [ ] `get_equipped_weapon()`, `get_equipped_tool(tool_type)`
  - [ ] `to_dict()`, `from_dict()` for serialization
- [ ] Implement `Entity` abstract base class:
  - [ ] `id`, `position`, `stats`, `inventory`, `status_effects`
  - [ ] `move_to(x, y)`, `distance_to(other)`, `can_see(other, range)`
  - [ ] Abstract methods: `update(world)`, `on_death()`

**Tests**:
- [ ] `test_entities.py`:
  - [ ] Test stats damage/healing/death
  - [ ] Test inventory add/remove/has operations
  - [ ] Test inventory overflow behavior
  - [ ] Test entity movement
  - [ ] Test distance calculations

**Acceptance Criteria**: Create mock entities, modify stats, verify death triggers, manage inventory

---

#### Task 1.3: Items System
**Files**: `items/item.py`, `items/weapon.py`, `items/tool.py`, `items/consumable.py`, `database/item_loader.py`

- [ ] Create database schema in `database/schema.py`:
  ```sql
  CREATE TABLE item_definitions (
      id INTEGER PRIMARY KEY,
      name TEXT UNIQUE,
      type TEXT,  -- weapon, tool, consumable, material
      properties JSON
  )
  ```
- [ ] Implement `Item` base class:
  - [ ] `from_database(item_id)`, `from_dict(data)`
  - [ ] `get_property(key, default)`, `can_stack()`
- [ ] Implement `Weapon(Item)`:
  - [ ] `get_damage()`, `get_attack_type()`, `get_range()`
- [ ] Implement `Tool(Item)`:
  - [ ] `get_tool_type()`, `get_durability()`, `use()` (reduces durability)
- [ ] Implement `Consumable(Item)`:
  - [ ] `get_effect()`, `consume(entity)` (apply effects)
- [ ] Create `ItemLoader`:
  - [ ] `load_all_items()`, `get_item_by_id()`, `get_item_by_name()`
  - [ ] Cache loaded items

**Tests**:
- [ ] `test_items.py`:
  - [ ] Load items from test JSON file
  - [ ] Verify weapon damage calculations
  - [ ] Test tool durability degradation
  - [ ] Test consumable effects on entity stats
  - [ ] Test item stacking rules

**Acceptance Criteria**: Define 10 test items in JSON, load them, create instances, use them

---

### Phase 2: Actions & Pathfinding 🎯

#### Task 2.1: Action Base System
**Files**: `actions/base.py`

- [ ] Implement `ActionResult` dataclass:
  - [ ] `success: bool`, `message: str`, `events: list[Event]`
- [ ] Implement `ResourceCost` dataclass:
  - [ ] `stamina`, `magic`, `health`, `items: dict[Item, quantity]`
- [ ] Implement `Action` abstract base class:
  - [ ] `can_execute(actor, world) -> bool`
  - [ ] `execute(actor, world) -> ActionResult`
  - [ ] `get_duration() -> int` (in ticks)
  - [ ] `get_cost() -> ResourceCost`
  - [ ] `__repr__()` for debugging

**Tests**:
- [ ] `test_actions.py`:
  - [ ] Create mock action subclass
  - [ ] Test can_execute preconditions
  - [ ] Verify resource costs are applied
  - [ ] Test action result propagation

**Acceptance Criteria**: Define 2-3 simple test actions, execute them, verify state changes

---

#### Task 2.2: Movement & Pathfinding
**Files**: `actions/movement.py`, `systems/pathfinding.py`

- [ ] Implement `Pathfinder`:
  - [ ] `find_path(start, goal, world, known_map=None) -> list[(x,y)]`
  - [ ] Use A* from `pathfinding` library
  - [ ] Handle passability checks
  - [ ] Cache paths (optional optimization)
- [ ] Implement `MoveAction`:
  - [ ] Single tile movement
  - [ ] Check destination is passable and adjacent
  - [ ] Cost: 1 stamina, duration: 1 tick
- [ ] Implement `PathfindAction`:
  - [ ] High-level action that chains MoveActions
  - [ ] Handles multi-step movement
  - [ ] Updates path if blocked

**Tests**:
- [ ] `test_pathfinding.py`:
  - [ ] Test A* on simple grid
  - [ ] Verify path avoids impassable terrain
  - [ ] Test pathfinding with obstacles
  - [ ] Test no path exists scenario
  - [ ] Test adjacent movement (should be direct)

**Acceptance Criteria**: Agent pathfinds across 10x10 world, avoids water/mountains

---

#### Task 2.3: Gathering Actions
**Files**: `actions/gathering.py`

- [ ] Implement `GatherAction` base class:
  - [ ] `resource_type`, `required_tool`, `required_terrain`, `skill_name`
  - [ ] `can_execute()`: check tool, terrain, stamina
  - [ ] `execute()`: roll for yield, add to inventory, gain XP
- [ ] Implement specific gatherers:
  - [ ] `FishAction` (requires fishing_rod, water_adjacent)
  - [ ] `MineAction` (requires pickaxe, mountain terrain)
  - [ ] `ForageAction` (requires none, forest/grassland)
  - [ ] `WoodcutAction` (requires axe, forest)
- [ ] Implement yield calculation:
  - [ ] Base yield + skill modifier + random variance
  - [ ] Rare item drops (low probability bonus items)

**Tests**:
- [ ] `test_gathering.py`:
  - [ ] Test gathering without required tool (should fail)
  - [ ] Test gathering on wrong terrain (should fail)
  - [ ] Test successful gathering adds items to inventory
  - [ ] Test skill XP gain
  - [ ] Verify yield variance (run 100 times, check distribution)

**Acceptance Criteria**: Agent successfully gathers wood, fish, ore in appropriate locations

---

### Phase 3: Combat System ⚔️

#### Task 3.1: Combat Actions
**Files**: `actions/combat.py`, `systems/combat_resolver.py`

- [ ] Implement `CombatResolver`:
  - [ ] `calculate_damage(attacker, defender, attack_type)`
  - [ ] Apply armor, resistances, weaknesses
  - [ ] Critical hit calculation (optional)
- [ ] Implement `CombatAction` base class:
  - [ ] `damage_type`, `range`, `stamina_cost`, `magic_cost`
  - [ ] `can_execute()`: check range, resources, target alive
  - [ ] `execute()`: calculate damage, apply to target, check death
- [ ] Implement attack types:
  - [ ] `MeleeAttack` (range 1, requires melee weapon)
  - [ ] `RangedAttack` (range 10, requires bow/crossbow)
  - [ ] `MagicAttack` (range 15, costs magic, no weapon needed)

**Tests**:
- [ ] `test_combat.py`:
  - [ ] Test melee attack between entities
  - [ ] Test ranged attack at various distances
  - [ ] Test magic attack (verify magic cost)
  - [ ] Test attack out of range (should fail)
  - [ ] Test damage calculation formulas
  - [ ] Test entity death after damage

**Acceptance Criteria**: Two entities can fight, health decreases, death triggers correctly

---

#### Task 3.2: Loot System
**Files**: `items/loot_table.py`, `entities/npc.py`

- [ ] Implement `LootTable`:
  - [ ] `items: list[tuple[Item, probability, (min_qty, max_qty)]]`
  - [ ] `generate_loot() -> list[tuple[Item, qty]]`
  - [ ] Use weighted random for drops
- [ ] Extend `NPC` class:
  - [ ] `loot_table: LootTable`
  - [ ] `on_death(killer)`:
    - [ ] Generate loot
    - [ ] Transfer to killer's inventory
    - [ ] Register with RespawnManager
- [ ] Create loot tables in database/JSON

**Tests**:
- [ ] `test_loot.py` (in `test_combat.py`):
  - [ ] Generate 1000 loot drops, verify probability distribution
  - [ ] Test NPC death transfers loot to killer
  - [ ] Test inventory overflow (if killer inventory full)

**Acceptance Criteria**: Kill NPC, receive loot, NPC marked for respawn

---

### Phase 4: Agent AI 🧠

#### Task 4.1: Personality & Character Classes
**Files**: `ai/personality.py`, `ai/character_class.py`

- [ ] Implement `Personality` dataclass:
  - [ ] `curiosity`, `bravery`, `sociability`, `greed`, `patience` (all 0-1 floats)
  - [ ] `randomize()` class method for procedural generation
- [ ] Implement `CharacterClass`:
  - [ ] `name`, `skill_affinities`, `starting_equipment`, `preferred_actions`
  - [ ] Predefined classes: WARRIOR, MAGE, HUNTER, ALCHEMIST, BLACKSMITH
  - [ ] `get_skill_modifier(skill_name) -> float`
- [ ] Implement `Agent` class (extending Entity):
  - [ ] `personality: Personality`, `character_class: CharacterClass`
  - [ ] `skills: dict[str, int]`, `known_map: FogOfWar`
  - [ ] `goal_queue: PriorityQueue[Goal]`

**Tests**:
- [ ] `test_ai.py`:
  - [ ] Create agents with different personalities
  - [ ] Verify character class skill modifiers
  - [ ] Test skill leveling

**Acceptance Criteria**: Create 5 agents with different personalities/classes

---

#### Task 4.2: Goal System
**Files**: `ai/goal.py`, `ai/decision_maker.py`

- [ ] Implement `Goal` abstract base class:
  - [ ] `priority: int`, `is_complete() -> bool`, `get_next_action() -> Action`
- [ ] Implement concrete goals:
  - [ ] `ExploreGoal` (driven by curiosity)
  - [ ] `GatherResourceGoal(resource_type)` (go to resource, gather)
  - [ ] `CraftItemGoal(recipe)` (gather ingredients, craft)
  - [ ] `AttackEnemyGoal(target)` (pursue and attack)
  - [ ] `TradeGoal(trade_offer)` (pathfind to trader, execute trade)
- [ ] Implement `DecisionMaker`:
  - [ ] `evaluate_goals(agent, world) -> list[tuple[Goal, utility]]`
  - [ ] Utility based on personality, class, current needs
  - [ ] `select_goal() -> Goal` (highest utility or weighted random)

**Tests**:
- [ ] `test_goals.py`:
  - [ ] Test goal completion detection
  - [ ] Test goal generates appropriate actions
  - [ ] Test decision maker selects goals based on personality
  - [ ] Curious agent should explore more than cautious agent

**Acceptance Criteria**: Agent autonomously selects and pursues goals

---

#### Task 4.3: Agent Perception & Decision Loop
**Files**: `entities/agent.py`

- [ ] Implement `Agent.perceive(world)`:
  - [ ] Update `known_map` with visible tiles
  - [ ] Detect nearby entities, resources, NPCs
  - [ ] Check trade_board for matching offers
- [ ] Implement `Agent.decide()`:
  - [ ] If current goal complete, select new goal
  - [ ] Decision maker evaluates options
  - [ ] Push goal to queue
- [ ] Implement `Agent.act()`:
  - [ ] Pop action from current goal
  - [ ] Execute action if possible
  - [ ] Handle action failure (replan)

**Tests**:
- [ ] `test_agent_lifecycle.py`:
  - [ ] Agent explores unknown map
  - [ ] Agent gathers resources when found
  - [ ] Agent crafts when has ingredients
  - [ ] Agent switches goals based on needs

**Acceptance Criteria**: Agent acts autonomously for 1000 ticks without crashing

---

### Phase 5: Systems Integration 🔗

#### Task 5.1: Fog of War / Internal Maps
**Files**: `systems/fog_of_war.py`

- [ ] Implement `MapTile`:
  - [ ] `terrain_type`, `last_updated`, `known_resources`, `known_npcs`
- [ ] Implement `FogOfWar`:
  - [ ] `tiles: 2D array of MapTile or None`
  - [ ] `reveal_area(center, radius, world)`
  - [ ] `is_explored(x, y)`, `can_pathfind_to(destination)`
  - [ ] `get_frontier_tiles() -> list[(x,y)]` (edge of known area)
- [ ] Integrate with Agent perception

**Tests**:
- [ ] `test_fog_of_war.py`:
  - [ ] Newly created agent has no explored tiles
  - [ ] Agent reveals tiles as it moves
  - [ ] Agent can pathfind within known area
  - [ ] Agent cannot pathfind to unexplored destination

**Acceptance Criteria**: Agent explores map incrementally, pathfinding respects fog of war

---

#### Task 5.2: Trading System
**Files**: `systems/trade_board.py`, `actions/trading.py`

- [ ] Implement `TradeOffer`:
  - [ ] `agent_id`, `offering`, `requesting`, `location`, `expiration_time`
- [ ] Implement `TradeBoard`:
  - [ ] `active_offers: dict[agent_id, TradeOffer]`
  - [ ] `post_offer(offer)`, `remove_offer(agent_id)`
  - [ ] `find_matches(agent) -> list[TradeOffer]`
- [ ] Implement `TradeAction`:
  - [ ] `can_execute()`: both agents in range, both have items
  - [ ] `execute()`: atomic swap, remove offer from board
  - [ ] Duration: 3 ticks

**Tests**:
- [ ] `test_trading.py`:
  - [ ] Agent posts trade offer
  - [ ] Another agent finds matching offer
  - [ ] Trade executes successfully
  - [ ] Items transferred correctly
  - [ ] Offer removed from board after trade

**Acceptance Criteria**: 2 agents autonomously find each other and trade

---

#### Task 5.3: Respawn Manager
**Files**: `systems/respawn_manager.py`

- [ ] Implement `RespawnManager`:
  - [ ] `pending_respawns: list[tuple[Entity, respawn_tick]]`
  - [ ] `register_death(entity, delay)`
  - [ ] `update(current_tick)`: respawn ready entities
- [ ] Implement `Entity.respawn()`:
  - [ ] Agents: reset to spawn, full health, clear inventory (or keep some?)
  - [ ] NPCs: reset to spawn, full health
- [ ] Integrate with combat system

**Tests**:
- [ ] `test_respawn.py`:
  - [ ] Entity dies, registered with manager
  - [ ] Entity respawns after delay
  - [ ] Stats reset correctly

**Acceptance Criteria**: Agent/NPC dies, respawns after configured delay

---

#### Task 5.4: NPC Behavior System
**Files**: `ai/npc_controller.py`, `entities/npc.py`

- [ ] Implement `Routine`:
  - [ ] `schedule: list[tuple[time_start, time_end, behavior_name]]`
  - [ ] `get_behavior(current_time) -> str`
- [ ] Implement `NPCController`:
  - [ ] `update(npc, current_time, world) -> Action`
  - [ ] Check tether radius (if exceeded, return to spawn)
  - [ ] Check aggro (if aggressive and player nearby, attack)
  - [ ] Execute routine behavior
- [ ] Implement NPC behaviors:
  - [ ] `wander()`, `idle()`, `patrol(waypoints)`, `flee()`

**Tests**:
- [ ] `test_npc_behavior.py`:
  - [ ] NPC follows routine schedule
  - [ ] NPC returns when exceeding tether
  - [ ] Aggressive NPC attacks nearby agent
  - [ ] Passive NPC ignores agent unless attacked

**Acceptance Criteria**: NPCs act according to type, don't wander off map

---

### Phase 6: Database & Persistence 💾

#### Task 6.1: Database Schema & Manager
**Files**: `database/db_manager.py`, `database/schema.py`, `database/event_logger.py`

- [ ] Define full SQLite schema in `schema.py`:
  - [ ] `item_definitions`, `recipe_definitions`
  - [ ] `agents`, `npcs`, `world_state`
  - [ ] `event_log` (for analytics)
- [ ] Implement `DatabaseManager`:
  - [ ] `initialize_db()` (create tables)
  - [ ] `save_simulation(simulation)` (periodic save)
  - [ ] `load_simulation() -> Simulation`
  - [ ] Batch operations for performance
- [ ] Implement `EventLogger`:
  - [ ] `event_queue: list[Event]`
  - [ ] `log_event(event_type, agent_id, data)`
  - [ ] `flush_to_db()` (bulk insert)

**Tests**:
- [ ] `test_database.py`:
  - [ ] Initialize fresh database
  - [ ] Save simulation state
  - [ ] Load simulation state (verify identical)
  - [ ] Log 1000 events, verify all persisted

**Acceptance Criteria**: Simulation can be saved and resumed from database

---

#### Task 6.2: Crafting System
**Files**: `actions/crafting.py`, `items/recipe.py`, `database/item_loader.py`

- [ ] Implement `Recipe`:
  - [ ] `output_item`, `required_items`, `required_skill`, `crafting_time`
  - [ ] `from_database(recipe_id)`, `load_all_recipes()`
- [ ] Implement `CraftAction`:
  - [ ] `can_execute()`: check ingredients, skill level, crafting station
  - [ ] `execute()`: consume ingredients, add output item, gain XP
  - [ ] Multi-tick action (duration based on recipe)
- [ ] Create recipe definitions in JSON/database

**Tests**:
- [ ] `test_crafting.py`:
  - [ ] Load recipes from database
  - [ ] Craft simple item (wood -> planks)
  - [ ] Craft complex item (ore + wood -> sword)
  - [ ] Test insufficient ingredients (should fail)
  - [ ] Test insufficient skill level (should fail)

**Acceptance Criteria**: Agent gathers resources, crafts tools/weapons

---

### Phase 7: Main Simulation Loop 🎮

#### Task 7.1: Simulation Class
**Files**: `core/simulation.py`, `core/time_manager.py`

- [ ] Implement `TimeManager`:
  - [ ] Track current tick
  - [ ] Convert ticks to in-game time (days, hours)
- [ ] Implement `Simulation`:
  - [ ] `__init__()`: load world, agents, NPCs, systems
  - [ ] `step()`:
    1. Update NPC controllers
    2. Agent perception
    3. Agent decision-making
    4. Execute all actions
    5. Update respawns
    6. Periodic database save
  - [ ] `run(num_ticks)`, `run_until(condition)`
- [ ] Add configuration system (tick rate, save interval, etc.)

**Tests**:
- [ ] `test_simulation.py`:
  - [ ] Initialize simulation
  - [ ] Run 100 ticks without errors
  - [ ] Verify agents act each tick
  - [ ] Verify time progresses correctly

**Acceptance Criteria**: Simulation runs 10,000 ticks with 10 agents + 10 NPCs

---

### Phase 8: Test Scenarios 🧪

#### Task 8.1: Small World Scenario (10x10)
**Files**: `tests/scenarios/small_world_10x10.py`

- [ ] Create 10x10 world with varied terrain
- [ ] Spawn 5 agents with different classes
- [ ] Spawn 5 NPCs (2 aggressive, 3 passive)
- [ ] Place resources strategically
- [ ] Run 1000 ticks
- [ ] Assertions:
  - [ ] All agents explore at least 50% of map
  - [ ] At least 2 combat encounters occur
  - [ ] At least 5 gathering actions successful
  - [ ] At least 1 crafting action successful

**Acceptance Criteria**: Scenario passes all assertions

---

#### Task 8.2: Combat Arena Scenario
**Files**: `tests/scenarios/combat_arena.py`

- [ ] Create 20x20 arena
- [ ] Spawn 5 warrior agents vs 5 aggressive NPCs
- [ ] No resources, only combat
- [ ] Run until one side eliminated or 2000 ticks
- [ ] Assertions:
  - [ ] At least 3 entities die
  - [ ] Combat damage calculated correctly
  - [ ] Loot drops occur
  - [ ] Respawns trigger

**Acceptance Criteria**: Combat resolves correctly, loot distributed

---

#### Task 8.3: Trading Village Scenario
**Files**: `tests/scenarios/trading_village.py`

- [ ] Create 30x30 world
- [ ] Spawn 10 agents (diverse classes)
- [ ] Abundant resources
- [ ] Run 5000 ticks
- [ ] Assertions:
  - [ ] At least 10 trade offers posted
  - [ ] At least 3 successful trades
  - [ ] Agents specialize (hunters gather more food, etc.)
  - [ ] Agents craft items from gathered resources

**Acceptance Criteria**: Economy emerges, agents trade autonomously

---

#### Task 8.4: Exploration Test Scenario
**Files**: `tests/scenarios/exploration_test.py`

- [ ] Create 50x50 world
- [ ] Spawn 1 agent with high curiosity
- [ ] No NPCs
- [ ] Run 3000 ticks
- [ ] Assertions:
  - [ ] Agent explores > 80% of map
  - [ ] Fog of war updates correctly
  - [ ] Agent pathfinds using known map
  - [ ] Agent doesn't revisit tiles unnecessarily

**Acceptance Criteria**: Agent explores efficiently, fog of war works

---

### Phase 9: Performance & Optimization ⚡

#### Task 9.1: Spatial Partitioning
**Files**: `world/spatial_hash.py`

- [ ] Implement `SpatialHash`:
  - [ ] Grid-based spatial partitioning
  - [ ] `insert(entity)`, `remove(entity)`, `update(entity)`
  - [ ] `query_range(x, y, radius) -> list[Entity]`
- [ ] Integrate with World class
- [ ] Use for entity proximity queries (combat, perception)

**Tests**:
- [ ] `test_spatial_hash.py`:
  - [ ] Insert 100 entities
  - [ ] Query range returns correct entities
  - [ ] Update entity position

**Acceptance Criteria**: Query 100 entities in range < 1ms

---

#### Task 9.2: Pathfinding Optimization
**Files**: `systems/pathfinding.py`

- [ ] Implement path caching:
  - [ ] Cache last N paths per agent
  - [ ] Invalidate if world changes
- [ ] Hierarchical pathfinding (optional):
  - [ ] Divide world into regions
  - [ ] Plan high-level path, then detailed

**Tests**:
- [ ] Benchmark pathfinding 1000 times
- [ ] Verify cache hit rate > 50%

**Acceptance Criteria**: Pathfinding averages < 5ms per agent

---

### Phase 10: Analytics & Tooling 📊

#### Task 10.1: Event Analysis Scripts
**Files**: `scripts/analyze_logs.py`

- [ ] Parse event_log from database
- [ ] Generate reports:
  - [ ] Combat statistics (kills, deaths, by class)
  - [ ] Trade network graph
  - [ ] Resource gathering rates
  - [ ] Agent specialization metrics
  - [ ] Wealth distribution (Gini coefficient)
- [ ] Export to CSV/JSON for external analysis

**Acceptance Criteria**: Run simulation for 10k ticks, generate meaningful insights

---

#### Task 10.2: Visualization (Optional but Recommended)
**Files**: `visualization/renderer.py`

- [ ] Simple Pygame or Matplotlib visualization
- [ ] Display:
  - [ ] Terrain map
  - [ ] Agent positions
  - [ ] NPC positions
  - [ ] Fog of war overlay
- [ ] Real-time or post-simulation playback

**Acceptance Criteria**: Visual confirmation of agent behavior

---

## Testing Strategy

### Unit Tests (tests/unit/)
- **Coverage Target**: 80%+
- **Focus**: Individual classes and methods in isolation
- **Use mocks** for dependencies (world, database, etc.)
- **Fast execution**: entire suite < 10 seconds

### Integration Tests (tests/integration/)
- **Coverage Target**: Key workflows
- **Focus**: Multi-component interactions
- **Examples**: Agent lifecycle, combat flow, trading flow
- **Execution time**: < 60 seconds

### Scenario Tests (tests/scenarios/)
- **Coverage Target**: End-to-end behaviors
- **Focus**: Emergent properties, long-running simulations
- **Examples**: Economy emergence, exploration patterns
- **Execution time**: Can be long (minutes), run less frequently

### Test Data Management
- Use `fixtures/` for reusable test data
- Seed random generators for deterministic tests
- Separate test database from production database

---

## Development Workflow

1. **For each task**:
   - [ ] Create feature branch
   - [ ] Implement code
   - [ ] Write tests FIRST (TDD approach encouraged)
   - [ ] Ensure tests pass
   - [ ] Run full test suite
   - [ ] Merge to main

2. **Daily checklist**:
   - [ ] Run `pytest tests/unit` (should be fast)
   - [ ] Run `pytest tests/integration` (weekly is fine)
   - [ ] Run at least one scenario test (to validate integration)

3. **Before declaring phase complete**:
   - [ ] All tests in phase pass
   - [ ] Code coverage meets target
   - [ ] Scenario test demonstrates functionality
   - [ ] Update documentation/README

---

## Success Metrics

### Technical Milestones
- [ ] Phase 1-3 complete: Basic simulation runs
- [ ] Phase 4-6 complete: Agents act autonomously
- [ ] Phase 7-8 complete: All systems integrated
- [ ] Phase 9 complete: Supports 100+ entities efficiently

### Research Milestones
- [ ] Agents exhibit specialization
- [ ] Emergent economy forms
- [ ] Trade networks develop
- [ ] Long-term behavior patterns observable (10k+ ticks)

---

## Final Validation Checklist

Before considering the project "complete":
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] All scenario tests pass
- [ ] 100 agents + 100 NPCs simulation runs for 10,000 ticks without errors
- [ ] Simulation can be saved and resumed
- [ ] Event logs contain analyzable data
- [ ] At least 3 research questions can be answered from logged data
- [ ] Documentation includes: setup guide, architecture overview, extending the system


---

## Notes for Implementation

- **Start simple**: Don't implement all features at once. Get basic version working first.
- **Test early, test often**: Catch bugs when they're introduced, not 3 phases later.
- **Use type hints**: `from __future__ import annotations` for better IDE support
- **Document as you go**: Docstrings for all public methods
- **Commit frequently**: Small, atomic commits make debugging easier
- **Profile before optimizing**: Use `cProfile` to find actual bottlenecks

Good luck! This is a well-scoped, achievable project with clear deliverables.
