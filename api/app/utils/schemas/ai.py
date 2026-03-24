"""Pydantic schemas for the AI router endpoints."""

from typing import Literal

from pydantic import BaseModel

from app.utils.ai_utils.ai_utils import EMBED_MODEL


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
