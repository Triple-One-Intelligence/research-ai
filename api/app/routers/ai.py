import os
import json
from typing import List, Dict, Any, Literal, Optional
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.utils.database_utils.database_utils import get_graph, VECTOR_INDEX_NAME
from app.utils.ai_utils.ai_utils import async_embed
from app.utils.ricgraph_utils.queries import rag_queries

router = APIRouter()

AI_SERVICE_URL = os.environ["AI_SERVICE_URL"]
CHAT_MODEL = os.getenv("CHAT_MODEL", "tinyllama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

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

async def get_similar_publications(prompt: str, entity: Optional[EntityRef], top_k: int) -> list[dict]:
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
            "searchK": top_k * 25,
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


def format_similar_publications_for_rag(similar_publications: list[dict]) -> str:
    """Turn a list of similar publications into a single string for RAG context.
    Each publication is formatted with its DOI, title, year, and optionally
    category and abstract."""
    lines = []
    for doc in similar_publications:
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


def format_entity_context(entity: EntityRef) -> str:
    """Returns a string describing which entity the prompt is about."""
    return (
        f"The following user query is related to a {entity.type} "
        f"named '{entity.label}'."
    )


def _build_rag_system_prompt(entity: Optional[EntityRef], publications_context: str) -> str:
    """Build the system prompt incorporating RAG context."""
    parts = [
        "Use ONLY the given context data as evidence. "
        "Be concise, neutral, and avoid speculation beyond the evidence. "
        "If evidence is insufficient, say so briefly."
    ]
    if entity:
        parts.append(f"\n{format_entity_context(entity)}")
    if publications_context:
        parts.append(f"\n\nRelevant publications:\n{publications_context}")
    else:
        parts.append("\n\nNo publications with abstracts were found for this entity.")
    return "\n".join(parts)

# --------------------------------------------------------------------
# Streaming helper
# --------------------------------------------------------------------

def _streaming_chat_response(payload: dict, debug_info: Optional[dict] = None):
    """Return a StreamingResponse that proxies Ollama /api/chat as SSE.
    If debug_info is provided, it is sent as the first SSE event."""
    url = f"{AI_SERVICE_URL}/api/chat"

    async def stream_ollama():
        if debug_info:
            yield f"data: {json.dumps({'debug': debug_info})}\n\n"
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
    """Streaming RAG-augmented generation: embeds the user prompt, retrieves
    similar publications from the vector index (scoped to the selected entity),
    and streams the LLM response token-by-token via SSE."""
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    similar_docs = await get_similar_publications(req.prompt, req.entity, req.top_k)
    rag_context = format_similar_publications_for_rag(similar_docs)
    system_prompt = _build_rag_system_prompt(req.entity, rag_context)

    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.prompt},
        ],
        "stream": True,
    }

    debug_info = None
    if DEBUG:
        debug_info = {
            "model": CHAT_MODEL,
            "user_prompt": req.prompt,
            "entity": req.entity.model_dump() if req.entity else None,
            "publications_found": len(similar_docs),
            "publications": similar_docs,
            "system_prompt": system_prompt,
            "full_messages": payload["messages"],
        }

    return _streaming_chat_response(payload, debug_info=debug_info)


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
