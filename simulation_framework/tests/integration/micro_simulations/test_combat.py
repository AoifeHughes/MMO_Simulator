"""
Combat micro-simulation tests that validate combat behavior and database logging.
"""

import pytest
from src.core.simulation import Simulation
from src.ai.goal import AttackEnemyGoal, ExploreGoal

from ..helpers import (
    create_controlled_world,
    create_test_config,
    force_agent_equipment,
    create_test_warrior,
    create_test_archer,
    create_weak_goblin,
    ControlledNPC,
    StaticNPC,
    assert_combat_occurred,
    assert_entity_died,
    assert_entity_health_changed,
    assert_action_logged,
    cleanup_test_database
)


class TestCombatValidation:
    """Tests that validate combat behavior and database logging"""

    def test_guaranteed_melee_combat(self):
        """Test that melee combat occurs and is logged to database"""
        # Setup controlled environment
        config = create_test_config(world_size=5, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Guaranteed Melee Combat Test")

        # Create flat world for predictable movement
        sim.world = create_controlled_world(5, 5, terrain="plains")

        # Create warrior with forced combat goal
        warrior = create_test_warrior((2, 2), "TestWarrior")
        force_agent_equipment(warrior, "sword")

        # Create weak goblin nearby
        goblin = create_weak_goblin((3, 2), "WeakGoblin")

        # Force warrior to attack goblin
        warrior.current_goals = [AttackEnemyGoal(goblin.id, priority=10)]

        sim.add_agent(warrior)
        sim.add_npc(goblin)

        # Run simulation
        sim.run(num_ticks=50)

        # Verify combat occurred and was logged
        assert_combat_occurred(sim.db, sim.simulation_id, warrior.id, goblin.id, min_attacks=1)
        assert_entity_health_changed(sim.db, sim.simulation_id, goblin.id, decreased=True)

        # Cleanup
        cleanup_test_database(config.database_path)

    def test_ranged_combat(self):
        """Test that ranged combat with bow works and is logged"""
        config = create_test_config(world_size=10, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Ranged Combat Test")

        sim.world = create_controlled_world(10, 10, terrain="plains")

        # Create archer with bow
        archer = create_test_archer((3, 3), "TestArcher")
        force_agent_equipment(archer, "bow")

        # Create static enemy at range
        enemy = StaticNPC((7, 3), "StaticEnemy")

        # Force archer to attack
        archer.current_goals = [AttackEnemyGoal(enemy.id, priority=10)]

        sim.add_agent(archer)
        sim.add_npc(enemy)

        # Run simulation
        sim.run(num_ticks=50)

        # Verify ranged attacks logged
        assert_action_logged(sim.db, sim.simulation_id, archer.id, "RangedAttack", min_count=1)

        cleanup_test_database(config.database_path)

    def test_combat_until_death(self):
        """Test that combat continues until enemy dies and death is logged"""
        config = create_test_config(world_size=5, max_ticks=200, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Combat Until Death Test")

        sim.world = create_controlled_world(5, 5, terrain="plains")

        # Strong warrior vs weak goblin - guarantee kill
        warrior = create_test_warrior((2, 2), "Warrior")
        force_agent_equipment(warrior, "sword")
        warrior.stats.attack_power = 50  # High damage to ensure kill

        goblin = create_weak_goblin((2, 3), "WeakGoblin")
        goblin.stats.max_health = 30
        goblin.stats.health = 30

        warrior.current_goals = [AttackEnemyGoal(goblin.id, priority=10)]

        sim.add_agent(warrior)
        sim.add_npc(goblin)

        # Run until goblin dies
        sim.run(num_ticks=100)

        # Verify death logged
        assert_entity_died(sim.db, sim.simulation_id, goblin.id)

        cleanup_test_database(config.database_path)

    def test_npc_aggro_behavior(self):
        """Test that NPC aggros on nearby agent and initiates combat"""
        config = create_test_config(world_size=10, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("NPC Aggro Test")

        sim.world = create_controlled_world(10, 10, terrain="plains")

        # Agent wanders near aggressive NPC
        agent = create_test_warrior((3, 3), "WanderingAgent")
        agent.current_goals = [ExploreGoal(priority=5)]

        # Aggressive NPC with high aggro range
        npc = ControlledNPC((5, 5), "AggroNPC", aggro_range=10)
        npc.stats.attack_power = 5

        sim.add_agent(agent)
        sim.add_npc(npc)

        # Run simulation
        sim.run(num_ticks=80)

        # Verify NPC initiated combat (attacks should be logged from NPC to agent)
        assert_combat_occurred(sim.db, sim.simulation_id, npc.id, agent.id, min_attacks=1)

        cleanup_test_database(config.database_path)

    def test_combat_damage_verification(self):
        """Test that combat damage is reflected in agent snapshots"""
        config = create_test_config(world_size=5, max_ticks=100, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Combat Damage Test")

        sim.world = create_controlled_world(5, 5, terrain="plains")

        warrior = create_test_warrior((2, 2), "Warrior")
        force_agent_equipment(warrior, "sword")

        # Aggressive enemy that will attack back
        enemy = ControlledNPC((2, 3), "Attacker", aggro_range=10)
        enemy.stats.attack_power = 10

        warrior.current_goals = [AttackEnemyGoal(enemy.id, priority=10)]

        sim.add_agent(warrior)
        sim.add_npc(enemy)

        # Run simulation
        sim.run(num_ticks=60)

        # Verify health decreased for at least one combatant
        try:
            assert_entity_health_changed(sim.db, sim.simulation_id, enemy.id, decreased=True)
        except AssertionError:
            # If enemy didn't take damage, warrior should have
            assert_entity_health_changed(sim.db, sim.simulation_id, warrior.id, decreased=True)

        cleanup_test_database(config.database_path)
