import os
import httpx
from fastapi import APIRouter, HTTPException, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

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
    model: str = "llama3" # Replace with your preferred default model
    messages: List[Message]
    stream: bool = False  # Set to True if you want to stream tokens back
    options: Optional[Dict[str, Any]] = None

class EmbedRequest(BaseModel):
    model: str = "nomic-embed-text" # Standard embedding model
    prompt: str

# --- Endpoints ---
@router.post("/chat") # non-streaming version, deprecated can be removed
async def chat(req: ChatRequest):
    """
    Sends a chat request to the Ollama container.
    """
    url = f"{AI_SERVICE_URL}/api/chat"
    
    # We use httpx.AsyncClient to prevent blocking the FastAPI event loop
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                json=req.model_dump(exclude_none=True),
                timeout=60.0 # LLMs can take a moment to respond
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error connecting to AI service: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=response.status_code, detail=f"AI service error: {response.text}")

@router.post("/chat-stream") # new streaming version
async def chat_stream(req: ChatRequest):
    """
    Sends a chat request to the Ollama container and streams the response back to the client.
    """
    url = f"{AI_SERVICE_URL}/api/chat-stream"

    async def event_generator():
        payload = req.model_dump(exclude_none=True)
        payload["stream"] = True

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines(): #TODO: readup on this method
                    if not line:
                        continue
                    # Ollama typically sends JSON per line; wrap each as SSE
                    yield f"{line}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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