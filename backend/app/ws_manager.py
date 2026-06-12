"""WebSocket connection manager — handles client connections and broadcasting.

Maintains a set of active WebSocket connections and provides broadcast
methods for pushing real-time events (score updates, new alerts, stats)
to all connected dashboard clients.
"""
from __future__ import annotations
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    """Manages WebSocket connections and broadcasts events to all clients."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and add it to the pool."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(f"WebSocket client connected ({len(self._connections)} total)")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the pool."""
        self._connections.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(self._connections)} remaining)")

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast a JSON event to all connected clients.

        Args:
            event_type: Machine-readable event type (e.g. 'score_update',
                       'new_alert', 'stats_update').
            data: Serializable payload dict.
        """
        payload = json.dumps({"type": event_type, "data": data}, default=str)
        stale = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.add(ws)
        # Clean up any dead connections
        for ws in stale:
            self._connections.discard(ws)

    @property
    def count(self) -> int:
        """Number of currently connected clients."""
        return len(self._connections)
