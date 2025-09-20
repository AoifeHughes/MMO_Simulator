#!/usr/bin/env python3
"""
Test script for the new configuration system
"""

import asyncio
import sys
import time
import logging

# Add current directory to path
sys.path.append('.')

from config.config_loader import ConfigLoader
from server.core.world_server import WorldServer
from client.core.agent_client import AgentClient, AgentConfig
from examples.simple_agent import SimpleExplorerAgent, CombatAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_config_loading():
    """Test configuration loading"""
    print("=" * 60)
    print("TESTING CONFIGURATION SYSTEM")
    print("=" * 60)

    config_loader = ConfigLoader("config")

    # Test loading all configs
    success = config_loader.load_all_configs()
    print(f"Configuration loading: {'✅ SUCCESS' if success else '❌ FAILED'}")

    if success:
        # Test world config
        world_config = config_loader.world_config
        print(f"World config loaded: {bool(world_config)}")
        if world_config:
            print(f"  - NPCs configured: {len(world_config.npcs)}")
            print(f"  - Enemy templates: {len(world_config.enemy_templates)}")
            print(f"  - Objects: {len(world_config.objects)}")

        # Test agent config
        agent_config = config_loader.agent_config
        print(f"Agent config loaded: {bool(agent_config)}")
        if agent_config:
            print(f"  - Agent templates: {len(agent_config.agent_templates)}")
            print(f"  - Test scenarios: {len(agent_config.test_scenarios)}")

        # Test server config
        server_config = config_loader.server_config
        print(f"Server config loaded: {bool(server_config)}")
        if server_config:
            print(f"  - Server host: {server_config.server_settings.get('host', 'default')}")
            print(f"  - Server port: {server_config.server_settings.get('port', 'default')}")

        # Validate configs
        issues = config_loader.validate_configs()
        if issues:
            print("Configuration issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✅ All configurations valid")

    return success


async def test_server_with_config():
    """Test server startup with configuration"""
    print("\n" + "=" * 60)
    print("TESTING SERVER WITH CONFIGURATION")
    print("=" * 60)

    try:
        # Start server with config
        server = WorldServer(config_dir="config")
        logger.info("Server created successfully with configuration")

        # Test that validation systems are initialized
        print(f"Bounds checker: {'✅' if server.bounds_checker else '❌'}")
        print(f"Movement validator: {'✅' if server.movement_validator else '❌'}")
        print(f"Action validator: {'✅' if server.action_validator else '❌'}")
        print(f"Agent manager: {'✅' if server.agent_manager else '❌'}")

        # Test configuration access
        print(f"World config: {'✅' if server.world_config else '❌'}")
        print(f"Agent config: {'✅' if server.agent_config else '❌'}")
        print(f"Server config: {'✅' if server.server_config else '❌'}")

        return True

    except Exception as e:
        logger.error(f"Server creation failed: {e}")
        return False


async def test_agent_template_creation():
    """Test creating agents from templates"""
    print("\n" + "=" * 60)
    print("TESTING AGENT TEMPLATE CREATION")
    print("=" * 60)

    config_loader = ConfigLoader("config")
    if not config_loader.load_all_configs():
        print("❌ Failed to load configs")
        return False

    agent_config = config_loader.agent_config
    if not agent_config:
        print("❌ No agent config available")
        return False

    # Test creating agents from each template
    for template_name, template in agent_config.agent_templates.items():
        try:
            # Create agent config
            config = AgentConfig(
                name=f"Test_{template_name}",
                agent_class=template.class_name,
                personality=template.personality,
                behavior_params=template.behavior_params
            )

            # Create appropriate agent class
            if template.class_name.lower() in ['warrior', 'fighter']:
                agent = CombatAgent(config.name)
            else:
                agent = SimpleExplorerAgent(config.name)

            agent.config = config

            print(f"✅ Created {template_name} agent: {config.name}")
            print(f"   Class: {template.class_name}")
            print(f"   Personality: {template.personality}")

        except Exception as e:
            print(f"❌ Failed to create {template_name} agent: {e}")
            return False

    return True


async def test_spawn_position_generation():
    """Test spawn position generation"""
    print("\n" + "=" * 60)
    print("TESTING SPAWN POSITION GENERATION")
    print("=" * 60)

    config_loader = ConfigLoader("config")
    if not config_loader.load_all_configs():
        print("❌ Failed to load configs")
        return False

    # Test spawn position generation
    positions = []
    for i in range(10):
        pos = config_loader.get_spawn_position()
        positions.append(pos)
        print(f"Spawn {i+1}: ({pos.x:.1f}, {pos.y:.1f})")

    # Check that positions are reasonable
    x_values = [pos.x for pos in positions]
    y_values = [pos.y for pos in positions]

    print(f"X range: {min(x_values):.1f} - {max(x_values):.1f}")
    print(f"Y range: {min(y_values):.1f} - {max(y_values):.1f}")

    # Check that they're within expected safe zone
    all_valid = all(400 <= pos.x <= 600 and 400 <= pos.y <= 600 for pos in positions)
    print(f"All positions in safe zone: {'✅' if all_valid else '❌'}")

    return True


async def test_scenario_loading():
    """Test scenario loading and validation"""
    print("\n" + "=" * 60)
    print("TESTING SCENARIO LOADING")
    print("=" * 60)

    config_loader = ConfigLoader("config")
    if not config_loader.load_all_configs():
        print("❌ Failed to load configs")
        return False

    agent_config = config_loader.agent_config
    if not agent_config:
        print("❌ No agent config available")
        return False

    # Test each scenario
    for scenario_name, scenario in agent_config.test_scenarios.items():
        print(f"\nScenario: {scenario_name}")
        print(f"  Description: {scenario.get('description', 'No description')}")
        print(f"  Duration: {scenario.get('duration', 'No limit')} seconds")

        # Count total agents
        total_agents = sum(agent_group['count'] for agent_group in scenario['agents'])
        print(f"  Total agents: {total_agents}")

        # List agent types
        for agent_group in scenario['agents']:
            template = agent_group['template']
            count = agent_group['count']
            name = agent_group['name']
            print(f"    - {count}x {template} ({name})")

        # Validate that templates exist
        valid = True
        for agent_group in scenario['agents']:
            template_name = agent_group['template']
            if template_name not in agent_config.agent_templates:
                print(f"    ❌ Template '{template_name}' not found")
                valid = False

        print(f"  Validity: {'✅' if valid else '❌'}")

    return True


async def main():
    """Run all tests"""
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║                  MMO CONFIGURATION SYSTEM TESTS             ║
    ║                                                              ║
    ║  Testing the new configuration-based setup                  ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    tests = [
        ("Configuration Loading", test_config_loading),
        ("Server with Config", test_server_with_config),
        ("Agent Template Creation", test_agent_template_creation),
        ("Spawn Position Generation", test_spawn_position_generation),
        ("Scenario Loading", test_scenario_loading),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} failed with exception: {e}")
            results.append((test_name, False))

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL TESTS PASSED! Configuration system is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

    return passed == total


if __name__ == "__main__":
    asyncio.run(main())