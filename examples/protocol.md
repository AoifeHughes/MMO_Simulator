# MMO Client-Server Protocol Documentation

## Overview

The MMO system uses a TCP-based JSON protocol for communication between clients (agents) and the authoritative server. This document describes the protocol for developing agents in any language.

## Connection Flow

1. **Connect**: Client opens TCP connection to server
2. **Authenticate**: Client sends CONNECT message with agent details
3. **Welcome**: Server responds with WELCOME and initial world state
4. **Game Loop**: Client sends actions, receives world updates and events
5. **Disconnect**: Client or server closes connection

## Message Format

All messages are JSON objects followed by a newline character (`\n`):

```json
{
    "type": "MESSAGE_TYPE",
    "timestamp": 1234567890.123,
    "sequence": 42,
    ... // Additional fields based on message type
}
```

## Message Types

### Client → Server

#### CONNECT
Initiate connection and authenticate:
```json
{
    "type": "CONNECT",
    "agent_name": "MyAgent",
    "agent_class": "Warrior",
    "version": "1.0.0"
}
```

#### ACTION
Perform an action in the game:
```json
{
    "type": "ACTION",
    "action": "MOVE|ATTACK|INTERACT|USE_ABILITY|CHAT",
    "data": {
        // Action-specific data
    },
    "agent_id": "agent_123"
}
```

**Action Types:**
- `MOVE`: Move to position
  ```json
  {"target": [100, 200], "speed": "walk|run|sneak"}
  ```
- `ATTACK`: Attack target entity
  ```json
  {"target_id": "entity_456"}
  ```
- `INTERACT`: Interact with entity/object
  ```json
  {"target_id": "npc_789"}
  ```
- `CHAT`: Send chat message
  ```json
  {"message": "Hello world!", "channel": "local|global"}
  ```

#### QUERY
Request information from server:
```json
{
    "type": "QUERY",
    "query": "GET_STATS|GET_SURROUNDINGS|GET_ENTITY_INFO",
    "params": {
        // Query-specific parameters
    },
    "agent_id": "agent_123"
}
```

#### HEARTBEAT
Keep connection alive:
```json
{
    "type": "HEARTBEAT"
}
```

### Server → Client

#### WELCOME
Response to successful connection:
```json
{
    "type": "WELCOME",
    "agent_id": "agent_123",
    "server_version": "1.0.0",
    "world_info": {
        "width": 10000,
        "height": 10000,
        "tick_rate": 60
    },
    "initial_position": [500, 500],
    "vision_range": 100.0
}
```

#### WORLD_UPDATE
Regular world state updates:
```json
{
    "type": "WORLD_UPDATE",
    "tick": 12345,
    "visible_entities": [
        {
            "id": "entity_456",
            "name": "Goblin",
            "entity_type": "enemy",
            "position": [450, 480],
            "health_percentage": 75.0,
            "level": 3,
            "state": "moving",
            "velocity": [1.0, 0.5]
        }
    ],
    "removed_entities": ["entity_789"]
}
```

#### ACTION_RESULT
Response to action requests:
```json
{
    "type": "ACTION_RESULT",
    "action": "MOVE",
    "success": true,
    "result": {
        "target": [100, 200],
        "speed": 50.0,
        "eta": 2.5
    },
    "error_message": null
}
```

#### EVENT
Broadcast events:
```json
{
    "type": "EVENT",
    "event": "COMBAT|CHAT|DEATH|LEVEL_UP",
    "data": {
        // Event-specific data
    },
    "position": [100, 200]  // Optional
}
```

#### ERROR
Error messages:
```json
{
    "type": "ERROR",
    "error": "Rate limit exceeded"
}
```

## Information Exposure

### What Clients Can See
- Entities within vision range (default 100 units)
- Health as percentage, not exact values
- Public entity states (idle, moving, combat)
- Recent events in range (combat, chat)

### What Clients Cannot See
- Exact stats of other entities
- Entities outside vision range
- Internal server calculations
- Other agents' decision-making

## Rate Limiting

- Maximum 10 actions per second per client
- Burst allowance of 15 actions
- Violating clients receive ERROR messages

## Example Agent (Python)

```python
import asyncio
import json
import logging

class SimpleAgent:
    def __init__(self, name):
        self.name = name
        self.reader = None
        self.writer = None

    async def connect(self, host="127.0.0.1", port=5555):
        self.reader, self.writer = await asyncio.open_connection(host, port)

        # Send connect message
        connect_msg = {
            "type": "CONNECT",
            "agent_name": self.name,
            "agent_class": "Explorer"
        }
        await self.send(connect_msg)

        # Wait for welcome
        welcome = await self.receive()
        if welcome["type"] == "WELCOME":
            self.agent_id = welcome["agent_id"]
            return True
        return False

    async def send(self, message):
        data = json.dumps(message) + "\n"
        self.writer.write(data.encode())
        await self.writer.drain()

    async def receive(self):
        data = await self.reader.readline()
        return json.loads(data.decode())

    async def move_to(self, x, y):
        action = {
            "type": "ACTION",
            "action": "MOVE",
            "data": {"target": [x, y], "speed": "walk"},
            "agent_id": self.agent_id
        }
        await self.send(action)
```

## Anti-Cheat Measures

- All movements validated for speed limits
- Actions checked for range and cooldowns
- Rate limiting prevents spam
- Server authoritative for all state changes

## Future Extensions

The protocol is designed to support:
- Additional action types
- More complex queries
- Plugin systems
- Cross-language agent development