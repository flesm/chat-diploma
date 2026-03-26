from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.app.application.dtos import MessageCreatePayload, WebSocketMessagePayload
from src.app.presentation.dependencies import get_current_websocket_user

router = APIRouter()


@router.websocket("/ws/updates")
async def updates_socket(websocket: WebSocket) -> None:
    try:
        user = await get_current_websocket_user(websocket)
    except Exception:
        await websocket.close(code=4401)
        return

    manager = websocket.app.state.realtime_manager
    await manager.connect_user(user.id, websocket)
    await websocket.send_json({"type": "connection.ready", "scope": "user"})

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect_user(user.id, websocket)


@router.websocket("/ws/conversations/{conversation_id}")
async def conversation_socket(
    websocket: WebSocket,
    conversation_id: str,
) -> None:
    try:
        user = await get_current_websocket_user(websocket)
        service = websocket.app.state.chat_service
        await service.ensure_access_to_conversation(conversation_id, user)
    except Exception:
        await websocket.close(code=4403)
        return

    manager = websocket.app.state.realtime_manager
    await manager.connect_conversation(conversation_id, websocket)
    await websocket.send_json(
        {
            "type": "connection.ready",
            "scope": "conversation",
            "conversation_id": conversation_id,
        }
    )

    try:
        while True:
            payload = WebSocketMessagePayload(**await websocket.receive_json())
            if payload.action != "message.send":
                await websocket.send_json(
                    {"type": "error", "detail": "Unsupported websocket action"}
                )
                continue

            await service.send_message(
                conversation_id=conversation_id,
                payload=MessageCreatePayload(
                    content=payload.content,
                    attachments=payload.attachments,
                ),
                user=user,
            )
    except WebSocketDisconnect:
        manager.disconnect_conversation(conversation_id, websocket)
