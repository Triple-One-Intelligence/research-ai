"""Shared AI service helpers for embedding and LLM requests."""

import logging
import os

import httpx
from fastapi import HTTPException

log = logging.getLogger(__name__)

# Refactoring: Shotgun Surgery fix — single source of truth for AI config.
# Previously duplicated in routers/ai.py, scripts/enrich.py, and schemas/ai.py.
AI_SERVICE_URL = os.environ["AI_SERVICE_URL"]
CHAT_MODEL = os.getenv("CHAT_MODEL", "tinyllama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_DIMENSIONS = int(os.getenv("EMBED_DIMENSIONS", "768"))


async def send_async_ai_request(url: str, request_params: dict) -> dict:
    """Send an asynchronous request to the AI service (used by the router)."""
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
    """Send an asynchronous embedding request and return the embedding vector."""
    url = f"{AI_SERVICE_URL}/api/embed"
    params = {
        "input": input,
        "model": EMBED_MODEL,
        "dimensions": EMBED_DIMENSIONS,
    }
    result = await send_async_ai_request(url, params)
    embeddings = result.get("embeddings")
    if not embeddings or not embeddings[0]:
        raise HTTPException(status_code=502, detail="AI service returned empty embeddings.")
    return embeddings[0]
