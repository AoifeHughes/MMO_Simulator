"""
Database management utilities for MMO Simulator.
Handles automatic database creation, cleanup, and rotation.
"""

import glob
import os
import time
from pathlib import Path
from typing import Optional


class DatabaseManager:
    """Manages simulation database lifecycle"""

    def __init__(self, base_path: str = None):
        """
        Initialize database manager.

        Args:
            base_path: Base directory for databases (defaults to project root)
        """
        if base_path is None:
            # Default to project root directory
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent
            self.base_path = project_root
        else:
            self.base_path = Path(base_path)

        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_default_database_path(self) -> str:
        """Get the default database path (simulation_data.db)"""
        return str(self.base_path / "simulation_data.db")

    def create_fresh_database(self, cleanup_old: bool = True) -> str:
        """
        Create a fresh database, optionally cleaning up the old one.

        Args:
            cleanup_old: If True, backup/delete existing database

        Returns:
            Path to the new database
        """
        db_path = self.get_default_database_path()

        if cleanup_old and os.path.exists(db_path):
            self._backup_existing_database(db_path)

        # Remove existing database if it exists
        if os.path.exists(db_path):
            os.remove(db_path)

        print(f"Created fresh database: {db_path}")
        return db_path

    def _backup_existing_database(self, db_path: str) -> Optional[str]:
        """
        Backup existing database with timestamp.

        Args:
            db_path: Path to existing database

        Returns:
            Path to backup file, or None if backup failed
        """
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = f"{db_path}.backup_{timestamp}"

            # Copy the existing database to backup
            import shutil

            shutil.copy2(db_path, backup_path)

            print(f"Backed up previous database to: {backup_path}")

            # Keep only the last 5 backups to prevent disk space issues
            self._cleanup_old_backups(db_path)

            return backup_path

        except Exception as e:
            print(f"Warning: Could not backup database: {e}")
            return None

    def _cleanup_old_backups(self, db_path: str, keep_count: int = 5):
        """Keep only the most recent backup files"""
        try:
            backup_pattern = f"{db_path}.backup_*"
            backup_files = glob.glob(backup_pattern)

            if len(backup_files) > keep_count:
                # Sort by modification time (newest first)
                backup_files.sort(key=os.path.getmtime, reverse=True)

                # Remove older backups
                for old_backup in backup_files[keep_count:]:
                    os.remove(old_backup)
                    print(f"Cleaned up old backup: {os.path.basename(old_backup)}")

        except Exception as e:
            print(f"Warning: Could not cleanup old backups: {e}")

    def get_backup_files(self) -> list[str]:
        """Get list of available backup files"""
        db_path = self.get_default_database_path()
        backup_pattern = f"{db_path}.backup_*"
        backup_files = glob.glob(backup_pattern)
        backup_files.sort(key=os.path.getmtime, reverse=True)
        return backup_files

    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore a specific backup as the current database.

        Args:
            backup_path: Path to backup file to restore

        Returns:
            True if successful, False otherwise
        """
        try:
            db_path = self.get_default_database_path()

            if not os.path.exists(backup_path):
                print(f"Backup file not found: {backup_path}")
                return False

            # Backup current database if it exists
            if os.path.exists(db_path):
                self._backup_existing_database(db_path)

            # Copy backup to current location
            import shutil

            shutil.copy2(backup_path, db_path)

            print(f"Restored database from backup: {backup_path}")
            return True

        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False

    def list_backups(self):
        """Print available backup files with timestamps"""
        backups = self.get_backup_files()

        if not backups:
            print("No backup files found.")
            return

        print("Available backup files:")
        for backup in backups:
            basename = os.path.basename(backup)
            timestamp = os.path.getmtime(backup)
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
            print(f"  {basename} (created: {time_str})")

    def cleanup_all_files(self):
        """Remove all database and backup files (use with caution!)"""
        try:
            db_path = self.get_default_database_path()

            # Remove main database
            if os.path.exists(db_path):
                os.remove(db_path)
                print(f"Removed: {db_path}")

            # Remove all backups
            backups = self.get_backup_files()
            for backup in backups:
                os.remove(backup)
                print(f"Removed: {backup}")

            print("All simulation databases cleaned up.")

        except Exception as e:
            print(f"Error during cleanup: {e}")


def get_database_path(auto_cleanup: bool = True) -> str:
    """
    Convenience function to get a fresh database path.

    Args:
        auto_cleanup: If True, backup and remove existing database

    Returns:
        Path to database file
    """
    manager = DatabaseManager()
    return manager.create_fresh_database(cleanup_old=auto_cleanup)


def list_database_backups():
    """Convenience function to list available backups"""
    manager = DatabaseManager()
    manager.list_backups()


def restore_database_backup(backup_path: str = None):
    """
    Convenience function to restore a backup.

    Args:
        backup_path: Specific backup to restore, or None to show options
    """
    manager = DatabaseManager()

    if backup_path is None:
        print("Available backups:")
        manager.list_backups()
        return

    return manager.restore_backup(backup_path)


if __name__ == "__main__":
    # CLI interface for database management
    import sys

    if len(sys.argv) < 2:
        print("Database Manager Commands:")
        print("  python database_manager.py create    - Create fresh database")
        print("  python database_manager.py list      - List backup files")
        print("  python database_manager.py restore <backup> - Restore backup")
        print("  python database_manager.py cleanup   - Remove all database files")
        sys.exit(1)

    command = sys.argv[1]
    manager = DatabaseManager()

    if command == "create":
        path = manager.create_fresh_database()
        print(f"Fresh database ready at: {path}")
    elif command == "list":
        manager.list_backups()
    elif command == "restore" and len(sys.argv) > 2:
        manager.restore_backup(sys.argv[2])
    elif command == "cleanup":
        confirm = input(
            "This will delete ALL simulation databases. Continue? (yes/no): "
        )
        if confirm.lower() == "yes":
            manager.cleanup_all_files()
        else:
            print("Cleanup cancelled.")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
