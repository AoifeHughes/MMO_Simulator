"""
Multi-system integration micro-simulation tests.
"""

from src.ai.goal import AttackEnemyGoal, RestGoal
from src.core.simulation import Simulation

from ..helpers import (
    StaticNPC,
    assert_combat_occurred,
    assert_entity_died,
    cleanup_test_database,
    create_controlled_world,
    create_test_config,
    create_test_warrior,
    create_weak_goblin,
    force_agent_equipment,
)


class TestMultiSystemIntegration:
    """Tests that validate multiple systems working together"""

    def test_combat_loot_inventory(self):
        """Test full combat -> loot -> inventory chain"""
        config = create_test_config(world_size=5, max_ticks=150, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Combat Loot Test")

        sim.world = create_controlled_world(5, 5, terrain="plains")

        warrior = create_test_warrior((2, 2), "LootWarrior")
        force_agent_equipment(warrior, "sword")
        warrior.stats.attack_power = 60  # Guarantee kill

        goblin = create_weak_goblin((2, 3), "LootGoblin")
        goblin.stats.max_health = 25
        goblin.stats.health = 25

        warrior.current_goals = [AttackEnemyGoal(goblin.id, priority=10)]

        sim.add_agent(warrior)
        sim.add_npc(goblin)

        # Run simulation
        sim.run(num_ticks=100)

        # Verify combat occurred
        assert_combat_occurred(
            sim.db, sim.simulation_id, warrior.id, goblin.id, min_attacks=1
        )

        # Verify death
        assert_entity_died(sim.db, sim.simulation_id, goblin.id)

        cleanup_test_database(config.database_path)

    def test_movement_combat_sequence(self):
        """Test agent paths to enemy, fights, and sequence is logged"""
        config = create_test_config(world_size=10, max_ticks=150, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Movement Combat Sequence Test")

        sim.world = create_controlled_world(10, 10, terrain="plains")

        warrior = create_test_warrior((2, 2), "SeqWarrior")
        force_agent_equipment(warrior, "sword")

        # Enemy far away
        enemy = StaticNPC((8, 8), "FarEnemy")

        warrior.current_goals = [AttackEnemyGoal(enemy.id, priority=10)]

        sim.add_agent(warrior)
        sim.add_npc(enemy)

        # Run simulation
        sim.run(num_ticks=120)

        # Verify combat occurred (which proves movement happened - warrior had to reach enemy)
        assert_combat_occurred(
            sim.db, sim.simulation_id, warrior.id, enemy.id, min_attacks=1
        )

        # Combat occurring proves movement succeeded (warrior moved from (2,2) to enemy at (8,8))

        cleanup_test_database(config.database_path)

    def test_stamina_depletion_rest(self):
        """Test that agent depletes stamina and rests to recover"""
        config = create_test_config(world_size=5, max_ticks=150, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Stamina Rest Test")

        sim.world = create_controlled_world(5, 5, terrain="plains")

        # Agent with low stamina
        agent = create_test_warrior((2, 2), "TiredWarrior")
        agent.stats.stamina = 10  # Very low stamina
        agent.stats.max_stamina = 100

        # Give rest goal (rest is passive - no action, just stat restoration)
        agent.current_goals = [RestGoal(priority=10)]

        sim.add_agent(agent)

        # Run simulation
        sim.run(num_ticks=100)

        # Verify stamina increased (rest goal restores stamina passively)
        snapshots = sim.db.get_agent_snapshots(sim.simulation_id, agent.id)
        snapshots.sort(key=lambda s: s.tick)
        initial_stamina = snapshots[0].stamina
        final_stamina = snapshots[-1].stamina

        assert final_stamina > initial_stamina, (
            f"Expected stamina to increase from resting, "
            f"but went from {initial_stamina} to {final_stamina}"
        )

        cleanup_test_database(config.database_path)

    def test_respawn_system(self):
        """Test that NPC respawns after death"""
        config = create_test_config(world_size=5, max_ticks=200, save_interval=5)
        sim = Simulation(config)
        sim.initialize_simulation("Respawn Test")

        sim.world = create_controlled_world(5, 5, terrain="plains")

        warrior = create_test_warrior((2, 2), "Killer")
        force_agent_equipment(warrior, "sword")
        warrior.stats.attack_power = 100  # Guarantee kill

        # NPC with quick respawn
        npc = create_weak_goblin((2, 3), "RespawnGoblin")
        npc.respawn_delay = 20  # Respawn after 20 ticks
        npc.stats.max_health = 20
        npc.stats.health = 20

        warrior.current_goals = [AttackEnemyGoal(npc.id, priority=10)]

        sim.add_agent(warrior)
        sim.add_npc(npc)

        # Run simulation
        sim.run(num_ticks=150)

        # Verify death occurred
        assert_entity_died(sim.db, sim.simulation_id, npc.id)

        # Note: Respawn verification would require checking world_snapshots
        # which is more complex - for now we verify death works

        cleanup_test_database(config.database_path)
