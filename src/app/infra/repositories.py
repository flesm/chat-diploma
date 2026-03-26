from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.app.domain.serializers import serialize_object_id, utc_now


class ConversationRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def create_indexes(self) -> None:
        await self._db.conversations.create_index(
            [("participant_ids", 1), ("updated_at", -1)]
        )
        await self._db.conversations.create_index([("mentor_id", 1), ("type", 1)])
        await self._db.conversations.create_index("direct_key", unique=True, sparse=True)
        await self._db.messages.create_index([("conversation_id", 1), ("created_at", 1)])

    async def list_for_mentor(
        self,
        mentor_id: str,
        allowed_intern_ids: list[str],
    ) -> list[dict[str, Any]]:
        cursor = self._db.conversations.find(
            {
                "mentor_id": mentor_id,
                "$or": [
                    {"intern_ids": {"$size": 0}},
                    {"intern_ids": {"$in": allowed_intern_ids}},
                ],
            }
        ).sort("updated_at", -1)
        return await cursor.to_list(length=200)

    async def list_for_participant(self, user_id: str) -> list[dict[str, Any]]:
        cursor = self._db.conversations.find({"participant_ids": user_id}).sort(
            "updated_at", -1
        )
        return await cursor.to_list(length=200)

    async def get_by_id(self, conversation_id: str) -> dict[str, Any]:
        if not ObjectId.is_valid(conversation_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        conversation = await self._db.conversations.find_one(
            {"_id": ObjectId(conversation_id)}
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation

    async def get_by_direct_key(self, direct_key: str) -> dict[str, Any] | None:
        return await self._db.conversations.find_one({"direct_key": direct_key})

    async def create_direct(
        self,
        mentor_id: str,
        intern_id: str,
        created_by: str,
    ) -> dict[str, Any]:
        now = utc_now()
        document = {
            "type": "direct",
            "title": None,
            "mentor_id": mentor_id,
            "intern_ids": [intern_id],
            "participant_ids": [mentor_id, intern_id],
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            "last_message_preview": "",
            "last_message_at": None,
            "direct_key": f"{mentor_id}:{intern_id}",
        }
        result = await self._db.conversations.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def create_group(
        self,
        mentor_id: str,
        intern_ids: list[str],
        title: str,
        created_by: str,
    ) -> dict[str, Any]:
        now = utc_now()
        document = {
            "type": "group",
            "title": title,
            "mentor_id": mentor_id,
            "intern_ids": intern_ids,
            "participant_ids": [mentor_id, *intern_ids],
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
            "last_message_preview": "",
            "last_message_at": None,
        }
        result = await self._db.conversations.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def update_last_message(
        self,
        conversation_id: str,
        preview: str,
        updated_at,
    ) -> dict[str, Any]:
        object_id = ObjectId(conversation_id)
        await self._db.conversations.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "updated_at": updated_at,
                    "last_message_at": updated_at,
                    "last_message_preview": preview[:120],
                }
            },
        )
        return await self._db.conversations.find_one({"_id": object_id})


class MessageRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db

    async def list_for_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        cursor = self._db.messages.find({"conversation_id": conversation_id}).sort(
            "created_at", 1
        )
        return await cursor.to_list(length=max(1, min(limit, 200)))

    async def create_message(
        self,
        conversation_id: str,
        sender_id: str,
        content: str,
        attachments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        message = {
            "conversation_id": conversation_id,
            "sender_id": sender_id,
            "content": content,
            "attachments": attachments,
            "created_at": utc_now(),
        }
        result = await self._db.messages.insert_one(message)
        message["_id"] = result.inserted_id
        return message


def build_message_attachments(attachments: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(ObjectId()),
            "file_id": attachment.file_id,
            "file_name": attachment.file_name,
            "mime_type": attachment.mime_type,
            "size": attachment.size,
            "status": "uploaded",
        }
        for attachment in attachments
    ]
