"""Router for AI endpoints: generation and embeddings."""

import logging

from fastapi import APIRouter, HTTPException

from app.utils.ai_utils.ai_utils import (
    AI_SERVICE_URL,
    CHAT_MAX_TOKENS,
    CHAT_MODEL,
    CHAT_CONTEXT_WINDOW,
    VECTOR_SEARCH_MULTIPLIER,
    build_rag_system_prompt,
    format_entity_context,
    format_similar_publications_for_rag,
    get_similar_publications,
    send_async_ai_request,
    streaming_chat_response,
)
from app.utils.schemas.ai import EmbedRequest, EntityRef, RagGenerateRequest

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate")
async def rag_generate(req: RagGenerateRequest):
    """Stream a generated answer, optionally augmented with entity-scoped RAG."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    try:
        similar_docs = await get_similar_publications(req.prompt, req.entity, req.top_k)
    except HTTPException:
        raise
    except Exception as e:
        log.error("RAG retrieval failed: %s", e)
        raise HTTPException(status_code=503, detail="RAG retrieval failed")

    rag_context = format_similar_publications_for_rag(similar_docs)
    system_prompt = build_rag_system_prompt(req.entity, rag_context)

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
        log.debug(
            "RAG generate - model=%s, entity=%s, publications_found=%d",
            CHAT_MODEL,
            req.entity.model_dump() if req.entity else None,
            len(similar_docs),
        )
        log.debug("System prompt: %s", system_prompt)

    return streaming_chat_response(payload)


@router.post("/embed")
async def embed(req: EmbedRequest):
    """Send an embedding request to the AI service."""
    return await send_async_ai_request(
        f"{AI_SERVICE_URL}/api/embed",
        {"model": req.model, "input": req.prompt},
    )
