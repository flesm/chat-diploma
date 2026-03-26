from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class RealtimeConnectionManager:
    def __init__(self) -> None:
        self._user_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._conversation_connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect_user(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._user_connections[user_id].add(websocket)

    def disconnect_user(self, user_id: str, websocket: WebSocket) -> None:
        self._user_connections[user_id].discard(websocket)
        if not self._user_connections[user_id]:
            self._user_connections.pop(user_id, None)

    async def connect_conversation(
        self,
        conversation_id: str,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()
        self._conversation_connections[conversation_id].add(websocket)

    def disconnect_conversation(
        self,
        conversation_id: str,
        websocket: WebSocket,
    ) -> None:
        self._conversation_connections[conversation_id].discard(websocket)
        if not self._conversation_connections[conversation_id]:
            self._conversation_connections.pop(conversation_id, None)

    async def broadcast_to_users(
        self,
        user_ids: list[str],
        payload: dict[str, Any],
    ) -> None:
        for user_id in user_ids:
            for websocket in list(self._user_connections.get(user_id, set())):
                await websocket.send_json(payload)

    async def broadcast_to_conversation(
        self,
        conversation_id: str,
        payload: dict[str, Any],
    ) -> None:
        for websocket in list(self._conversation_connections.get(conversation_id, set())):
            await websocket.send_json(payload)
