"""
Player data persistence system
"""

import json
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import asdict
import logging

from server.core.game_state import ServerEntity, GameState
from shared.math_utils import Vector2

logger = logging.getLogger(__name__)


class PlayerPersistence:
    """Handles saving and loading player data"""

    def __init__(self, save_directory: str = "output/persistence"):
        self.save_directory = save_directory
        self.player_data_file = os.path.join(save_directory, "player_data.json")
        self.world_state_file = os.path.join(save_directory, "world_state.json")

        # Ensure directory exists
        os.makedirs(save_directory, exist_ok=True)

        logger.info(f"PlayerPersistence initialized with directory: {save_directory}")

    def save_player_data(self, game_state: GameState) -> bool:
        """Save all player data to file"""
        try:
            player_data = {}
            world_data = {}

            # Save all agents (both active and inactive)
            for entity in game_state.entities.values():
                if entity.entity_type == 'agent':
                    player_data[entity.id] = {
                        'id': entity.id,
                        'name': entity.name,
                        'entity_type': entity.entity_type,
                        'position': [entity.position.x, entity.position.y],
                        'velocity': [entity.velocity.x, entity.velocity.y],
                        'health': entity.health,
                        'max_health': entity.max_health,
                        'level': entity.level,
                        'state': entity.state,
                        'alive': entity.alive,
                        'is_active': entity.is_active,
                        'last_update_time': entity.last_update_time,
                        'owner_id': entity.owner_id,
                        'data': entity.data,
                        'vision_range': entity.vision_range
                    }

            # Save world metadata
            world_data = {
                'tick': game_state.tick,
                'server_time': game_state.server_time,
                'stats': game_state.stats,
                'agents_mapping': game_state.agents,  # client_id -> entity_id mapping
                'save_timestamp': time.time()
            }

            # Write player data
            with open(self.player_data_file, 'w') as f:
                json.dump(player_data, f, indent=2)

            # Write world state
            with open(self.world_state_file, 'w') as f:
                json.dump(world_data, f, indent=2)

            logger.info(f"Saved {len(player_data)} players to {self.player_data_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save player data: {e}")
            return False

    def load_player_data(self, game_state: GameState) -> bool:
        """Load player data from file and restore to game state"""
        try:
            if not os.path.exists(self.player_data_file):
                logger.info("No saved player data found")
                return False

            if not os.path.exists(self.world_state_file):
                logger.info("No saved world state found")
                return False

            # Load player data
            with open(self.player_data_file, 'r') as f:
                player_data = json.load(f)

            # Load world state
            with open(self.world_state_file, 'r') as f:
                world_data = json.load(f)

            # Restore players
            restored_count = 0
            for entity_id, data in player_data.items():
                try:
                    # Create entity with saved data
                    entity = game_state.create_entity(
                        id=data['id'],
                        name=data['name'],
                        entity_type=data['entity_type'],
                        position=Vector2(data['position'][0], data['position'][1]),
                        velocity=Vector2(data['velocity'][0], data['velocity'][1]),
                        health=data['health'],
                        max_health=data['max_health'],
                        level=data['level'],
                        state=data['state'],
                        alive=data['alive'],
                        owner_id=data.get('owner_id'),
                        data=data.get('data', {}),
                        vision_range=data.get('vision_range', 100.0)
                    )

                    # Set persistence-specific fields
                    entity.is_active = data['is_active']
                    entity.last_update_time = data['last_update_time']

                    # Remove the entity that was auto-created by game_state.create_entity()
                    # since we want to use our saved ID
                    if entity.id != entity_id:
                        game_state.destroy_entity(entity.id)
                        entity.id = entity_id
                        game_state.entities[entity_id] = entity
                        game_state.spatial_grid.insert(entity_id, entity.position, entity.vision_range)

                    restored_count += 1

                except Exception as e:
                    logger.error(f"Failed to restore player {entity_id}: {e}")

            # Restore world state
            if 'agents_mapping' in world_data:
                game_state.agents.update(world_data['agents_mapping'])

            if 'stats' in world_data:
                game_state.stats.update(world_data['stats'])

            # Note: We don't restore tick/server_time as server should continue from current time

            logger.info(f"Restored {restored_count} players from save file")
            logger.info(f"Save timestamp: {time.ctime(world_data.get('save_timestamp', 0))}")

            return restored_count > 0

        except Exception as e:
            logger.error(f"Failed to load player data: {e}")
            return False

    def has_saved_data(self) -> bool:
        """Check if saved player data exists"""
        return os.path.exists(self.player_data_file) and os.path.exists(self.world_state_file)

    def get_save_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the saved data"""
        try:
            if not self.has_saved_data():
                return None

            with open(self.world_state_file, 'r') as f:
                world_data = json.load(f)

            with open(self.player_data_file, 'r') as f:
                player_data = json.load(f)

            active_players = sum(1 for p in player_data.values() if p.get('is_active', False))
            inactive_players = sum(1 for p in player_data.values() if not p.get('is_active', True))

            return {
                'save_timestamp': world_data.get('save_timestamp', 0),
                'total_players': len(player_data),
                'active_players': active_players,
                'inactive_players': inactive_players,
                'last_tick': world_data.get('tick', 0),
                'save_time_str': time.ctime(world_data.get('save_timestamp', 0))
            }

        except Exception as e:
            logger.error(f"Failed to get save info: {e}")
            return None

    def clear_saved_data(self):
        """Clear all saved data"""
        try:
            if os.path.exists(self.player_data_file):
                os.remove(self.player_data_file)
            if os.path.exists(self.world_state_file):
                os.remove(self.world_state_file)
            logger.info("Cleared saved player data")
        except Exception as e:
            logger.error(f"Failed to clear saved data: {e}")

    def auto_save(self, game_state: GameState, interval_seconds: float = 30.0):
        """Auto-save player data at regular intervals"""
        # This would be called periodically by the server
        # For now, just save immediately
        return self.save_player_data(game_state)