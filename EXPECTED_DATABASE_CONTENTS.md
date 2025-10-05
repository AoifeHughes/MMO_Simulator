# Expected Database Contents After 3 Minutes (180 Ticks)

## Test Configuration
- **Duration**: 180 ticks (3 simulated minutes)
- **Agents**: 18 specialized agents
- **NPCs**: 12 hostile creatures
- **World**: 60x60 grid
- **Logging Interval**: Every 60 ticks (1 minute)

## Expected Database Tables

### 1. `simulation_runs`
**Expected Rows**: 1

**Contents**:
- Simulation metadata (name, description)
- World configuration (60x60, seed)
- Start and end timestamps
- Total ticks: 180
- Total agents: 18

---

### 2. `agent_snapshots`
**Expected Rows**: ~90-108 snapshots

**Calculation**:
- 18 agents + 12 NPCs = 30 entities
- Snapshots at tick 60, 120, 180 = 3 snapshots
- 30 entities × 3 snapshots = **90 snapshots minimum**
- May be more if NPCs respawn and get counted

**Contents per snapshot**:
- Entity ID, name, position (x, y)
- Health, stamina (current and max)
- Character class or NPC type
- Personality traits (for agents)
- Skills dictionary
- Current goals list
- Inventory item count

---

### 3. `world_snapshots`
**Expected Rows**: 3 snapshots

**Timing**: Ticks 60, 120, 180

**Contents per snapshot**:
- Total entities count
- Active agents count
- Active NPCs count
- Market prices dictionary (wood, stone, berries, etc.)
- World events array

---

### 4. `action_logs`
**Expected Rows**: 200-500+ actions

**Action Types We Expect to See**:

1. **Movement Actions** (50-100 entries)
   - `PathfindAction`: Agents moving to resources/enemies
   - `WanderAction`: Exploration movement
   - Success rate: ~80-90%

2. **Gathering Actions** (40-80 entries)
   - `WoodcutAction`: Wood gathering (Alice, Noah)
   - `MineAction`: Stone/ore gathering (Bob, Emma)
   - `ForageAction`: Berries/herbs (Carol, Olivia, Quinn)
   - `FishAction`: Fish gathering (Dave, Riley)
   - Success rate: ~60-80% (depends on resource availability)

3. **Combat Actions** (30-60 entries)
   - `MeleeAttack`: Primary combat action
   - `FleeAction`: When agents retreat
   - Success rate: ~50-70% for attacks

4. **Crafting Actions** (5-15 entries)
   - `CraftAction`: Emma crafting Iron Sword
   - `CraftAction`: Frank crafting Health Potions
   - Success rate: ~40-60% (depends on having materials)

5. **Respawn Events** (5-20 entries)
   - `Respawn`: Defeated NPCs/agents returning
   - Success rate: 100%

**Expected Distribution**:
- Movement: ~40% of actions
- Gathering: ~30% of actions
- Combat: ~20% of actions
- Crafting: ~5% of actions
- Other (rest, respawn): ~5%

---

### 5. `combat_logs`
**Expected Rows**: 30-60 combat events

**What We Expect**:
- **Attacker IDs**: Warriors (Ivy, Jack, Kate), Explorers encountering enemies
- **Target IDs**: Goblins and Wolves primarily
- **Damage Dealt**: Range 5-25 per hit
- **Damage Type**: Mostly "physical"
- **Critical Hits**: 10-20% of attacks
- **Kills**: 5-15 enemy deaths (leading to respawns)
- **Weapon Used**: MeleeAttack, RangedAttack (if equipped)

**Combat Metrics**:
- Total damage dealt: 500-1,500
- Average damage per hit: 8-15
- Total kills: 5-15
- Critical hit rate: 10-20%

---

### 6. `trade_logs`
**Expected Rows**: 0-5 trades

**Note**: Trading requires proximity and mutual agreement, so we expect:
- Merchant Grace may initiate trades
- Trader Henry may attempt trades
- Most trades may not complete due to:
  - Agents being too far apart
  - Lack of desired items
  - AI prioritizing other goals

