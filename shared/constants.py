"""
Shared game constants
"""

# Network settings
DEFAULT_SERVER_HOST = "127.0.0.1"
DEFAULT_SERVER_PORT = 5555
MAX_CLIENTS = 100
CLIENT_TIMEOUT = 30.0  # Seconds before client is considered disconnected
PLAYER_TIMEOUT = 30.0  # Seconds of no updates before player goes inactive
HEARTBEAT_INTERVAL = 5.0  # How often clients should send heartbeats

# Game settings
WORLD_WIDTH = 10000.0
WORLD_HEIGHT = 10000.0
DEFAULT_VISION_RANGE = 100.0
MAX_VISION_RANGE = 500.0

# Update rates
SERVER_TICK_RATE = 60  # Hz
WORLD_UPDATE_RATE = 10  # Hz - How often to send world updates to clients
AGENT_DECISION_RATE = 2  # Hz - How often agents make decisions

# Movement
DEFAULT_MOVE_SPEED = 50.0  # Units per second
RUN_SPEED_MULTIPLIER = 2.0
MAX_MOVE_SPEED = 200.0  # Anti-cheat limit

# Combat
DEFAULT_ATTACK_RANGE = 5.0
DEFAULT_ATTACK_COOLDOWN = 1.0  # Seconds
DEFAULT_RESPAWN_TIME = 30.0  # Seconds

# Rate limiting
ACTIONS_PER_SECOND = 10  # Max actions per client per second
RATE_LIMIT_WINDOW = 1.0  # Rolling window in seconds
RATE_LIMIT_BURST = 15  # Allow burst of actions

# View distances for different entity types
ENTITY_VIEW_DISTANCES = {
    'agent': 150.0,
    'npc': 100.0,
    'enemy': 120.0,
    'object': 80.0,
    'item': 50.0,
    'effect': 200.0  # Visual effects visible from far
}

# Information levels (what clients can see about entities)
INFO_LEVEL_FULL = "full"  # Own agent
INFO_LEVEL_DETAILED = "detailed"  # Party members
INFO_LEVEL_BASIC = "basic"  # Other agents
INFO_LEVEL_MINIMAL = "minimal"  # Enemies

# Message size limits
MAX_MESSAGE_SIZE = 65536  # 64KB
MAX_CHAT_LENGTH = 256

# Database/persistence
SAVE_INTERVAL = 60.0  # Seconds between auto-saves
SNAPSHOT_INTERVAL = 300.0  # Seconds between full world snapshots