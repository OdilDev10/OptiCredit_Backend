"""SSE (Server-Sent Events) manager for real-time notifications."""

import asyncio
import json
from typing import Dict, Set
from uuid import UUID


class SSEManager:
    """Manager for SSE connections and broadcasting."""

    def __init__(self):
        self._connections: Dict[str, Set[asyncio.Queue]] = {}

    def connect(self, user_id: str) -> asyncio.Queue:
        """Add a new SSE connection for a user. Returns the queue for this connection."""
        if user_id not in self._connections:
            self._connections[user_id] = set()
        queue = asyncio.Queue(maxsize=100)
        self._connections[user_id].add(queue)
        return queue

    def disconnect(self, user_id: str, queue: asyncio.Queue) -> None:
        """Remove an SSE connection."""
        if user_id in self._connections:
            self._connections[user_id].discard(queue)
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def send_to_user(self, user_id: str, event_type: str, data: dict) -> None:
        """Send an SSE event to a specific user."""
        if user_id not in self._connections:
            return

        message = json.dumps(
            {
                "type": event_type,
                "data": data,
            }
        )

        disconnected = set()
        for queue in self._connections[user_id]:
            try:
                await queue.put(message)
            except Exception:
                disconnected.add(queue)

        for queue in disconnected:
            self._connections[user_id].discard(queue)

    async def broadcast(
        self, event_type: str, data: dict, user_ids: list[str] | None = None
    ) -> None:
        """Broadcast an event to all connected users or specific users."""
        if user_ids:
            for user_id in user_ids:
                await self.send_to_user(user_id, event_type, data)
        else:
            for user_id in list(self._connections.keys()):
                await self.send_to_user(user_id, event_type, data)

    @property
    def connected_users(self) -> int:
        """Get count of connected users."""
        return len(self._connections)


sse_manager = SSEManager()
