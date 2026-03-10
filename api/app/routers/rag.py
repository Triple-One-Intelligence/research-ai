import os
from typing import List, Literal, Optional
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.utils.database_utils import database_utils

# --------------------------------------------------------------------
# Config (reuse same env variables used elsewhere)
# --------------------------------------------------------------------
AI_SERVICE_URL = os.environ["AI_SERVICE_URL"]
CHAT_MODEL = os.getenv("CHAT_MODEL", "tinyllama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

router = APIRouter(prefix="/rag", tags=["rag"])

# --------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------

class EntityRef(BaseModel):
    id: str
    type: Literal["person", "organization"]
    label: str

class RagSource(BaseModel):
    doi: str
    title: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None
    abstract: str
    score: float

class RagAskRequest(BaseModel):
    entity: EntityRef
    prompt: str
    top_k: int = 8

class RagAskResponse(BaseModel):
    answer: str
    sources: List[RagSource]


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0

    num = 0.0
    da = 0.0
    db = 0.0
    for x, y in zip(a, b):
        num += x * y
        da += x * x
        db += y * y

    if da == 0.0 or db == 0.0:
        return 0.0

    return num / ((da**0.5) * (db**0.5))


async def _embed(text: str) -> list[float]:
    """
    Call Ollama embeddings API directly (same as /embed, but internal).
    """
    url = f"{AI_SERVICE_URL}/api/embeddings"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embedding")
            
            if not isinstance(emb, list):
                raise RuntimeError("Embedding response missing 'embedding' list")

            return emb

        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Error connecting to AI embeddings service: {e}",
            )


async def _chat_with_context(prompt: str, context: str) -> str:
    """
    Call Ollama chat API, injecting retrieved context into the prompt.
    """
    url = f"{AI_SERVICE_URL}/api/chat"
    messages = [
        {
            "role": "system",
            "content": (
                "You are a research assistant. Answer the user's question "
                "using ONLY the information in the provided sources. "
                "If the sources are insufficient or unrelated, say so explicitly."
            ),
        },
        {
            "role": "user",
            "content": f"{prompt}\n\n---\nSources:\n{context}",
        },
    ]

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                json={
                    "model": CHAT_MODEL,
                    "messages": messages,
                    "stream": False,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama-style response: { "message": { "content": "..." }, ... }
            msg = data.get("message") or {}
            content = msg.get("content")

            if not isinstance(content, str):
                raise RuntimeError("Chat response missing 'message.content'")

            return content

        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Error connecting to AI chat service: {e}",
            )


def _get_entity_publication_docs(entity: EntityRef, max_docs: int) -> list[dict]:
    """
    Fetch publication nodes for the given entity from Neo4j, including
    abstract + embedding stored by the enrich.py script.
    This intentionally mirrors your existing connections_queries, but
    adds abstract + embedding.
    """
    driver = database_utils.get_graph()
    docs: list[dict] = []

    with driver.session() as session:
        if entity.type == "person":
            # Person: resolve person-root first, then traverse to DOI nodes
            res = session.run(
                """
                // Resolve person-root node from arbitrary person node id
                MATCH (start:RicgraphNode {_key: $entityId})
                OPTIONAL MATCH (start)-[:LINKS_TO]-(root:RicgraphNode {name: 'person-root'})
                WITH CASE WHEN start.name = 'person-root' THEN start ELSE root END AS root
                WHERE root IS NOT NULL
                // Publications attached to this person-root
                MATCH (root)-[:LINKS_TO]-(pub:RicgraphNode {name: 'DOI'})
                WHERE pub.value IS NOT NULL
                  AND pub.abstract IS NOT NULL
                  AND pub.embedding IS NOT NULL
                RETURN
                  pub.value     AS doi,
                  pub.comment   AS title,
                  pub.year      AS year,
                  pub.category  AS category,
                  pub.abstract  AS abstract,
                  pub.embedding AS embedding
                LIMIT $maxDocs
                """,
                entityId=entity.id,
                maxDocs=max_docs,
            )
        else:
            # Organization: org -> person-root -> DOI
            res = session.run(
                """
                MATCH (org:RicgraphNode {_key: $entityId})
                      -[:LINKS_TO]-(:RicgraphNode {name: 'person-root'})-[:LINKS_TO]
                      (pub:RicgraphNode {name: 'DOI'})
                WHERE pub.value IS NOT NULL
                  AND pub.abstract IS NOT NULL
                  AND pub.embedding IS NOT NULL
                RETURN
                  pub.value     AS doi,
                  pub.comment   AS title,
                  pub.year      AS year,
                  pub.category  AS category,
                  pub.abstract  AS abstract,
                  pub.embedding AS embedding
                LIMIT $maxDocs
                """,
                entityId=entity.id,
                maxDocs=max_docs,
            )

        for row in res:
            data = row.data()
            docs.append(data)

    return docs


# --------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------


@router.post("/ask", response_model=RagAskResponse)
async def rag_ask(req: RagAskRequest) -> RagAskResponse:
    """
    Simple RAG endpoint:
    1) Get publications for the selected entity.
    2) Embed (entity + question).
    3) Rank docs by cosine similarity in Python.
    4) Build a context block and call the chat model.
    """

    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    docs = _get_entity_publication_docs(req.entity, max_docs=100)
    if not docs:
        # No docs – fallback: answer without context but tell the user.
        answer = await _chat_with_context(
            f"(No related publications were found for entity {req.entity.label} "
            f"[{req.entity.type}/{req.entity.id}].) {req.prompt}",
            context="(no sources available)",
        )
        return RagAskResponse(answer=answer, sources=[])

    query_text = (
        f"Entity: {req.entity.label} ({req.entity.type}, id={req.entity.id})\n"
        f"Question: {req.prompt}"
    )
    query_emb = await _embed(query_text)

    # Score and pick top_k
    scored: list[RagSource] = []
    for d in docs:
        emb = d.get("embedding")

        if not isinstance(emb, list):
            continue

        score = _cosine_similarity(query_emb, emb)

        if score <= 0:
            continue

        src = RagSource(
            doi=d.get("doi"),
            title=d.get("title"),
            year=d.get("year"),
            category=d.get("category"),
            abstract=d.get("abstract") or "",
            score=score,
        )
        scored.append(src)

    scored.sort(key=lambda s: s.score, reverse=True)
    top_sources = scored[: max(req.top_k, 1)]

    # Build context text for the LLM
    context_chunks = []
    for i, s in enumerate(top_sources, start=1):
        meta_bits = []

        if s.year is not None:
            meta_bits.append(f"Year: {s.year}")

        if s.category:
            meta_bits.append(f"Category: {s.category}")
            
        meta_str = " | ".join(meta_bits) if meta_bits else ""
        context_chunks.append(
            f"[S{i}] DOI: {s.doi}\n"
            f"Title: {s.title or '(no title)'}\n"
            f"{meta_str}\n"
            f"Abstract: {s.abstract}\n"
        )

    context_text = "\n\n".join(context_chunks)
    answer = await _chat_with_context(req.prompt, context_text)

    return RagAskResponse(answer=answer, sources=top_sources)