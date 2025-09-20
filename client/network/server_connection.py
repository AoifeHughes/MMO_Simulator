"""
Client connection to server
"""

import asyncio
import logging
from typing import Optional

from shared.messages import Message, Protocol

logger = logging.getLogger(__name__)


class ServerConnection:
    """Handles connection to the game server"""

    def __init__(self):
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False

    async def connect(self, host: str, port: int):
        """Connect to the server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(host, port)
            self.connected = True
            logger.info(f"Connected to {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to {host}:{port}: {e}")
            raise

    async def disconnect(self):
        """Disconnect from server"""
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.connected = False
        logger.info("Disconnected from server")

    async def send(self, message: Message):
        """Send message to server"""
        if not self.connected or not self.writer:
            raise RuntimeError("Not connected to server")

        try:
            data = Protocol.encode_message(message)
            self.writer.write(data)
            await self.writer.drain()
            logger.debug(f"Sent: {message.type.value}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.connected = False
            raise

    async def receive(self) -> Optional[Message]:
        """Receive message from server"""
        if not self.connected or not self.reader:
            return None

        try:
            data = await self.reader.readline()
            if not data:
                self.connected = False
                return None

            message = Protocol.decode_message(data.strip())
            if message:
                logger.debug(f"Received: {message.type.value}")
            return message

        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            self.connected = False
            return None