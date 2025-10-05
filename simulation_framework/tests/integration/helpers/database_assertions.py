"""Database assertion helpers for verifying simulation behavior"""

from typing import List, Optional, Tuple, Dict, Any
from src.database.database import Database
from src.database.models import CombatLog, ActionLog, AgentSnapshot


def get_combat_logs(
    db: Database,
    simulation_id: int,
    attacker_id: Optional[int] = None,
    target_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get combat logs from database.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        attacker_id: Filter by attacker (optional)
        target_id: Filter by target (optional)

    Returns:
        List of combat log dictionaries
    """
    query = "SELECT * FROM combat_logs WHERE simulation_id = ?"
    params = [simulation_id]

    if attacker_id is not None:
        query += " AND attacker_id = ?"
        params.append(attacker_id)

    if target_id is not None:
        query += " AND target_id = ?"
        params.append(target_id)

    query += " ORDER BY tick ASC"

    return db.execute_custom_query(query, tuple(params))


def get_action_logs(
    db: Database,
    simulation_id: int,
    agent_id: Optional[int] = None,
    action_type: Optional[str] = None
) -> List[ActionLog]:
    """
    Get action logs from database.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        agent_id: Filter by agent (optional)
        action_type: Filter by action type (optional)

    Returns:
        List of ActionLog objects
    """
    return db.get_action_logs(
        simulation_id=simulation_id,
        agent_id=agent_id,
        action_type=action_type
    )


def get_agent_snapshots(
    db: Database,
    simulation_id: int,
    agent_id: int,
    start_tick: Optional[int] = None,
    end_tick: Optional[int] = None
) -> List[AgentSnapshot]:
    """Get agent snapshots from database"""
    return db.get_agent_snapshots(
        simulation_id=simulation_id,
        agent_id=agent_id,
        start_tick=start_tick,
        end_tick=end_tick
    )


def assert_combat_occurred(
    db: Database,
    simulation_id: int,
    attacker_id: int,
    target_id: int,
    min_attacks: int = 1
) -> None:
    """
    Assert that combat occurred between two entities.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        attacker_id: Attacker entity ID
        target_id: Target entity ID
        min_attacks: Minimum number of attacks that should have occurred

    Raises:
        AssertionError: If combat didn't occur or min_attacks not met
    """
    # Check combat_logs table first (if it's being used)
    combat_logs = get_combat_logs(db, simulation_id, attacker_id, target_id)

    # Also check action_logs for attack actions
    attack_actions = get_action_logs(
        db, simulation_id, agent_id=attacker_id, action_type="MeleeAttack"
    ) + get_action_logs(
        db, simulation_id, agent_id=attacker_id, action_type="RangedAttack"
    ) + get_action_logs(
        db, simulation_id, agent_id=attacker_id, action_type="MagicAttack"
    )

    total_attacks = len(combat_logs) + len(attack_actions)

    assert total_attacks >= min_attacks, (
        f"Expected at least {min_attacks} attacks from {attacker_id} to {target_id}, "
        f"but found {total_attacks} (combat_logs: {len(combat_logs)}, "
        f"action_logs: {len(attack_actions)})"
    )


def assert_entity_died(
    db: Database,
    simulation_id: int,
    entity_id: int,
    tick_range: Optional[Tuple[int, int]] = None
) -> None:
    """
    Assert that an entity died during the simulation.

    For NPCs, checks combat_logs for target_died=True.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        entity_id: Entity that should have died
        tick_range: Optional (start_tick, end_tick) when death should have occurred

    Raises:
        AssertionError: If entity didn't die or died outside tick range
    """
    # Get agent snapshots to check health over time
    snapshots = get_agent_snapshots(
        db, simulation_id, entity_id,
        start_tick=tick_range[0] if tick_range else None,
        end_tick=tick_range[1] if tick_range else None
    )

    if snapshots:
        # Entity is an Agent with snapshots
        died = any(snapshot.health <= 0 for snapshot in snapshots)

        assert died, (
            f"Expected entity {entity_id} to die"
            f"{f' between ticks {tick_range[0]}-{tick_range[1]}' if tick_range else ''}, "
            f"but health values were: {[s.health for s in snapshots]}"
        )
    else:
        # Entity might be an NPC - check combat logs for target_died flag
        combat_logs = get_combat_logs(db, simulation_id, target_id=entity_id)

        died = any(log.get('target_died', False) for log in combat_logs)

        assert died, (
            f"Expected entity {entity_id} (NPC) to die, "
            f"but found no combat logs with target_died=True"
        )


def assert_entity_health_changed(
    db: Database,
    simulation_id: int,
    entity_id: int,
    decreased: bool = True
) -> None:
    """
    Assert that an entity's health changed during simulation.

    For NPCs (which aren't saved in agent_snapshots), we verify via combat_logs
    showing they took damage.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        entity_id: Entity ID to check
        decreased: True to check health decreased, False for increased

    Raises:
        AssertionError: If health didn't change as expected
    """
    snapshots = get_agent_snapshots(db, simulation_id, entity_id)

    if len(snapshots) >= 2:
        # Entity is an Agent/NPC with snapshots
        snapshots.sort(key=lambda s: s.tick)
        initial_health = snapshots[0].health
        final_health = snapshots[-1].health

        if decreased:
            # Check if health decreased OR entity died (final health = 0)
            health_decreased = final_health < initial_health or final_health == 0
            assert health_decreased, (
                f"Expected entity {entity_id} health to decrease, "
                f"but went from {initial_health} to {final_health}"
            )
        else:
            assert final_health > initial_health, (
                f"Expected entity {entity_id} health to increase, "
                f"but went from {initial_health} to {final_health}"
            )
    else:
        # Entity might be an NPC - check combat logs for damage dealt to it
        combat_logs = get_combat_logs(db, simulation_id, target_id=entity_id)

        if decreased:
            # Check that entity was hit and took damage
            damage_taken = sum(log['damage_dealt'] for log in combat_logs if log.get('damage_dealt', 0) > 0)
            assert damage_taken > 0, (
                f"Expected entity {entity_id} to take damage (NPC), "
                f"but found {damage_taken} total damage in combat logs"
            )
        else:
            # For health increase, we'd need different logic (not applicable to NPCs in combat)
            raise AssertionError(f"Cannot verify health increase for NPC {entity_id} without snapshots")


def assert_resource_gathered(
    db: Database,
    simulation_id: int,
    agent_id: int,
    resource_type: str,
    min_amount: int = 1
) -> None:
    """
    Assert that an agent gathered resources.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        agent_id: Agent ID
        resource_type: Type of resource (wood, stone, etc.)
        min_amount: Minimum amount that should have been gathered

    Raises:
        AssertionError: If resource gathering didn't occur
    """
    # Check action logs for gathering actions
    gather_actions = get_action_logs(
        db, simulation_id, agent_id=agent_id, action_type="GatherAction"
    ) + get_action_logs(
        db, simulation_id, agent_id=agent_id, action_type="WoodcutAction"
    ) + get_action_logs(
        db, simulation_id, agent_id=agent_id, action_type="MineAction"
    )

    # Filter for successful gathering of the specific resource
    successful_gathers = [
        action for action in gather_actions
        if action.success and resource_type.lower() in action.result_message.lower()
    ]

    assert len(successful_gathers) >= min_amount, (
        f"Expected at least {min_amount} successful {resource_type} gathering actions "
        f"for agent {agent_id}, but found {len(successful_gathers)}"
    )


def assert_movement_occurred(
    db: Database,
    simulation_id: int,
    agent_id: int,
    from_pos: Optional[Tuple[int, int]] = None,
    to_pos: Optional[Tuple[int, int]] = None
) -> None:
    """
    Assert that an agent moved during simulation.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        agent_id: Agent ID
        from_pos: Optional starting position to verify
        to_pos: Optional ending position to verify

    Raises:
        AssertionError: If movement didn't occur or positions don't match
    """
    snapshots = get_agent_snapshots(db, simulation_id, agent_id)

    assert len(snapshots) >= 2, (
        f"Need at least 2 snapshots to check movement, got {len(snapshots)}"
    )

    # Sort by tick
    snapshots.sort(key=lambda s: s.tick)

    initial_pos = (snapshots[0].position_x, snapshots[0].position_y)
    final_pos = (snapshots[-1].position_x, snapshots[-1].position_y)

    # Check if position changed
    assert initial_pos != final_pos, (
        f"Expected agent {agent_id} to move, but stayed at {initial_pos}"
    )

    # Verify specific positions if provided
    if from_pos:
        assert initial_pos == from_pos, (
            f"Expected agent {agent_id} to start at {from_pos}, "
            f"but was at {initial_pos}"
        )

    if to_pos:
        assert final_pos == to_pos, (
            f"Expected agent {agent_id} to end at {to_pos}, "
            f"but was at {final_pos}"
        )


def assert_action_logged(
    db: Database,
    simulation_id: int,
    agent_id: int,
    action_type: str,
    min_count: int = 1,
    success: Optional[bool] = None
) -> None:
    """
    Assert that a specific action was logged.

    Args:
        db: Database instance
        simulation_id: Simulation ID
        agent_id: Agent ID
        action_type: Type of action (MoveAction, AttackAction, etc.)
        min_count: Minimum number of times action should have been logged
        success: If specified, only count actions with this success status

    Raises:
        AssertionError: If action wasn't logged min_count times
    """
    actions = get_action_logs(db, simulation_id, agent_id=agent_id, action_type=action_type)

    if success is not None:
        actions = [a for a in actions if a.success == success]

    assert len(actions) >= min_count, (
        f"Expected at least {min_count} {action_type} actions for agent {agent_id}"
        f"{f' with success={success}' if success is not None else ''}, "
        f"but found {len(actions)}"
    )


def assert_stamina_decreased(
    db: Database,
    simulation_id: int,
    agent_id: int
) -> None:
    """Assert that agent's stamina decreased (proving actions consumed stamina)"""
    snapshots = get_agent_snapshots(db, simulation_id, agent_id)

    assert len(snapshots) >= 2, (
        f"Need at least 2 snapshots to check stamina, got {len(snapshots)}"
    )

    snapshots.sort(key=lambda s: s.tick)
    initial_stamina = snapshots[0].stamina
    final_stamina = snapshots[-1].stamina

    assert final_stamina < initial_stamina, (
        f"Expected agent {agent_id} stamina to decrease, "
        f"but went from {initial_stamina} to {final_stamina}"
    )


def assert_inventory_changed(
    db: Database,
    simulation_id: int,
    agent_id: int
) -> None:
    """Assert that agent's inventory changed (items added or removed)"""
    snapshots = get_agent_snapshots(db, simulation_id, agent_id)

    assert len(snapshots) >= 2, (
        f"Need at least 2 snapshots to check inventory, got {len(snapshots)}"
    )

    snapshots.sort(key=lambda s: s.tick)
    initial_items = snapshots[0].inventory_items
    final_items = snapshots[-1].inventory_items

    assert initial_items != final_items, (
        f"Expected agent {agent_id} inventory to change, "
        f"but stayed at {initial_items} items"
    )
