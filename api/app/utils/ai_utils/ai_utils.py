import os
import httpx
from fastapi import HTTPException

AI_SERVICE_URL = os.environ["AI_SERVICE_URL"]
CHAT_MODEL = os.getenv("CHAT_MODEL", "tinyllama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_DIMENSIONS = int(os.getenv("EMBED_DIMENSIONS", "768"))

def send_ai_request(url: str, request_params: dict, client: httpx.Client) -> dict:   
    try:
        response = client.post(
            url, 
            json=request_params,
            timeout=60.0 # LLMs can take a moment to respond
        )
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Error connecting to AI service: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=response.status_code, detail=f"AI service error: {response.text}")

async def send_async_ai_request(url: str, request_params: dict) -> dict:   
    # We use httpx.AsyncClient to prevent blocking the FastAPI event loop
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                json=request_params,
                timeout=60.0 # LLMs can take a moment to respond
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error connecting to AI service: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=response.status_code, detail=f"AI service error: {response.text}")

async def generate(prompt: str) -> dict:
    """
    Sends a generate request to the Ollama container.
    """
    # to see which params are possible: https://docs.ollama.com/api/generate
    params = {
        "prompt": prompt,
        "model": CHAT_MODEL,
        "system": "Use ONLY the given context data as evidence. Be concise, neutral, and avoid speculation beyond the evidence. If evidence is insufficient, say so briefly.",
        "stream": True
        }
    url = f"{AI_SERVICE_URL}/api/chat"
    
    return await send_async_ai_request(url, params)



async def async_embed(input: str):
    """
    Sends an asynchronous embedding request to the Ollama container.
    """
    url = f"{AI_SERVICE_URL}/api/embed"

    params = {
        "input": input,
        "model": EMBED_MODEL,
        "dimensions": EMBED_DIMENSIONS
        }
    return await send_async_ai_request(url, params)

def embed(input: str, client: httpx.Client):
    """
    Sends an embedding request to the Ollama container.
    """
    url = f"{AI_SERVICE_URL}/api/embed"

    params = {
        "input": input,
        "model": EMBED_MODEL,
        "dimensions": EMBED_DIMENSIONS
        }
    return send_ai_request(url, params, client)