**If trades occur**:
- Initiator: Grace or Henry
- Offered items: Excess gathered resources
- Requested items: Items they don't have
- Gold amounts: 0-50 (if gold system active)

---

### 7. `analytics`
**Expected Rows**: 30-60 metrics

**Metrics Categories**:

1. **Economy** (at ticks 60, 120, 180)
   - Market prices for tradeable items
   - Resource abundance
   - Total wealth

2. **Combat** (at ticks 60, 120, 180)
   - Total damage dealt
   - Combat encounters
   - Kill/death ratios

3. **Exploration** (at ticks 60, 120, 180)
   - Tiles explored
   - Territory coverage
   - Agent distribution

4. **Social** (at ticks 60, 120, 180)
   - Trade attempts
   - Agent proximities
   - Relationship changes

---

## Specific Agent Expectations

### Gatherers
- **Alice (Woodcutter)**: 10-20 wood gathering actions, success rate 60-80%
- **Bob (Miner)**: 8-15 stone mining actions, success rate 50-70%
- **Carol (Herbalist)**: 6-12 herb foraging actions, success rate 60-80%
- **Dave (Fisher)**: 8-14 fishing actions, success rate 50-70%

### Crafters
- **Emma (Blacksmith)**: 3-8 iron ore gathering, 0-2 sword crafting attempts
- **Frank (Alchemist)**: 3-6 herb gathering, 0-3 potion crafting attempts

### Warriors
- **Ivy, Jack, Kate**: 10-20 combat actions each, 5-10 exploration moves

### Traders
- **Grace, Henry**: Multiple movement actions, 1-3 trade attempts

### Explorers
- **Leo, Maya**: 20-30 exploration/movement actions

---

## Database Health Checks

### Minimum Requirements
✅ **simulation_runs**: 1 entry
✅ **agent_snapshots**: ≥ 90 entries
✅ **world_snapshots**: 3 entries
✅ **action_logs**: ≥ 100 entries
✅ **combat_logs**: ≥ 10 entries
✅ **trade_logs**: ≥ 0 entries (optional)
✅ **analytics**: ≥ 12 entries (4 categories × 3 snapshots)

### Quality Indicators
- Action success rate: 50-80% overall
- Combat damage variance: 5-25 range
- All 18 agents appear in snapshots
- NPCs respawn after death (respawn entries in action_logs)
- Market prices fluctuate between snapshots
- Multiple action types represented

### Red Flags (Issues to Investigate)
❌ No combat logs (agents not encountering NPCs)
❌ Action logs < 50 (agents not acting)
❌ All actions failing (>90% failure rate)
❌ No respawn events despite combat
❌ Agent snapshots missing entities
❌ Market prices don't change

---

## Validation Queries

```sql
-- Check simulation completed
SELECT name, current_tick, total_agents FROM simulation_runs;

-- Count snapshots per minute
SELECT tick, COUNT(*) FROM agent_snapshots GROUP BY tick;

-- Action type distribution
SELECT action_type, COUNT(*) as count,
       AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
FROM action_logs
GROUP BY action_type;

-- Combat summary
SELECT COUNT(*) as fights,
       SUM(damage_dealt) as total_damage,
       AVG(damage_dealt) as avg_damage,
       SUM(target_died) as kills
FROM combat_logs;

-- Agent activity
SELECT agent_id, COUNT(*) as actions
FROM action_logs
GROUP BY agent_id
ORDER BY actions DESC;

-- Market price evolution
SELECT tick, market_prices
FROM world_snapshots
ORDER BY tick;
```

---

## Expected File Size
- Database file: **100-300 KB**
- Larger if more combat/actions occur
- Smaller if agents are inactive

---

## Success Criteria
1. ✅ All expected tables exist and populated
2. ✅ 90+ agent snapshots (3 per entity)
3. ✅ 100+ action logs showing diverse activities
4. ✅ 10+ combat events with damage dealt
5. ✅ 3 world snapshots at regular intervals
6. ✅ Respawn events logged when NPCs/agents die
7. ✅ Multiple action types (movement, gathering, combat, crafting)
8. ✅ Reasonable success rates (not all failures)
9. ✅ Market prices present in world snapshots
10. ✅ Analytics metrics captured
