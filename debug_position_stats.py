#!/usr/bin/env python3
"""
Debug Position Statistics Reporter

This script can be used to print position statistics during or after simulation runs.
"""

import sys
import time
from shared.position_stats import print_stats_report, get_summary_stats, get_agent_stats

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "json":
            # Output JSON format for programmatic consumption
            import json
            stats = get_summary_stats()
            print(json.dumps(stats, indent=2))
        elif sys.argv[1].startswith("agent:"):
            # Get stats for specific agent
            agent_id = sys.argv[1].split(":", 1)[1]
            agent_stats = get_agent_stats(agent_id)
            import json
            print(json.dumps(agent_stats, indent=2))
        else:
            print("Usage: python debug_position_stats.py [json|agent:AGENT_ID]")
            sys.exit(1)
    else:
        # Default: Print human-readable report
        print_stats_report()

if __name__ == "__main__":
    main()