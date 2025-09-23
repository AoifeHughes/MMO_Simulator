#!/usr/bin/env python3
import asyncio
import pygame
import sys
import logging
from main import SimulatorApp

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_scenario():
    print("Creating SimulatorApp...")
    app = SimulatorApp(mode='scenario', visualize=True, scenario='peaceful_village')

    print(f"Initial state - running: {app.running}")

    # Let's manually step through the setup
    app.running = True
    tasks = []

    print("Starting server...")
    server_task = await app.start_server()
    print(f"After start_server - running: {app.running}")
    if server_task:
        tasks.append(server_task)
        print("Server task added")

    print("Spawning scenario agents...")
    await app.spawn_scenario_agents()
    print(f"After spawn_scenario_agents - running: {app.running}")
    if app.agent_clients:
        agent_task = asyncio.create_task(app.run_agent_clients_loop())
        tasks.append(agent_task)
        print(f"Added agent task, total tasks: {len(tasks)}")

    print("Setting up visualization...")
    if app.visualize:
        print("Creating visualization task...")
        try:
            # Let's test renderer creation separately
            from visualizer.renderer import Renderer
            print("Testing renderer creation...")
            renderer = Renderer()
            print("Renderer created successfully!")
            renderer.cleanup()

            viz_task = asyncio.create_task(app.run_visualization())
            tasks.append(viz_task)
            print(f"Visualization task added, total tasks: {len(tasks)}")
        except Exception as e:
            print(f"Error creating visualization: {e}")
            import traceback
            traceback.print_exc()

    print(f"Final task count: {len(tasks)}")
    print(f"Running state: {app.running}")

    if tasks:
        print("Starting task execution...")
        try:
            # Run for just a few seconds to see what happens
            done, pending = await asyncio.wait(tasks, timeout=3.0, return_when=asyncio.FIRST_COMPLETED)
            print(f"Tasks completed: {len(done)}, pending: {len(pending)}")

            for task in done:
                if task.exception():
                    print(f"Task failed with exception: {task.exception()}")
                    import traceback
                    traceback.print_exception(type(task.exception()), task.exception(), task.exception().__traceback__)
        except Exception as e:
            print(f"Error in task execution: {e}")
            import traceback
            traceback.print_exc()

    print("Cleaning up...")
    await app.cleanup()

if __name__ == "__main__":
    asyncio.run(debug_scenario())