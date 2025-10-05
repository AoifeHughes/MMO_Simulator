# Issue Analysis and Fixes

## Summary of Warnings

After running the 3-minute complex simulation, we identified several critical issues:

1. **Wood gathering: 0% success rate** (235 attempts, 0 successes)
2. **Combat: 2.7% success rate** (187 attempts, 5 successes)
3. **Foraging: 9.4% success rate** (32 attempts, 3 successes)
4. **Crafting: 0% success rate** (20 attempts, 0 successes)

---

## Issue #1: Wood Gathering (0% Success)

### Root Cause
**Missing Equipment**: Agents attempting to gather wood don't have the required axe tool.

### Evidence
- `WoodcutAction` requires `required_tool="axe"` (gathering.py:224)
- `can_execute()` checks for equipped axe (gathering.py:40-45)
- Hunter class (Alice's class) has woodcutting skill but **no axe** in equipment_preferences
- Hunter equipment: `["bow", "leather_armor", "hunting_knife"]` (character_class.py:129)

### Why It Fails
```python
# gathering.py lines 40-45
if self.required_tool:
    tool = actor.inventory.get_equipped_tool(self.required_tool)
    if not tool:
        return False  # ← Fails here, no axe equipped
```

### Fix Required
**Option 1**: Add axe to Hunter class equipment
**Option 2**: Remove tool requirement for basic wood gathering
**Option 3**: Create specialized "Lumberjack" class or give specific agents axes

### Recommended Fix
Add multiple tools to classes that need them (not just one tool via elif chain):

```python
# In CharacterClass.get_starting_equipment()
# Change from elif chain to multiple if statements
if "pickaxe" in self.equipment_preferences:
    equipment.append(Tool.create_pickaxe())
if "axe" in self.equipment_preferences:  # Changed from elif
    equipment.append(Tool.create_axe())
if "fishing_rod" in self.equipment_preferences:  # Changed from elif
    equipment.append(Tool.create_fishing_rod())
```

Then update Hunter equipment preferences to include axe:
```python
equipment_preferences=["bow", "leather_armor", "hunting_knife", "axe"]
```

---

## Issue #2: Combat (2.7% Success)

### Root Cause
**Range Mismatch**: Goal allows attacking at distance <= 2.0, but action requires distance <= 1.0

### Evidence
- `AttackEnemyGoal.get_next_action()` creates MeleeAttack when `distance <= 2.0` (goal.py:275, 279)
- `MeleeAttack.can_execute()` requires `distance <= base_range + 0.01` where base_range = 1.0 (combat.py:36)
- Agents pathfind to within 2.0 tiles, think they can attack, but action fails

### Why It Fails
```python
# goal.py lines 275-280
if distance <= 2.0:  # ← Goal says "attack now"
    return MeleeAttack(agent.id, self.target_id)

# combat.py lines 34-37
distance = actor.distance_to(target)
if distance > self.base_range + 0.01:  # base_range = 1.0
    return False  # ← Action says "too far" when distance > 1.0
```

### Scenario
1. Agent at (10, 10), Enemy at (11, 11)
2. Distance = sqrt(2) ≈ 1.41
3. Goal: "Distance 1.41 <= 2.0, attack!" → Creates MeleeAttack
4. Action: "Distance 1.41 > 1.0, fail!" → Cannot execute attack

### Fix Required
**Option 1**: Change goal to use distance <= 1.5 (conservative)
**Option 2**: Change MeleeAttack base_range to 2.0 (aggressive)
**Option 3**: Use distance <= 1.5 in both (balanced)

### Recommended Fix
Use **1.5 tiles** as the maximum melee range (allows diagonal attacks):

```python
# In goal.py, AttackEnemyGoal.get_next_action()
elif distance <= 1.5:  # Changed from 2.0
    return MeleeAttack(agent.id, self.target_id)

# In combat.py, MeleeAttack.__init__()
class MeleeAttack(CombatAction):
    def __init__(self, actor_id: int, target_id: int):
        super().__init__(
            actor_id,
            target_id,
            damage_type=DamageType.PHYSICAL,
            base_range=1.5  # Changed from 1.0
        )
```

This allows:
- Orthogonal attacks (distance 1.0) ✓
- Diagonal attacks (distance ~1.41) ✓
- Two-tile-away attacks (distance 2.0) ✗

---

## Issue #3: Foraging (9.4% Success)

### Root Cause
**Terrain/Resource Mismatch**: Agents trying to forage but either:
1. Not on correct terrain (forest/grass)
2. Tiles don't have forageable resources

### Evidence
- ForageAction requires terrain in `["forest", "grass"]` (gathering.py:212-214)
- Must also have gatherable resources on tile (gathering.py:216)
- Only 3/32 attempts succeeded

### Why It Fails
```python
# gathering.py lines 207-216
def can_execute(self, actor: Entity, world: World) -> bool:
    tile = world.get_tile(*actor.position)
    if not tile:
        return False

    valid_terrain = tile.terrain_type.value in ["forest", "grass"]
    if not valid_terrain:
        return False  # ← Fail if on mountain/water/etc

    return tile.can_gather(self.resource_type) and self.get_cost().can_afford(actor)
    # ← Fail if tile has no berries/herbs
```

### Fix Required
**Option 1**: Ensure world generation creates more forageable resources
**Option 2**: Have agents pathfind to forest/grass tiles before foraging
**Option 3**: Increase resource node density in world generator

### Recommended Fix
The 9.4% success rate suggests this is **working as intended** - agents wander to random tiles, most don't have resources. The goal should pathfind to resource locations (similar to GatherResourceGoal for wood/stone).

Current ForageAction is being used directly without pathfinding to resources first.

---

## Issue #4: Crafting (0% Success)

### Root Cause
**Missing Materials**: Crafting requires materials from gathering, which is currently failing.

### Evidence
- CraftAction checks for required materials (crafting.py:60-62)
- Emma needs iron_ore for Iron Sword
- Frank needs herbs for Health Potion
- Gathering is failing (0% wood, 9% forage), so no materials collected

### Why It Fails
```python
# crafting.py lines 55-62
def can_execute(self, actor: Entity, world: World) -> bool:
    if not self.recipe:
        return False

    # Check materials
    for material, needed in self.recipe.get("materials", {}).items():
        if not actor.inventory.has_item(material, needed * self.quantity):
            return False  # ← No materials in inventory
```

### Fix Required
**Dependent on Issue #1**: Once gathering is fixed, crafting will work.

### Recommended Fix
Fix gathering systems first, then crafting will automatically work.

---

## Additional Issue: Mining (Not in Report but Likely Failing)

### Root Cause
**Missing Equipment**: Same as wood gathering - miners need pickaxes.

### Evidence
- `MineAction` requires `required_tool="pickaxe"` (gathering.py:193)
- Warrior class (Bob's class) has **no pickaxe** in equipment

### Fix Required
Add pickaxe to Warrior or create dedicated Miner class.

---

## Implementation Plan

### Phase 1: Equipment Fixes (HIGH PRIORITY)
1. ✅ Change `get_starting_equipment()` from elif chain to multiple if statements
2. ✅ Add "axe" to Hunter equipment_preferences
3. ✅ Add "pickaxe" to Warrior or Blacksmith equipment_preferences
4. ✅ Add "fishing_rod" to Hunter equipment_preferences (for Dave/Riley)

### Phase 2: Combat Range Fixes (HIGH PRIORITY)
1. ✅ Change MeleeAttack base_range from 1.0 to 1.5
2. ✅ Change AttackEnemyGoal distance check from 2.0 to 1.5

### Phase 3: Resource Availability (MEDIUM PRIORITY)
1. ⚠️ Verify world generator creates resource nodes on tiles
2. ⚠️ Ensure forest tiles have wood resources
3. ⚠️ Ensure grass/forest tiles have forageable items
4. ⚠️ Ensure mountain tiles have stone/ore resources

### Phase 4: Goal Pathfinding (MEDIUM PRIORITY)
1. ⚠️ ForageAction should pathfind to resource tiles (like GatherResourceGoal does)
2. ⚠️ Verify GatherResourceGoal pathfinding to resource locations

---

## Expected Results After Fixes

### Wood Gathering
- **Before**: 0% success (0/235)
- **After**: 60-80% success (hunters have axes, can cut wood)

### Combat
- **Before**: 2.7% success (5/187)
- **After**: 50-70% success (range mismatch fixed)

### Foraging
- **Before**: 9.4% success (3/32)
- **After**: 20-40% success (still terrain dependent, but better with pathfinding)

### Crafting
- **Before**: 0% success (0/20)
- **After**: 40-60% success (depends on gathering success)

### Mining
- **Before**: Not tested (Bob is Warrior, no pickaxe)
- **After**: 50-70% success (warriors/blacksmiths have pickaxes)

---

## Files to Modify

1. **simulation_framework/src/ai/character_class.py**
   - Fix: `get_starting_equipment()` method (lines 46-68)
   - Fix: Hunter equipment_preferences (line 129)
   - Fix: Warrior equipment_preferences (line 87)
   - Fix: Blacksmith equipment_preferences (line 170)

2. **simulation_framework/src/ai/goal.py**
   - Fix: `AttackEnemyGoal.get_next_action()` (lines 275, 279)

3. **simulation_framework/src/actions/combat.py**
   - Fix: `MeleeAttack.__init__()` base_range parameter

---

## Testing Plan

After fixes, run the same simulation:
```bash
PYTHONPATH=. python examples/complex_simulation.py --ticks 180 --no-visual
```

Then verify:
```sql
SELECT action_type,
       COUNT(*) as total,
       SUM(success) as successes,
       ROUND(100.0 * SUM(success) / COUNT(*), 1) as success_rate
FROM action_logs
GROUP BY action_type
ORDER BY total DESC;
```

**Success Criteria**:
- WoodcutAction: >50% success
- MeleeAttack: >40% success
- ForageAction: >15% success
- CraftAction: >20% success (after materials gathered)
- MineAction: >40% success (if agents attempt it)
