"""Router for AI endpoints: chat, RAG generation, and embeddings."""

import json
import logging
from typing import TypedDict

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.utils.database_utils.database_utils import get_graph, VECTOR_INDEX_NAME
from app.utils.ai_utils.ai_utils import (
    AI_SERVICE_URL, CHAT_MODEL, CHAT_MAX_TOKENS, CHAT_CONTEXT_WINDOW, async_embed, send_async_ai_request,
)
from app.utils.ricgraph_utils.queries import rag_queries
from app.utils.schemas.ai import (
    ChatRequest, EmbedRequest, EntityRef, RagGenerateRequest,
)
from app.prompts.system_prompt import SYSTEM_PROMPT


class SimilarPublication(TypedDict):
    doi: str
    title: str | None
    year: int | None
    category: str | None
    abstract: str | None

log = logging.getLogger(__name__)

# Number of candidates fetched from the vector index before filtering to top_k.
# A higher multiplier improves recall when scoped to a specific entity.
VECTOR_SEARCH_MULTIPLIER = 25

router = APIRouter()

# --------------------------------------------------------------------
# RAG helpers
# --------------------------------------------------------------------

async def get_similar_publications(prompt: str, entity: EntityRef | None, top_k: int) -> list[SimilarPublication]:
    """Embed the user prompt and retrieve the most similar publications
    from the vector index, optionally scoped to an entity."""
    prompt_embedding = await async_embed(prompt)

    if entity:
        if entity.type == "person":
            query = rag_queries.PERSON_SIMILAR_PUBLICATIONS
        else:
            query = rag_queries.ORG_SIMILAR_PUBLICATIONS
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
                "doi": r["doi"],
                "title": r["title"],
                "year": r["year"],
                "category": r["category"],
                "abstract": r["abstract"],
            }
            for r in results
        ]


def format_similar_publications_for_rag(similar_publications: list[SimilarPublication]) -> str:
    """Turn a list of similar publications into numbered documents for RAG context."""
    blocks = []
    for idx, doc in enumerate(similar_publications, 1):
        lines = [f"Document [{idx}]"]
        lines.extend(filter(None, [
            f"DOI: {doc['doi']}" if doc.get("doi") else None,
            f"Title: {doc['title']}" if doc.get("title") else None,
            f"Year: {doc['year']}" if doc.get("year") else None,
            f"Category: {doc['category']}" if doc.get("category") else None,
            f"Abstract: {doc['abstract']}" if doc.get("abstract") else None,
        ]))
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_entity_context(entity: EntityRef) -> str:
    """Returns a string describing which entity the prompt is about."""
    return (
        f"The following user query is related to a {entity.type} "
        f"named '{entity.label}'."
    )


def _build_rag_system_prompt(entity: EntityRef | None, publications_context: str) -> str:
    """Build the system prompt incorporating RAG context."""
    parts = [SYSTEM_PROMPT]
    if entity:
        parts.append(f"\n{format_entity_context(entity)}")
    if publications_context:
        parts.append(f"\n\n{publications_context}")
    else:
        parts.append("\n\nNo publications with abstracts were found for this entity.")
    return "\n".join(parts)

# --------------------------------------------------------------------
# Streaming helper
# --------------------------------------------------------------------

def _streaming_chat_response(payload: dict):
    """Return a StreamingResponse that proxies Ollama /api/chat as SSE."""
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

# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

@router.post("/chat")
async def chat(req: ChatRequest):
    """Streaming chat without RAG context."""
    payload = req.model_dump(exclude_none=True)
    payload["model"] = CHAT_MODEL  # Always use the configured model
    payload["stream"] = True
    payload["options"] = {"num_predict": CHAT_MAX_TOKENS}
    return _streaming_chat_response(payload)


@router.post("/generate")
async def rag_generate(req: RagGenerateRequest):
    """Streaming RAG-augmented generation: embeds the user prompt, retrieves
    similar publications from the vector index (scoped to the selected entity),
    and streams the LLM response token-by-token via SSE."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    try:
        similar_docs = await get_similar_publications(req.prompt, req.entity, req.top_k)
    except HTTPException:
        raise  # Re-raise AI service errors (503, 404) as-is
    except Exception as e:
        log.error("RAG retrieval failed: %s", e)
        raise HTTPException(status_code=503, detail="RAG retrieval failed")
    rag_context = format_similar_publications_for_rag(similar_docs)
    system_prompt = _build_rag_system_prompt(req.entity, rag_context)

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.prompt},
        ],
        "stream": True,
        "options": {"num_predict": CHAT_MAX_TOKENS, "num_ctx": CHAT_CONTEXT_WINDOW},
    }

    if log.isEnabledFor(logging.DEBUG):
        log.debug("RAG generate — model=%s, entity=%s, publications_found=%d",
                  CHAT_MODEL,
                  req.entity.model_dump() if req.entity else None,
                  len(similar_docs))
        log.debug("System prompt: %s", system_prompt)

    return _streaming_chat_response(payload)


@router.post("/embed")
async def embed(req: EmbedRequest):
    """Sends an embedding request to the Ollama container."""
    return await send_async_ai_request(
        f"{AI_SERVICE_URL}/api/embed",
        {"model": req.model, "input": req.prompt},
    )
