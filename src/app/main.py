from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.example", extra="ignore")

    mongo_url: str = Field(alias="MONGO_URL")
    mongo_db: str = Field(alias="MONGO_DB")
    auth_api_url: str = Field(alias="AUTH_API_URL")
    core_api_url: str = Field(alias="CORE_API_URL")


settings = Settings()
security = HTTPBearer(auto_error=True)


class CurrentUser(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    role: str | None = None
    token: str


class AttachmentPayload(BaseModel):
    file_id: str
    file_name: str
    mime_type: str | None = None
    size: int | None = None


class MessageCreatePayload(BaseModel):
    content: str = ""
    attachments: list[AttachmentPayload] = Field(default_factory=list)


class ConversationCreatePayload(BaseModel):
    intern_id: str


class GroupConversationCreatePayload(BaseModel):
    title: str
    intern_ids: list[str]


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


async def fetch_current_user(token: str) -> CurrentUser:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.auth_api_url}/auth/me",
            params={"token": token},
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    payload = response.json()
    return CurrentUser(
        id=str(payload["id"]),
        email=payload["email"],
        first_name=payload["first_name"],
        last_name=payload["last_name"],
        role=payload.get("role"),
        token=token,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> CurrentUser:
    return await fetch_current_user(credentials.credentials)


def get_db(request_app: FastAPI) -> AsyncIOMotorDatabase:
    return request_app.state.db


async def verify_mentor_intern_links(token: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.core_api_url}/mentor-intern-links",
            headers={"Authorization": f"Bearer {token}"},
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot load mentor interns")

    data = response.json()
    return data if isinstance(data, list) else []


async def verify_my_mentor(token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{settings.core_api_url}/mentor-intern-links/my-mentor",
            headers={"Authorization": f"Bearer {token}"},
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot load mentor link",
        )

    data = response.json()
    return data if isinstance(data, dict) else {}


async def ensure_access_to_conversation(
    db: AsyncIOMotorDatabase,
    user: CurrentUser,
    conversation_id: str,
) -> dict[str, Any]:
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conversation = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if user.id not in conversation.get("participant_ids", []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to conversation")

    return conversation


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo = AsyncIOMotorClient(settings.mongo_url)
    db = mongo[settings.mongo_db]
    app.state.mongo = mongo
    app.state.db = db

    await db.conversations.create_index([("participant_ids", 1), ("updated_at", -1)])
    await db.conversations.create_index([("mentor_id", 1), ("type", 1)])
    await db.conversations.create_index("direct_key", unique=True, sparse=True)
    await db.messages.create_index([("conversation_id", 1), ("created_at", 1)])

    yield

    mongo.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Chat service is running"}


@app.get("/api/v1/conversations")
async def list_conversations(
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    db = app.state.db

    if user.role == "mentor":
        allowed_intern_ids = {
            item["intern_id"] for item in await verify_mentor_intern_links(user.token)
        }
        cursor = db.conversations.find(
            {
                "mentor_id": user.id,
                "$or": [
                    {"intern_ids": {"$size": 0}},
                    {"intern_ids": {"$in": list(allowed_intern_ids)}},
                ],
            }
        ).sort("updated_at", -1)
    else:
        cursor = db.conversations.find({"participant_ids": user.id}).sort("updated_at", -1)

    conversations = await cursor.to_list(length=200)
    return [serialize_conversation(item) for item in conversations]


@app.post("/api/v1/conversations/direct")
async def create_or_get_direct_conversation(
    payload: ConversationCreatePayload,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    if user.role == "mentor":
        mentor_id = user.id
        intern_id = payload.intern_id
        linked_intern_ids = {
            item["intern_id"] for item in await verify_mentor_intern_links(user.token)
        }
        if intern_id not in linked_intern_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Intern is not assigned to mentor",
            )
    elif user.role == "intern":
        link = await verify_my_mentor(user.token)
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

    db = app.state.db
    direct_key = f"{mentor_id}:{intern_id}"
    existing = await db.conversations.find_one({"direct_key": direct_key})
    if existing:
        return serialize_conversation(existing)

    now = utc_now()
    document = {
        "type": "direct",
        "title": None,
        "mentor_id": mentor_id,
        "intern_ids": [intern_id],
        "participant_ids": [mentor_id, intern_id],
        "created_by": user.id,
        "created_at": now,
        "updated_at": now,
        "last_message_preview": "",
        "last_message_at": None,
        "direct_key": direct_key,
    }
    result = await db.conversations.insert_one(document)
    document["_id"] = result.inserted_id
    return serialize_conversation(document)


@app.post("/api/v1/conversations/group")
async def create_group_conversation(
    payload: GroupConversationCreatePayload,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    if user.role != "mentor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only mentor can create group chat")

    intern_ids = sorted(set(payload.intern_ids))
    if not payload.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title is required")
    if not intern_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose at least one intern")

    linked_intern_ids = {
        item["intern_id"] for item in await verify_mentor_intern_links(user.token)
    }
    if not set(intern_ids).issubset(linked_intern_ids):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Some interns are not assigned to mentor")

    db = app.state.db
    now = utc_now()
    document = {
        "type": "group",
        "title": payload.title.strip(),
        "mentor_id": user.id,
        "intern_ids": intern_ids,
        "participant_ids": [user.id, *intern_ids],
        "created_by": user.id,
        "created_at": now,
        "updated_at": now,
        "last_message_preview": "",
        "last_message_at": None,
    }
    result = await db.conversations.insert_one(document)
    document["_id"] = result.inserted_id
    return serialize_conversation(document)


@app.get("/api/v1/conversations/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    limit: int = 100,
    user: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    db = app.state.db
    conversation = await ensure_access_to_conversation(db, user, conversation_id)

    cursor = db.messages.find({"conversation_id": serialize_object_id(conversation["_id"])}).sort(
        "created_at", 1
    )
    messages = await cursor.to_list(length=max(1, min(limit, 200)))
    return [serialize_message(item) for item in messages]


@app.post("/api/v1/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: MessageCreatePayload,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    db = app.state.db
    conversation = await ensure_access_to_conversation(db, user, conversation_id)

    if not payload.content.strip() and not payload.attachments:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")

    now = utc_now()
    message = {
        "conversation_id": serialize_object_id(conversation["_id"]),
        "sender_id": user.id,
        "content": payload.content.strip(),
        "attachments": [
            {
                "id": str(ObjectId()),
                "file_id": attachment.file_id,
                "file_name": attachment.file_name,
                "mime_type": attachment.mime_type,
                "size": attachment.size,
                "status": "uploaded",
            }
            for attachment in payload.attachments
        ],
        "created_at": now,
    }
    result = await db.messages.insert_one(message)
    message["_id"] = result.inserted_id

    preview = payload.content.strip() or (
        f"Файл: {payload.attachments[0].file_name}" if payload.attachments else ""
    )
    await db.conversations.update_one(
        {"_id": conversation["_id"]},
        {
            "$set": {
                "updated_at": now,
                "last_message_at": now,
                "last_message_preview": preview[:120],
            }
        },
    )

    return serialize_message(message)
