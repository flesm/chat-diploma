from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from src.app.application.dtos import (
    AttachmentPayload,
    ConversationCreatePayload,
    CurrentUser,
    GroupConversationCreatePayload,
    MessageCreatePayload,
)


@pytest.fixture
def mentor_user() -> CurrentUser:
    return CurrentUser(
        id="mentor-1",
        email="mentor@example.com",
        first_name="Mentor",
        last_name="User",
        role="mentor",
        token="mentor-token",
    )


@pytest.fixture
def intern_user() -> CurrentUser:
    return CurrentUser(
        id="intern-1",
        email="intern@example.com",
        first_name="Intern",
        last_name="User",
        role="intern",
        token="intern-token",
    )


@pytest.fixture
def conversation_document() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "_id": ObjectId(),
        "type": "direct",
        "title": None,
        "mentor_id": "mentor-1",
        "intern_ids": ["intern-1"],
        "participant_ids": ["mentor-1", "intern-1"],
        "last_message_preview": "",
        "last_message_at": None,
        "created_at": now,
        "updated_at": now,
    }


@pytest.fixture
def message_document(conversation_document: dict) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "_id": ObjectId(),
        "conversation_id": str(conversation_document["_id"]),
        "sender_id": "mentor-1",
        "content": "Hello",
        "attachments": [],
        "created_at": now,
    }


@pytest.fixture
def direct_payload() -> ConversationCreatePayload:
    return ConversationCreatePayload(intern_id="intern-1")


@pytest.fixture
def group_payload() -> GroupConversationCreatePayload:
    return GroupConversationCreatePayload(
        title=" Sprint updates ",
        intern_ids=["intern-1", "intern-2"],
    )


@pytest.fixture
def message_payload() -> MessageCreatePayload:
    return MessageCreatePayload(
        content=" Hello team ",
        attachments=[
            AttachmentPayload(
                file_id="file-1",
                file_name="spec.pdf",
                mime_type="application/pdf",
                size=128,
            )
        ],
    )


@pytest.fixture
def conversations_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def messages_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mentor_gateway() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def realtime_manager() -> AsyncMock:
    return AsyncMock()
