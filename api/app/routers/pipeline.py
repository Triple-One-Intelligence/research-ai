"""
Streaming SSE endpoint for the 4 prompt pipelines. Context built in pipelines/contexts.py.
"""
import asyncio
import json
import logging

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import AI_SERVICE_URL, CHAT_MODEL, CHAT_MAX_TOKENS, CHAT_CONTEXT_WINDOW
from app.utils.schemas.ai import EntityRef
from app.pipelines.contexts import (
    executive_summary_context, top_organizations_context,
    top_collaborators_context, recent_publications_context,
)

log = logging.getLogger(__name__)
router = APIRouter()

_VALID_PROMPT_TYPES = frozenset({
    "executiveSummary", "topOrganizations", "topCollaborators", "recentPublications"
})


class PipelineRequest(BaseModel):
    prompt: str
    entity: EntityRef


def _stream_ollama(payload: dict) -> StreamingResponse:
    """Streams chat response as SSE."""
    url = f"{AI_SERVICE_URL}/api/chat"

    async def generate():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, timeout=300.0) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield f"data: {json.dumps({'token': token})}\n\n"
                        if chunk.get("done"):
                            yield "data: [DONE]\n\n"
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            log.error("Ollama request failed: %s", e)
            yield f"data: {json.dumps({'error': 'AI service unavailable'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _llm_payload(system_prompt: str, user_prompt: str) -> dict:
    """Builds chat request payload."""
    return {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "options": {"num_predict": CHAT_MAX_TOKENS, "num_ctx": CHAT_CONTEXT_WINDOW, "temperature": 0},
    }


@router.post("/pipeline/{prompt_type}")
async def pipeline(prompt_type: str, req: PipelineRequest):
    """Builds pipeline context and streams the LLM response."""
    if prompt_type not in _VALID_PROMPT_TYPES:
        raise HTTPException(status_code=404, detail=f"Unknown pipeline: {prompt_type}")
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    try:
        if prompt_type == "executiveSummary":
            system_prompt = await executive_summary_context(req.entity, req.prompt)
        elif prompt_type == "topOrganizations":
            system_prompt = await asyncio.to_thread(top_organizations_context, req.entity, req.prompt)
        elif prompt_type == "topCollaborators":
            system_prompt = await asyncio.to_thread(top_collaborators_context, req.entity, req.prompt)
        else:
            system_prompt = await asyncio.to_thread(recent_publications_context, req.entity, req.prompt)
    except Exception as e:
        log.error("Pipeline retrieval failed for %s: %s", prompt_type, e)
        raise HTTPException(status_code=503, detail="Pipeline retrieval failed")

    return _stream_ollama(_llm_payload(system_prompt, req.prompt))
