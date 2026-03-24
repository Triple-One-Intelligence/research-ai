"""Pydantic schemas for the AI router endpoints."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel

from app.utils.ai_utils.ai_utils import CHAT_MODEL, EMBED_MODEL


class Message(BaseModel):
    role: Literal["user", "stystem"]
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

class TopColleaguesRequest(BaseModel):
    person_id: str
    top_n: int = 10

class ColleagueOut(BaseModel):
    person_id: str
    name: str | None
    coauthor_publications: int
    same_organization: bool
    embedding_similarity: float  # cosine similarity (0..1)
    score: float

#TODO: replace this with the normal "Publication"
class SimilarPublication(TypedDict):
    doi: str
    title: str | None
    year: int | None
    category: str | None
    abstract: str | None