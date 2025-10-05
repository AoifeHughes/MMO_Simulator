#!/usr/bin/env python3
"""
Database management CLI tool for MMO Simulator.

Usage:
    python manage_database.py list      # List all backup files
    python manage_database.py restore   # Restore most recent backup
    python manage_database.py cleanup   # Clean all database files
    python manage_database.py fresh     # Create fresh database
"""

import sys
import os

# Add the simulation framework to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from simulation_framework.src.utils.database_manager import DatabaseManager


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()
    manager = DatabaseManager()

    if command == "list":
        print("=== Database Files ===")
        db_path = manager.get_default_database_path()
        if os.path.exists(db_path):
            print(f"Current database: {db_path}")
        else:
            print("No current database found")

        print("\nBackup files:")
        manager.list_backups()

    elif command == "restore":
        backups = manager.get_backup_files()
        if not backups:
            print("No backup files found.")
            return

        # Restore the most recent backup
        most_recent = backups[0]
        print(f"Restoring most recent backup: {os.path.basename(most_recent)}")
        if manager.restore_backup(most_recent):
            print("✅ Restore successful!")
        else:
            print("❌ Restore failed!")

    elif command == "cleanup":
        print("⚠️  This will delete ALL simulation databases and backups!")
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            manager.cleanup_all_files()
            print("✅ All databases cleaned up!")
        else:
            print("❌ Cleanup cancelled.")

    elif command == "fresh":
        db_path = manager.create_fresh_database(cleanup_old=True)
        print(f"✅ Fresh database ready at: {db_path}")

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()