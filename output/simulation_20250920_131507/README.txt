MMO SIMULATION VISUALIZATION OUTPUT
========================================

FILES IN THIS DIRECTORY:

simulation_data.csv - Raw simulation data in CSV format
  Columns: timestamp, tick, agent_id, agent_name, health, max_health,
           pos_x, pos_y, action, velocity_x, velocity_y

simulation_data.json - Raw simulation data in JSON format
  Complete snapshots with all world state information

summary_report.txt - Human-readable analysis report
  Agent statistics, movement patterns, health analysis

frame_*.png - World state visualizations
  Generated every 5 snapshots showing:
  - Red circles: Hazard zones
  - Green circles: Healing stations
  - Colored dots: Agents (color = health, arrows = velocity)
    Blue = healthy, Yellow = moderate, Orange = low health
    Brighter colors indicate special actions

Total snapshots captured: 29
Capture interval: 2.0 seconds
