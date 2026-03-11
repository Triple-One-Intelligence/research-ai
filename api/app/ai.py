import os
import json
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

CHAT_MODEL = os.getenv("CHAT_MODEL", "tinyllama")

router = APIRouter()

# Get the Ollama URL from the environment
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL")

if not AI_SERVICE_URL:
    raise RuntimeError("AI_SERVICE_URL environment variable is not set")

# --- Pydantic Models ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = CHAT_MODEL
    messages: List[Message]
    stream: bool = True
    options: Optional[Dict[str, Any]] = None

class EmbedRequest(BaseModel):
    model: str = "nomic-embed-text"
    prompt: str

# --- Endpoints ---
@router.post("/chat")
async def chat(req: ChatRequest):
    url = f"{AI_SERVICE_URL}/api/chat"
    payload = req.model_dump(exclude_none=True)
    payload["stream"] = True

    async def stream_ollama():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, timeout=120.0) as resp:
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

    return StreamingResponse(
        stream_ollama(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/embed")
async def embed(req: EmbedRequest):
    """
    Sends an embedding request to the Ollama container.
    """
    url = f"{AI_SERVICE_URL}/api/embeddings"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                json=req.model_dump(exclude_none=True),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error connecting to AI service: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=response.status_code, detail=f"AI service error: {response.text}")