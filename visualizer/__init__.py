"""
Pygame-based visualization system for the MMO Simulator.

This module provides real-time visualization capabilities for simulation runs,
including interactive features like panning, zooming, and agent inspection.
"""

try:
    from .pygame_visualizer import GameVisualizer, Camera
    from .ui import UIManager, InfoPanel, HUD, Button

    __all__ = [
        'GameVisualizer',
        'Camera',
        'UIManager',
        'InfoPanel',
        'HUD',
        'Button'
    ]

    PYGAME_AVAILABLE = True

except ImportError:
    # pygame not available, provide graceful fallback
    GameVisualizer = None
    Camera = None
    UIManager = None
    InfoPanel = None
    HUD = None
    Button = None

    __all__ = []

    PYGAME_AVAILABLE = False

__version__ = "1.0.0"