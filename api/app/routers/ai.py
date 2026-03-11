import os
import json
from typing import List, Dict, Any, Literal, Optional
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.utils.database_utils.database_utils import get_graph, VECTOR_INDEX_NAME
from app.utils.ricgraph_utils.queries import rag_queries

router = APIRouter()

AI_SERVICE_URL = os.environ["AI_SERVICE_URL"]
CHAT_MODEL = os.getenv("CHAT_MODEL", "tinyllama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# --------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    model: str = CHAT_MODEL
    messages: List[Message]
    stream: bool = True
    options: Optional[Dict[str, Any]] = None

class EmbedRequest(BaseModel):
    model: str = EMBED_MODEL
    prompt: str

class EntityRef(BaseModel):
    id: str
    type: Literal["person", "organization"]
    label: str

class RagGenerateRequest(BaseModel):
    prompt: str
    entity: Optional[EntityRef] = None
    top_k: int = 8

# --------------------------------------------------------------------
# RAG helpers
# --------------------------------------------------------------------

async def _embed_text(text: str) -> list[float]:
    """Get embedding vector for text via Ollama."""
    url = f"{AI_SERVICE_URL}/api/embeddings"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["embedding"]


async def _get_similar_publications(prompt: str, top_k: int) -> list[dict]:
    """Retrieve similar publications from the Neo4j vector index."""
    prompt_embedding = await _embed_text(prompt)

    with get_graph().session() as session:
        results = session.run(
            rag_queries.SIMILAR_PUBLICATIONS,
            indexName=VECTOR_INDEX_NAME,
            k=top_k,
            prompt_embedding=prompt_embedding,
        )
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


def _format_publications_context(publications: list[dict]) -> str:
    """Format retrieved publications into a context string for the LLM."""
    lines = []
    for doc in publications:
        parts = [
            f"DOI: {doc.get('doi', 'n/a')}",
            f"Title: {doc.get('title', 'n/a')}",
            f"Year: {doc.get('year', 'n/a')}",
        ]
        if doc.get("category"):
            parts.append(f"Category: {doc['category']}")
        if doc.get("abstract"):
            parts.append(f"Abstract: {doc['abstract']}")
        lines.append(" | ".join(parts))
    return "\n\n".join(lines)


def _build_rag_system_prompt(entity: Optional[EntityRef], publications_context: str) -> str:
    """Build the system prompt incorporating RAG context."""
    parts = [
        "Use ONLY the given context data as evidence. "
        "Be concise, neutral, and avoid speculation beyond the evidence. "
        "If evidence is insufficient, say so briefly."
    ]
    if entity:
        parts.append(
            f"\nThe following user query is related to a {entity.type} "
            f"named '{entity.label}'."
        )
    if publications_context:
        parts.append(f"\n\nRelevant publications:\n{publications_context}")
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

# --------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------

@router.post("/chat")
async def chat(req: ChatRequest):
    """Streaming chat without RAG context."""
    payload = req.model_dump(exclude_none=True)
    payload["stream"] = True
    return _streaming_chat_response(payload)


@router.post("/generate")
async def rag_generate(req: RagGenerateRequest):
    """Streaming RAG-augmented generation: retrieves relevant publications
    from the vector index, builds an enriched prompt, and streams the
    LLM response token-by-token via SSE."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    similar_pubs = await _get_similar_publications(req.prompt, req.top_k)
    pub_context = _format_publications_context(similar_pubs)
    system_prompt = _build_rag_system_prompt(req.entity, pub_context)

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.prompt},
        ],
        "stream": True,
    }
    return _streaming_chat_response(payload)


@router.post("/embed")
async def embed(req: EmbedRequest):
    """Sends an embedding request to the Ollama container."""
    url = f"{AI_SERVICE_URL}/api/embeddings"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=req.model_dump(exclude_none=True),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=503, detail=f"Error connecting to AI service: {e}")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=response.status_code, detail=f"AI service error: {response.text}")
