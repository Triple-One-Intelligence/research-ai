"""Pydantic schemas for the AI router endpoints."""

from typing import Any, Literal

from pydantic import BaseModel

from app.utils.ai_utils.ai_utils import CHAT_MODEL, EMBED_MODEL


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = CHAT_MODEL
    messages: list[Message]
    stream: bool = True
    options: dict[str, Any] | None = None


class EmbedRequest(BaseModel):
    model: str = EMBED_MODEL
    prompt: str


class EntityRef(BaseModel):
    id: str
    type: Literal["person", "organization"]
    label: str


class RagGenerateRequest(BaseModel):
    prompt: str
    entity: EntityRef | None = None
    top_k: int = 8
