#!/usr/bin/env python3
"""
Run example client agents
"""

import asyncio
import sys

# Fix import paths
sys.path.append('.')

from examples.simple_agent import main

if __name__ == "__main__":
    print("Starting client agents - make sure server is running first!")
    asyncio.run(main())