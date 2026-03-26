from typing import Any

from fastapi import HTTPException, status

from src.app.application.dtos import (
    ConversationCreatePayload,
    CurrentUser,
    GroupConversationCreatePayload,
    MessageCreatePayload,
)
from src.app.domain.serializers import (
    serialize_conversation,
    serialize_message,
    serialize_object_id,
)
from src.app.infra.gateways import MentorGateway
from src.app.infra.realtime import RealtimeConnectionManager
from src.app.infra.repositories import (
    ConversationRepository,
    MessageRepository,
    build_message_attachments,
)


class ChatService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        mentor_gateway: MentorGateway,
        realtime: RealtimeConnectionManager,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._mentor_gateway = mentor_gateway
        self._realtime = realtime

    async def list_conversations(self, user: CurrentUser) -> list[dict[str, Any]]:
        if user.role == "mentor":
            links = await self._mentor_gateway.verify_mentor_intern_links(user.token)
            items = await self._conversations.list_for_mentor(
                mentor_id=user.id,
                allowed_intern_ids=[item["intern_id"] for item in links],
            )
        else:
            items = await self._conversations.list_for_participant(user.id)
        return [serialize_conversation(item) for item in items]

    async def create_or_get_direct_conversation(
        self,
        payload: ConversationCreatePayload,
        user: CurrentUser,
    ) -> dict[str, Any]:
        if user.role == "mentor":
            mentor_id = user.id
            intern_id = payload.intern_id
            linked_intern_ids = {
                item["intern_id"]
                for item in await self._mentor_gateway.verify_mentor_intern_links(user.token)
            }
            if intern_id not in linked_intern_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Intern is not assigned to mentor",
                )
        elif user.role == "intern":
            link = await self._mentor_gateway.verify_my_mentor(user.token)
            mentor_id = link.get("mentor_id")
            intern_id = user.id
            if payload.intern_id and payload.intern_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Intern can create only own chat with mentor",
                )
            if not mentor_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Mentor is not assigned for this intern",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only mentor or intern can create conversations",
            )

        direct_key = f"{mentor_id}:{intern_id}"
        existing = await self._conversations.get_by_direct_key(direct_key)
        conversation = existing or await self._conversations.create_direct(
            mentor_id=mentor_id,
            intern_id=intern_id,
            created_by=user.id,
        )
        serialized = serialize_conversation(conversation)
        await self._notify_conversation_update(conversation)
        return serialized

    async def create_group_conversation(
        self,
        payload: GroupConversationCreatePayload,
        user: CurrentUser,
    ) -> dict[str, Any]:
        if user.role != "mentor":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only mentor can create group chat",
            )

        intern_ids = sorted(set(payload.intern_ids))
        if not payload.title.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Title is required",
            )
        if not intern_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Choose at least one intern",
            )

        linked_intern_ids = {
            item["intern_id"]
            for item in await self._mentor_gateway.verify_mentor_intern_links(user.token)
        }
        if not set(intern_ids).issubset(linked_intern_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Some interns are not assigned to mentor",
            )

        conversation = await self._conversations.create_group(
            mentor_id=user.id,
            intern_ids=intern_ids,
            title=payload.title.strip(),
            created_by=user.id,
        )
        serialized = serialize_conversation(conversation)
        await self._notify_conversation_update(conversation)
        return serialized

    async def ensure_access_to_conversation(
        self,
        conversation_id: str,
        user: CurrentUser,
    ) -> dict[str, Any]:
        conversation = await self._conversations.get_by_id(conversation_id)
        if user.id not in conversation.get("participant_ids", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to conversation",
            )
        return conversation

    async def list_messages(
        self,
        conversation_id: str,
        user: CurrentUser,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        conversation = await self.ensure_access_to_conversation(conversation_id, user)
        items = await self._messages.list_for_conversation(
            conversation_id=serialize_object_id(conversation["_id"]),
            limit=limit,
        )
        return [serialize_message(item) for item in items]

    async def send_message(
        self,
        conversation_id: str,
        payload: MessageCreatePayload,
        user: CurrentUser,
    ) -> dict[str, Any]:
        conversation = await self.ensure_access_to_conversation(conversation_id, user)

        content = payload.content.strip()
        if not content and not payload.attachments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty",
            )

        message = await self._messages.create_message(
            conversation_id=serialize_object_id(conversation["_id"]),
            sender_id=user.id,
            content=content,
            attachments=build_message_attachments(payload.attachments),
        )
        preview = content or (
            f"Файл: {payload.attachments[0].file_name}"
            if payload.attachments
            else ""
        )
        updated_conversation = await self._conversations.update_last_message(
            conversation_id=serialize_object_id(conversation["_id"]),
            preview=preview,
            updated_at=message["created_at"],
        )

        serialized_message = serialize_message(message)
        await self._realtime.broadcast_to_conversation(
            serialize_object_id(conversation["_id"]),
            {"type": "message.created", "data": serialized_message},
        )
        await self._notify_conversation_update(updated_conversation)
        return serialized_message

    async def _notify_conversation_update(self, conversation: dict[str, Any]) -> None:
        await self._realtime.broadcast_to_users(
            conversation.get("participant_ids", []),
            {
                "type": "conversation.updated",
                "data": serialize_conversation(conversation),
            },
        )
