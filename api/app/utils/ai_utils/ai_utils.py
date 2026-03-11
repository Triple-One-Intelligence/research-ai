import os
import httpx
from fastapi import HTTPException

AI_SERVICE_URL = os.environ["AI_SERVICE_URL"]
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_DIMENSIONS = int(os.getenv("EMBED_DIMENSIONS", "768"))


def _send_ai_request(url: str, request_params: dict, client: httpx.Client) -> dict:
    """Send a synchronous request to the AI service (used by the enrich script)."""
    try:
        response = client.post(
            url,
            json=request_params,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Error connecting to AI service: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=response.status_code, detail=f"AI service error: {response.text}")


def embed(input: str, client: httpx.Client) -> dict:
    """Send a synchronous embedding request to the Ollama container."""
    url = f"{AI_SERVICE_URL}/api/embed"
    params = {
        "input": input,
        "model": EMBED_MODEL,
        "dimensions": EMBED_DIMENSIONS,
    }
    return _send_ai_request(url, params, client)
