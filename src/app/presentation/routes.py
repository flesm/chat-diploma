from typing import Any

from fastapi import APIRouter, Depends

from src.app.application.dtos import (
    ConversationCreatePayload,
    CurrentUser,
    GroupConversationCreatePayload,
    MessageCreatePayload,
)
from src.app.application.services import ChatService
from src.app.presentation.dependencies import get_chat_service, get_current_user

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    return {"message": "Chat service is running"}


@router.get("/api/v1/conversations")
async def list_conversations(
    user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[dict[str, Any]]:
    return await chat_service.list_conversations(user)


@router.post("/api/v1/conversations/direct")
async def create_or_get_direct_conversation(
    payload: ConversationCreatePayload,
    user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    return await chat_service.create_or_get_direct_conversation(payload, user)


@router.post("/api/v1/conversations/group")
async def create_group_conversation(
    payload: GroupConversationCreatePayload,
    user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    return await chat_service.create_group_conversation(payload, user)


@router.get("/api/v1/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    limit: int = 100,
    user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[dict[str, Any]]:
    return await chat_service.list_messages(conversation_id, user, limit)


@router.post("/api/v1/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: MessageCreatePayload,
    user: CurrentUser = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    return await chat_service.send_message(conversation_id, payload, user)
