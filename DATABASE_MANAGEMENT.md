# 🗄️ **Automatic Database Management System**

The MMO Simulator now includes an **automatic database management system** that handles fresh database creation, backup management, and cleanup for every simulation run.

## 🚀 **How It Works**

### **Automatic Fresh Database Creation**
- **Every simulation run** automatically creates a fresh `simulation_data.db`
- **Previous database** is automatically backed up with timestamp
- **No manual cleanup needed** - each run starts with a clean slate
- **Backup files preserved** for analysis of previous runs

### **Default Behavior**
```bash
# Each time you run ANY simulation:
python comprehensive_test_simulation.py          # ← Creates fresh DB
python comprehensive_visual_simulation.py        # ← Creates fresh DB
python examples/visual_simulation.py            # ← Creates fresh DB
```

**What happens automatically:**
1. 📁 Existing `simulation_data.db` → Backed up as `simulation_data.db.backup_20231229_143022`
2. 🗑️ Old database removed
3. ✨ Fresh `simulation_data.db` created for new run
4. 🧹 Old backups cleaned up (keeps last 5)

## 📁 **File Locations**

### **Current Database**
```
/Users/aoife/git/MMO_Simulator/simulation_data.db
```
*Always contains data from your most recent simulation run*

### **Backup Files**
```
/Users/aoife/git/MMO_Simulator/simulation_data.db.backup_20231229_143022
/Users/aoife/git/MMO_Simulator/simulation_data.db.backup_20231229_142015
/Users/aoife/git/MMO_Simulator/simulation_data.db.backup_20231229_141008
...
```
*Timestamped backups of previous simulation runs*

## 🛠️ **Database Management Commands**

### **List Database Files**
```bash
python manage_database.py list
```
Shows current database and all available backups.

### **Restore Previous Run**
```bash
python manage_database.py restore
```
Restores the most recent backup as the current database.

### **Clean All Databases**
```bash
python manage_database.py cleanup
```
⚠️ Removes ALL database files and backups (use with caution!).

### **Create Fresh Database**
```bash
python manage_database.py fresh
```
Manually create a fresh database (same as starting a simulation).

## 🔄 **Typical Workflow**

### **Normal Usage** (No commands needed!)
```bash
# Run simulation - automatically gets fresh database
python comprehensive_visual_simulation.py

# Analyze current results
python analyze_simulation_results.py

# Run another simulation - automatically creates new fresh database
python comprehensive_test_simulation.py

# Previous results are safely backed up automatically!
```

### **Comparing Multiple Runs**
```bash
# Run first simulation
python comprehensive_test_simulation.py
python analyze_simulation_results.py    # Analyze run 1

# Run second simulation
python comprehensive_test_simulation.py
python analyze_simulation_results.py    # Analyze run 2

# Compare with previous run
python manage_database.py list          # See available backups
python manage_database.py restore       # Restore previous run
python analyze_simulation_results.py    # Analyze run 1 again
```

## 🎯 **Benefits**

### **✅ Always Fresh Start**
- No contamination from previous runs
- Consistent baseline for comparisons
- Clean database schema each time

### **✅ Automatic Backup**
- Previous runs preserved automatically
- No manual backup needed
- Timestamped for easy identification

### **✅ Easy Analysis**
- Current run always in `simulation_data.db`
- Previous runs easily accessible via backups
- Simple restore process for comparisons

### **✅ Disk Space Management**
- Automatic cleanup of old backups
- Keeps only recent 5 backups
- No manual maintenance required

## 💡 **Pro Tips**

### **For Development/Testing**
```bash
# Just run simulations normally - fresh DB each time
python comprehensive_visual_simulation.py
```

### **For Research/Analysis**
```bash
# Run multiple experiments
python comprehensive_test_simulation.py    # Experiment 1
# ... analyze results ...

python comprehensive_test_simulation.py    # Experiment 2
# ... analyze results ...

# Compare experiments
python manage_database.py list            # See all runs
python manage_database.py restore         # Go back to previous
```

### **For Demos**
```bash
# Always start with fresh state
python comprehensive_visual_simulation.py  # Clean demo every time
```

## 🔧 **Advanced Configuration**

If you need custom database behavior, you can still override:

```python
# Custom database path (disables auto-management)
config = SimulationConfig(
    database_path="/custom/path/my_simulation.db",  # Manual path
    # ... other config ...
)

# Or disable cleanup for this run
from simulation_framework.src.utils.database_manager import get_database_path
config = SimulationConfig(
    database_path=get_database_path(auto_cleanup=False),  # Keep old DB
    # ... other config ...
)
```

## 📊 **Example Output**

```bash
$ python comprehensive_visual_simulation.py

=== COMPREHENSIVE VISUAL SIMULATION ===
This will run the comprehensive test with pygame visualization!
Backed up previous database to: simulation_data.db.backup_20231229_143022
Created fresh database: /Users/aoife/git/MMO_Simulator/simulation_data.db
Configuration: 30x30 world
Database: /Users/aoife/git/MMO_Simulator/simulation_data.db
...simulation runs...
✅ Database saved permanently at: /Users/aoife/git/MMO_Simulator/simulation_data.db

$ python analyze_simulation_results.py
# Analyzes the fresh results from the run above

$ python manage_database.py list
=== Database Files ===
Current database: /Users/aoife/git/MMO_Simulator/simulation_data.db

Backup files:
  simulation_data.db.backup_20231229_143022 (created: 2023-12-29 14:30:22)
  simulation_data.db.backup_20231229_142015 (created: 2023-12-29 14:20:15)
```

---

**🎉 That's it!** The database system now automatically manages itself. Just run your simulations and focus on the results! 🚀