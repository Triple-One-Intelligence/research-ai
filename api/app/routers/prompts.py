import json
import logging
from typing import TypedDict

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.utils.database_utils.database_utils import get_graph
# Refactoring: Shotgun Surgery fix — constants centralized in ai_utils
from app.utils.ai_utils.ai_utils import (
    AI_SERVICE_URL, CHAT_MODEL,CHAT_MAX_TOKENS
)
from app.utils.ricgraph_utils.queries import rag_queries
from app.utils.schemas.ai import (
    ChatRequest, EntityRef, Message
)

#TODO: replace this with the normal "Publication"
class SimilarPublication(TypedDict):
    doi: str
    title: str | None
    year: int | None
    category: str | None
    abstract: str | None

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/prompt_top5publications")
def _stream_prompt1_response(selected_entity: EntityRef, language: str = "English") -> StreamingResponse:

    USER_PROMPT = "Generate a short summary regarding the selected documents if availible and list them off."
    
    # Retrieve the publications from Neo4j 
    if selected_entity.type == "person":
        query = rag_queries.get_PERSON_PUBLICATIONS
    elif selected_entity.type == "organization":
        query = rag_queries.get_ORG_PUBLICATIONS
    
    params = {
        "entityId": selected_entity.id,
        "limit": 5
    }

    documentList: list[SimilarPublication]= []
    
    with get_graph().session() as session:
        results = session.run(query, **params)
        documentList = [
            {
                "doi": r["doi"],
                "title": r["title"],
                "year": r["year"],
                "category": r["category"],
                "abstract": r["abstract"],
            }
            for r in results
        ]
    
    # Format the context to a string
    rag_context = format_similar_publications_for_rag(documentList)
    system_prompt = _build_rag_system_prompt(selected_entity, rag_context)

    messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": "Respond in: " + language},
            {"role": "user", "content": USER_PROMPT}, #TODO: add a new prompt or combine it with the system prompt
        ]
    
    # Send it all to the AI
    return _streaming_chat_response(messages)


#--------------------------------HELPERS--------------------------------
def format_similar_publications_for_rag(similar_publications: list[SimilarPublication]) -> str:
    """Turn a list of similar publications into numbered documents for RAG context.

    Uses a numbered document format (Document [1], Document [2], …) so that
    citation-aware models like Command-R can produce inline references."""
    blocks = []
    for idx, doc in enumerate(similar_publications, 1):
        lines = [f"Document [{idx}]"]
        lines.append(f"DOI: {doc.get('doi', 'n/a')}")
        lines.append(f"Title: {doc.get('title', 'n/a')}")
        lines.append(f"Year: {doc.get('year', 'n/a')}")
        if doc.get("category"):
            lines.append(f"Category: {doc['category']}")
        if doc.get("abstract"):
            lines.append(f"Abstract: {doc['abstract']}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def format_entity_context(entity: EntityRef) -> str:
    """Returns a string describing which entity the prompt is about."""
    return (
        f"The following user query is related to a {entity.type} "
        f"named '{entity.label}'."
    )


def _build_rag_system_prompt(entity: EntityRef | None, publications_context: str) -> str:
    """Build the system prompt incorporating RAG context.

    Pattern: Builder — constructs the prompt step-by-step from parts.
    Instructs the model to cite sources using document numbers [1], [2], etc."""
    
    parts = [
        "Use ONLY the given context documents as evidence. "
        "Cite your sources inline using document numbers, e.g. [1], [2]. "
        "Always include the DOI when referencing a specific publication. "
        "Do not invent information that is not present in the documents. "
        "If evidence is insufficient, say so. Respond in the language of the user query."
    ]
    if entity:
        parts.append(f"\n{format_entity_context(entity)}")
    if publications_context:
        parts.append(f"\n\n{publications_context}")
    else:
        parts.append("\n\nNo publications with abstracts were found for this entity.")
    return "\n".join(parts)


def _streaming_chat_response(messages: list[Message]) -> StreamingResponse:
    """Return a StreamingResponse that proxies Ollama /api/chat as SSE.

    Pattern: Proxy — wraps the Ollama API and transforms its response format."""
    url = f"{AI_SERVICE_URL}/api/chat"

    payload = {
        "model": CHAT_MODEL,
        "messages": messages,
        "stream": True,
        "options": {"num_predict": CHAT_MAX_TOKENS},
    }

    async def stream_ollama():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, timeout=300.0) as resp:
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
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_ollama(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )