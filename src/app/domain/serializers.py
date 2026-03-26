from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_object_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return str(value)


def serialize_message(message: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": serialize_object_id(message["_id"]),
        "conversation_id": message["conversation_id"],
        "sender_id": message["sender_id"],
        "content": message.get("content", ""),
        "attachments": message.get("attachments", []),
        "created_at": message["created_at"].isoformat(),
    }


def serialize_conversation(conversation: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": serialize_object_id(conversation["_id"]),
        "type": conversation["type"],
        "title": conversation.get("title"),
        "mentor_id": conversation["mentor_id"],
        "intern_ids": conversation.get("intern_ids", []),
        "participant_ids": conversation.get("participant_ids", []),
        "last_message_preview": conversation.get("last_message_preview", ""),
        "last_message_at": (
            conversation["last_message_at"].isoformat()
            if conversation.get("last_message_at")
            else None
        ),
        "created_at": conversation["created_at"].isoformat(),
        "updated_at": conversation["updated_at"].isoformat(),
    }
