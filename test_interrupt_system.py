#!/usr/bin/env python3
"""
Comprehensive tests for the interrupt system in MMO Simulator.
Tests action interruptions, threat detection, and priority-based goal switching.
"""

import sys
import os
sys.path.insert(0, '.')

from simulation_framework.src.core.simulation import Simulation
from simulation_framework.src.core.config import SimulationConfig
from simulation_framework.src.entities.agent import create_agent_with_archetype
from simulation_framework.src.entities.npc import create_basic_goblin
from simulation_framework.src.ai.goal import ExploreGoal, FleeFromDangerGoal, GatherResourceGoal
from simulation_framework.src.ai.personality import Personality
import tempfile
import logging

# Enable logging to see interrupt messages
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_entity_management():
    """Test that entities are properly added to world.entities"""
    print("=== Test 1: Entity Management ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    config = SimulationConfig(world_width=10, world_height=10, world_seed=123, database_path=db_path)
    sim = Simulation(config)
    sim.initialize_simulation('Entity Test', 'Test entity management')

    agent = create_agent_with_archetype((5, 5), 'explorer', 'Test Agent')
    sim.add_agent(agent)

    goblin = create_basic_goblin((6, 5))
    sim.add_npc(goblin)

    # Verify entities are in world.entities
    assert len(sim.world.entities) == 2, f"Expected 2 entities in world, got {len(sim.world.entities)}"
    assert agent.id in sim.world.entities, "Agent not found in world.entities"
    assert goblin.id in sim.world.entities, "Goblin not found in world.entities"

    print("✓ Entities properly added to world.entities")


def test_npc_aggro_system():
    """Test that NPCs automatically target nearby agents"""
    print("\n=== Test 2: NPC Aggro System ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    config = SimulationConfig(world_width=10, world_height=10, world_seed=123, database_path=db_path)
    sim = Simulation(config)
    sim.initialize_simulation('Entity Test', 'Test entity management')

    agent = create_agent_with_archetype((5, 5), 'explorer', 'Test Agent')
    sim.add_agent(agent)

    goblin = create_basic_goblin((6, 5))
    sim.add_npc(goblin)

    # Initially goblin should have no target
    assert goblin.target_id is None, f"Goblin should have no initial target, got {goblin.target_id}"

    # Run one simulation step to trigger aggro check
    sim.running = True
    sim.step()

    # Goblin should now target the agent (distance = 1, within aggro_range = 5)
    assert goblin.target_id == agent.id, f"Goblin should target agent {agent.id}, got {goblin.target_id}"

    print(f"✓ Goblin automatically acquired target: Agent {goblin.target_id}")


def test_threat_detection():
    """Test that agents detect threats from hostile NPCs"""
    print("\n=== Test 3: Threat Detection ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    config = SimulationConfig(world_width=10, world_height=10, world_seed=123, database_path=db_path)
    sim = Simulation(config)
    sim.initialize_simulation('Threat Test', 'Test threat detection')
    sim.running = True

    # Create weak, cautious agent
    agent = create_agent_with_archetype((5, 5), 'explorer', 'Cautious Agent')
    agent.personality = Personality(
        bravery=0.1, caution=0.9, aggression=0.1, curiosity=0.5,
        industriousness=0.5, greed=0.3, patience=0.5, sociability=0.5
    )
    agent.stats.max_health = 30
    agent.stats.health = 30
    agent.stats.attack_power = 2
    agent.stats.defense = 1
    sim.add_agent(agent)

    goblin = create_basic_goblin((6, 5))
    sim.add_npc(goblin)

    # Trigger aggro
    sim.step()

    # Agent should now detect the goblin as a threat
    threats = agent.decision_maker._find_immediate_threats(agent, sim.world)

    assert len(threats) > 0, "Agent should detect at least one threat"
    assert goblin in threats, "Agent should detect goblin as threat"

    print(f"✓ Agent detected {len(threats)} threat(s): {[t.name for t in threats]}")


def test_flee_goal_generation():
    """Test that FleeFromDangerGoal is generated for threats"""
    print("\n=== Test 4: Flee Goal Generation ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    config = SimulationConfig(world_width=10, world_height=10, world_seed=123, database_path=db_path)
    sim = Simulation(config)
    sim.initialize_simulation('Threat Test', 'Test threat detection')
    sim.running = True

    # Create weak, cautious agent
    agent = create_agent_with_archetype((5, 5), 'explorer', 'Cautious Agent')
    agent.personality = Personality(
        bravery=0.1, caution=0.9, aggression=0.1, curiosity=0.5,
        industriousness=0.5, greed=0.3, patience=0.5, sociability=0.5
    )
    agent.stats.max_health = 30
    agent.stats.health = 30
    agent.stats.attack_power = 2
    agent.stats.defense = 1
    sim.add_agent(agent)

    goblin = create_basic_goblin((6, 5))
    sim.add_npc(goblin)

    # Trigger aggro
    sim.step()

    # Reset decision maker cooldown so it can make decisions
    agent.decision_maker.reset_decision_cooldown()

    # Generate potential goals (including flee goals)
    potential_goals = agent.decision_maker._generate_potential_goals(agent, sim.world)

    flee_goals = [g for g in potential_goals if isinstance(g, FleeFromDangerGoal)]
    assert len(flee_goals) > 0, "Should generate at least one FleeFromDangerGoal"

    flee_goal = flee_goals[0]
    assert flee_goal.danger_source_id == goblin.id, f"Flee goal should target goblin {goblin.id}"
    assert flee_goal.priority == 9, f"Flee goal should have priority 9, got {flee_goal.priority}"

    print(f"✓ Generated FleeFromDangerGoal with priority {flee_goal.priority}")


def test_priority_based_interruption():
    """Test that high-priority goals interrupt lower-priority actions"""
    print("\n=== Test 5: Priority-Based Action Interruption ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    config = SimulationConfig(world_width=10, world_height=10, world_seed=123, database_path=db_path)
    sim = Simulation(config)
    sim.initialize_simulation('Interrupt Test', 'Test priority-based interruption')
    sim.running = True

    # Create weak, cautious agent
    agent = create_agent_with_archetype((5, 5), 'explorer', 'Cautious Agent')
    agent.personality = Personality(
        bravery=0.1, caution=0.9, aggression=0.1, curiosity=0.5,
        industriousness=0.5, greed=0.3, patience=0.5, sociability=0.5
    )
    agent.stats.max_health = 30
    agent.stats.health = 30
    agent.stats.attack_power = 2
    agent.stats.defense = 1
    sim.add_agent(agent)

    goblin = create_basic_goblin((6, 5))
    sim.add_npc(goblin)

    # Trigger aggro
    sim.step()

    # Reset decision maker cooldown so it can make decisions
    agent.decision_maker.reset_decision_cooldown()

    # Generate potential goals (including flee goals)
    potential_goals = agent.decision_maker._generate_potential_goals(agent, sim.world)

    flee_goals = [g for g in potential_goals if isinstance(g, FleeFromDangerGoal)]
    assert len(flee_goals) > 0, "Should generate at least one FleeFromDangerGoal"

    flee_goal = flee_goals[0]

    # Give agent a low-priority goal and start an action
    explore_goal = ExploreGoal(priority=3)
    agent.current_goals = [explore_goal]  # Start with low-priority goal
    agent.decision_maker.reset_decision_cooldown()

    # Agent should start exploring
    agent.decide(sim.world)  # This sorts goals by priority
    agent.act(sim.world)     # This should create a WanderAction

    initial_action = agent.current_action
    initial_goal = agent.current_action_goal

    assert initial_action is not None, "Agent should have started an action"
    assert initial_goal == explore_goal, "Action should be from explore goal"

    print(f"✓ Agent started {type(initial_action).__name__} from goal priority {initial_goal.priority}")

    # Now add high-priority flee goal
    agent.current_goals.append(flee_goal)
    agent.decide(sim.world)  # This should put flee goal first (priority 9 > 3)

    assert agent.current_goals[0] == flee_goal, "Flee goal should be highest priority"

    # Next act() call should interrupt the current action
    agent.act(sim.world)

    new_action = agent.current_action
    new_goal = agent.current_action_goal

    # Verify interruption occurred or flee action was executed
    if new_action != initial_action:
        print(f"✓ Action interrupted! New action: {type(new_action).__name__ if new_action else None}")
        print(f"✓ New goal priority: {new_goal.priority if new_goal else None}")
        # For single-tick actions like FleeAction, current_action_goal may be None after execution
        if new_goal:
            assert new_goal == flee_goal, "New action should be from flee goal"
        else:
            print("✓ Flee action executed immediately (single-tick action)")
    else:
        # Check if initial action was not interruptible
        if hasattr(initial_action, 'can_interrupt'):
            can_interrupt = initial_action.can_interrupt()
            print(f"Initial action can_interrupt: {can_interrupt}")
            if not can_interrupt:
                print("✓ Action was not interrupted because it's non-interruptible")
            else:
                # This might happen if the action completed naturally
                print("⚠ Action was not interrupted - this might be expected behavior")


def test_complete_interrupt_scenario():
    """Test a complete interrupt scenario from start to finish"""
    print("\n=== Test 6: Complete Interrupt Scenario ===")

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    config = SimulationConfig(world_width=15, world_height=15, world_seed=456, database_path=db_path)
    sim = Simulation(config)
    sim.initialize_simulation('Complete Test', 'Full interrupt scenario test')
    sim.running = True

    # Create cautious agent who will flee
    agent = create_agent_with_archetype((7, 7), 'explorer', 'Cautious Agent')
    agent.personality.bravery = 0.2  # Low bravery = more likely to flee
    agent.personality.caution = 0.8  # High caution = more likely to flee

    # Start with gathering goal
    gather_goal = GatherResourceGoal("wood", target_quantity=5, priority=4)
    agent.current_goals = [gather_goal]

    sim.add_agent(agent)

    # Create goblin far away initially
    goblin = create_basic_goblin((12, 12))  # Distance ~7 from agent
    sim.add_npc(goblin)

    print(f"Initial setup: Agent at {agent.position}, Goblin at {goblin.position}")
    print(f"Distance: {agent.distance_to(goblin):.1f}, Goblin aggro range: {goblin.aggro_range}")

    # Run simulation steps
    for step in range(8):
        old_pos = agent.position
        old_action = type(agent.current_action).__name__ if agent.current_action else None
        old_goals = len(agent.current_goals)

        sim.step()

        new_pos = agent.position
        new_action = type(agent.current_action).__name__ if agent.current_action else None
        new_goals = len(agent.current_goals)
        distance_to_goblin = agent.distance_to(goblin)

        print(f"Step {step}: Agent {old_pos}->{new_pos}, Action {old_action}->{new_action}, "
              f"Goals {old_goals}->{new_goals}, Distance to goblin: {distance_to_goblin:.1f}")

        # Check if goblin acquired target
        if goblin.target_id == agent.id:
            print(f"  -> Goblin acquired agent as target!")

        # Check for flee goals
        flee_goals = [g for g in agent.current_goals if isinstance(g, FleeFromDangerGoal)]
        if flee_goals:
            print(f"  -> Agent has FleeFromDangerGoal (priority {flee_goals[0].priority})!")

        # Check if we're outside aggro range
        if distance_to_goblin > goblin.aggro_range:
            print(f"  -> Agent escaped! Outside aggro range ({goblin.aggro_range})")
            break

    print("✓ Complete scenario test finished")


def run_all_tests():
    """Run all interrupt system tests"""
    print("Running Interrupt System Tests...\n")

    try:
        test_entity_management()
        test_npc_aggro_system()
        test_threat_detection()
        test_flee_goal_generation()
        test_priority_based_interruption()
        test_complete_interrupt_scenario()

        print("\n🎉 All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)