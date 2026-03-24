"""Shared AI service helpers for embedding and LLM requests."""

import logging

import httpx
from fastapi import HTTPException

from app.config import (
    AI_SERVICE_URL, CHAT_MODEL, EMBED_MODEL, EMBED_DIMENSIONS,
    CHAT_MAX_TOKENS, CHAT_CONTEXT_WINDOW, EMBED_NUM_GPU,
)

log = logging.getLogger(__name__)


async def send_async_ai_request(url: str, request_params: dict) -> dict:
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
        except httpx.HTTPStatusError as e:
            log.error("AI service error (status %d): %s", response.status_code, response.text)
            raise HTTPException(status_code=502, detail="AI service returned an error.")


async def async_embed(input: str) -> list[float]:
    url = f"{AI_SERVICE_URL}/api/embed"
    params: dict = {
        "input": input,
        "model": EMBED_MODEL,
    }
    params["options"] = {"num_gpu": EMBED_NUM_GPU}
    result = await send_async_ai_request(url, params)
    embeddings = result.get("embeddings")
    if not embeddings or not embeddings[0]:
        raise HTTPException(status_code=502, detail="AI service returned empty embeddings.")
    return embeddings[0]
