"""Shared AI service helpers for embedding, streaming chat, and RAG support."""

import json
import logging
from typing import TypedDict

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.utils.database_utils.database_utils import VECTOR_INDEX_NAME, get_graph
from app.utils.ricgraph_utils.queries import rag_queries

from app.config import (
    AI_SERVICE_URL, CHAT_MODEL, EMBED_MODEL, EMBED_DIMENSIONS,
    CHAT_MAX_TOKENS, CHAT_CONTEXT_WINDOW, EMBED_NUM_GPU,
)

VECTOR_SEARCH_MULTIPLIER = 25

log = logging.getLogger(__name__)


class SimilarPublication(TypedDict):
    doi: str
    title: str | None
    year: int | None
    category: str | None
    abstract: str | None


async def send_async_ai_request(url: str, request_params: dict) -> dict:
    """Send an asynchronous request to the AI service."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=request_params,
                timeout=60.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error connecting to AI service: {e}")
        except httpx.HTTPStatusError:
            log.error("AI service error (status %d): %s", response.status_code, response.text)
            raise HTTPException(status_code=502, detail="AI service returned an error.")


async def async_embed(input: str) -> list[float]:
    """Send an asynchronous embedding request and return the embedding vector."""
    url = f"{AI_SERVICE_URL}/api/embed"
    params: dict = {
        "input": input,
        "model": EMBED_MODEL,
        "options": {"num_gpu": EMBED_NUM_GPU},
    }
    result = await send_async_ai_request(url, params)
    embeddings = result.get("embeddings")
    if not embeddings or not embeddings[0]:
        raise HTTPException(status_code=502, detail="AI service returned empty embeddings.")
    return embeddings[0]


async def get_similar_publications(prompt: str, entity, top_k: int) -> list[SimilarPublication]:
    """Embed the prompt and retrieve similar publications from the vector index."""
    prompt_embedding = await async_embed(prompt)

    if entity:
        query = (
            rag_queries.PERSON_SIMILAR_PUBLICATIONS
            if entity.type == "person"
            else rag_queries.ORG_SIMILAR_PUBLICATIONS
        )
        params = {
            "indexName": VECTOR_INDEX_NAME,
            "searchK": top_k * VECTOR_SEARCH_MULTIPLIER,
            "prompt_embedding": prompt_embedding,
            "entityId": entity.id,
            "limit": top_k,
        }
    else:
        query = rag_queries.SIMILAR_PUBLICATIONS
        params = {
            "indexName": VECTOR_INDEX_NAME,
            "k": top_k,
            "prompt_embedding": prompt_embedding,
        }

    with get_graph().session() as session:
        results = session.run(query, **params)
        return [
            {
                "doi": row["doi"],
                "title": row["title"],
                "year": row["year"],
                "category": row["category"],
                "abstract": row["abstract"],
            }
            for row in results
        ]


def format_similar_publications_for_rag(similar_publications: list[SimilarPublication]) -> str:
    """Turn similar publications into a numbered context block for RAG."""
    blocks = []
    for idx, doc in enumerate(similar_publications, 1):
        lines = [f"Document [{idx}]"]
        lines.append(f"DOI: {doc.get('doi', 'n/a')}")
        lines.append(f"Title: {doc.get('title', 'n/a')}")
        lines.append(f"Year: {doc.get('year', 'n/a')}")
        if doc.get("category"):
            lines.append(f"Category: {doc['category']}")
        if doc.get("abstract"):
            lines.append(f"Abstract: {doc['abstract']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_entity_context(entity) -> str:
    """Return a short text describing the selected entity."""
    return (
        f"The following user query is related to a {entity.type} "
        f"named '{entity.label}'."
    )


def build_rag_system_prompt(entity, publications_context: str) -> str:
    """Build the system prompt incorporating RAG context."""
    parts = [
        "Use ONLY the given context documents as evidence. "
        "Cite your sources inline using document numbers, e.g. [1], [2]. "
        "Always include the DOI when referencing a specific publication. "
        "Do not invent information that is not present in the documents. "
        "If evidence is insufficient, say so. Respond in the language of the user query."
    ]
    if entity:
        parts.append(f"\n{format_entity_context(entity)}")
    if publications_context:
        parts.append(f"\n\n{publications_context}")
    else:
        parts.append("\n\nNo publications with abstracts were found for this entity.")
    return "\n".join(parts)


def streaming_chat_response(payload: dict) -> StreamingResponse:
    """Proxy the AI chat endpoint and re-emit its response as SSE."""
    url = f"{AI_SERVICE_URL}/api/chat"

    async def stream_ollama():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, timeout=300.0) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if chunk.get("done"):
                            yield "data: [DONE]\n\n"
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_ollama(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
