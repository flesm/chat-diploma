from pydantic import BaseModel, Field


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


class WebSocketMessagePayload(MessageCreatePayload):
    action: str = "message.send"
