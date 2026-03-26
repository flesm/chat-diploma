import pytest
from fastapi import HTTPException

from src.app.application.services import ChatService


class TestChatService:
    async def test_list_conversations_for_mentor_filters_by_links(
        self,
        conversations_repo,
        messages_repo,
        mentor_gateway,
        realtime_manager,
        mentor_user,
        conversation_document,
    ) -> None:
        mentor_gateway.verify_mentor_intern_links.return_value = [
            {"intern_id": "intern-1"}
        ]
        conversations_repo.list_for_mentor.return_value = [conversation_document]
        service = ChatService(
            conversations_repo,
            messages_repo,
            mentor_gateway,
            realtime_manager,
        )

        result = await service.list_conversations(mentor_user)

        assert len(result) == 1
        conversations_repo.list_for_mentor.assert_awaited_once_with(
            mentor_id="mentor-1",
            allowed_intern_ids=["intern-1"],
        )

    async def test_create_or_get_direct_conversation_rejects_unlinked_intern(
        self,
        conversations_repo,
        messages_repo,
        mentor_gateway,
        realtime_manager,
        mentor_user,
        direct_payload,
    ) -> None:
        mentor_gateway.verify_mentor_intern_links.return_value = []
        service = ChatService(
            conversations_repo,
            messages_repo,
            mentor_gateway,
            realtime_manager,
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_or_get_direct_conversation(
                direct_payload,
                mentor_user,
            )

        assert exc_info.value.status_code == 403

    async def test_create_or_get_direct_conversation_reuses_existing_chat(
        self,
        conversations_repo,
        messages_repo,
        mentor_gateway,
        realtime_manager,
        mentor_user,
        direct_payload,
        conversation_document,
    ) -> None:
        mentor_gateway.verify_mentor_intern_links.return_value = [
            {"intern_id": "intern-1"}
        ]
        conversations_repo.get_by_direct_key.return_value = conversation_document
        service = ChatService(
            conversations_repo,
            messages_repo,
            mentor_gateway,
            realtime_manager,
        )

        result = await service.create_or_get_direct_conversation(
            direct_payload,
            mentor_user,
        )

        assert result["id"] == str(conversation_document["_id"])
        conversations_repo.create_direct.assert_not_called()
        realtime_manager.broadcast_to_users.assert_awaited_once()

    async def test_create_group_conversation_requires_mentor_role(
        self,
        conversations_repo,
        messages_repo,
        mentor_gateway,
        realtime_manager,
        intern_user,
        group_payload,
    ) -> None:
        service = ChatService(
            conversations_repo,
            messages_repo,
            mentor_gateway,
            realtime_manager,
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.create_group_conversation(group_payload, intern_user)

        assert exc_info.value.status_code == 403

    async def test_send_message_rejects_empty_payload(
        self,
        conversations_repo,
        messages_repo,
        mentor_gateway,
        realtime_manager,
        mentor_user,
        conversation_document,
    ) -> None:
        conversations_repo.get_by_id.return_value = conversation_document
        service = ChatService(
            conversations_repo,
            messages_repo,
            mentor_gateway,
            realtime_manager,
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.send_message(
                str(conversation_document["_id"]),
                type("Payload", (), {"content": " ", "attachments": []})(),
                mentor_user,
            )

        assert exc_info.value.status_code == 400

    async def test_send_message_broadcasts_updates(
        self,
        conversations_repo,
        messages_repo,
        mentor_gateway,
        realtime_manager,
        mentor_user,
        conversation_document,
        message_document,
        message_payload,
    ) -> None:
        conversations_repo.get_by_id.return_value = conversation_document
        messages_repo.create_message.return_value = message_document
        conversations_repo.update_last_message.return_value = conversation_document
        service = ChatService(
            conversations_repo,
            messages_repo,
            mentor_gateway,
            realtime_manager,
        )

        result = await service.send_message(
            str(conversation_document["_id"]),
            message_payload,
            mentor_user,
        )

        assert result["content"] == "Hello"
        messages_repo.create_message.assert_awaited_once()
        realtime_manager.broadcast_to_conversation.assert_awaited_once()
        realtime_manager.broadcast_to_users.assert_awaited_once()
