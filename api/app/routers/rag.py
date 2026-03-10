import os
from typing import List, Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.database_utils import database_utils
from app.utils.ricgraph_utils.connections_utils import get_connections

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

def _get_abstracts_by_dois(dois: list[str]) -> list[dict]:
    """
    Fetch abstracts for a specific set of DOIs (and basic metadata).
    Used by the executive-summary pipeline instead of full embedding-based RAG.
    """
    if not dois:
        return []
    driver = database_utils.get_graph()
    docs: list[dict] = []
    with driver.session() as session:
        res = session.run(
            """
            MATCH (pub:RicgraphNode {name: 'DOI'})
            WHERE pub.value IN $dois AND pub.abstract IS NOT NULL
            RETURN
              pub.value   AS doi,
              pub.comment AS title,
              pub.year    AS year,
              pub.category AS category,
              pub.abstract AS abstract
            """,
            dois=dois,
        )
        for row in res:
            docs.append(row.data())
    return docs

# --------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------


@router.post("/ask", response_model=RagAskResponse)
async def rag_ask(req: RagAskRequest) -> RagAskResponse:
    """
    Executive summary / RAG endpoint.
    For a person:
      - Use the connections service to get top 5 publications (by year)
        and top 3 organizations.
      - Fetch abstracts for those publication DOIs.
      - Build a context containing org names + publication metadata
        (DOI, title, year, category, abstract).
      - Ask the chat model for a summary.
    For an organization:
      - Use the connections service to get top 10 publications (by year).
      - Fetch abstracts for those DOIs.
      - Build a context and ask the chat model for a summary.
    """
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")
    entity = req.entity
    # 1) Use connections to get top publications and organizations
    if entity.type == "person":
        # Top 5 pubs, top 3 orgs – no need for many collaborators here
        conn = get_connections(
            entity_id=entity.id,
            entity_type="person",
            max_publications=5,
            max_collaborators=0,
            max_organizations=3,
            max_members=0,
        )
        publications = conn.get("publications", [])[:5]
        orgs = conn.get("organizations", [])[:3]
    else:
        # Organization: top 10 publications
        conn = get_connections(
            entity_id=entity.id,
            entity_type="organization",
            max_publications=10,
            max_collaborators=0,
            max_organizations=0,
            max_members=0,
        )
        publications = conn.get("publications", [])[:10]
        orgs = []
    if not publications:
        # No publications – tell the user explicitly
        answer = await _chat_with_context(
            f"(No related publications were found for entity {entity.label} "
            f"[{entity.type}/{entity.id}].) {req.prompt}",
            context="(no sources available)",
        )
        return RagAskResponse(answer=answer, sources=[])
    # 2) Collect DOIs from the selected publications
    #    (only the main doi field; extend with versions if you want)
    dois: list[str] = []
    for pub in publications:
        doi = pub.get("doi")
        if isinstance(doi, str):
            dois.append(doi)
    # Optional: deduplicate
    dois = list(dict.fromkeys(dois))
    # 3) Fetch abstracts and metadata for these DOIs
    docs = _get_abstracts_by_dois(dois)
    if not docs:
        answer = await _chat_with_context(
            f"(Selected top publications for entity {entity.label} "
            f"but none have abstracts stored.) {req.prompt}",
            context="(no sources available)",
        )
        return RagAskResponse(answer=answer, sources=[])
    # 4) Convert docs into RagSource models (no scoring; just placeholder score)
    sources: list[RagSource] = []
    for d in docs:
        src = RagSource(
            doi=d.get("doi"),
            title=d.get("title"),
            year=d.get("year"),
            category=d.get("category"),
            abstract=d.get("abstract") or "",
            score=1.0,  # all selected docs are considered "top"
        )
        sources.append(src)
    # 5) Build context text for the LLM
    context_chunks: list[str] = []
    # Organizations (only for person entities)
    if entity.type == "person" and orgs:
        org_names = [o.get("name") for o in orgs if isinstance(o.get("name"), str)]
        if org_names:
            context_chunks.append(
                "Affiliated organizations:\n" + "\n".join(f"- {name}" for name in org_names)
            )
    # Publications with abstracts
    for i, s in enumerate(sources, start=1):
        meta_bits = []
        if s.year is not None:
            meta_bits.append(f"Year: {s.year}")
        if s.category:
            meta_bits.append(f"Category: {s.category}")
        meta_str = " | ".join(meta_bits) if meta_bits else ""
        context_chunks.append(
            f"[P{i}] DOI: {s.doi}\n"
            f"Title: {s.title or '(no title)'}\n"
            f"{meta_str}\n"
            f"Abstract: {s.abstract}\n"
        )
    context_text = "\n\n".join(context_chunks)
    # 6) Ask the chat model to produce the executive summary
    answer = await _chat_with_context(req.prompt, context_text)
    return RagAskResponse(answer=answer, sources=sources)


# just the docs for testing

class RagDocsRequest(BaseModel):
    entity: EntityRef
    prompt: str
class RagDocsResponse(BaseModel):
    prompt: str
    context_text: str

@router.post("/docs", response_model=RagDocsResponse)
async def rag_docs(req: RagDocsRequest) -> RagDocsResponse:
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    entity = req.entity

    # 1) Select top pubs + orgs using same logic as executive summary
    if entity.type == "person":
        conn = get_connections(
            entity_id=entity.id,
            entity_type="person",
            max_publications=5,
            max_collaborators=0,
            max_organizations=3,
            max_members=0,
        )
        publications = conn.get("publications", [])[:5]
        orgs = conn.get("organizations", [])[:3]
    else:
        conn = get_connections(
            entity_id=entity.id,
            entity_type="organization",
            max_publications=10,
            max_collaborators=0,
            max_organizations=0,
            max_members=0,
        )
        publications = conn.get("publications", [])[:10]
        orgs = []

    # 2) Collect DOIs
    dois: list[str] = []
    for pub in publications:
        doi = pub.get("doi")
        if isinstance(doi, str):
            dois.append(doi)
    dois = list(dict.fromkeys(dois))  # dedupe, preserve order

    # 3) Fetch abstracts by DOI
    docs = _get_abstracts_by_dois(dois)

    # 4) Build the exact context_text you would pass to _chat_with_context
    context_chunks: list[str] = []

    if entity.type == "person" and orgs:
        org_names = [o.get("name") for o in orgs if isinstance(o.get("name"), str)]
        if org_names:
            context_chunks.append(
                "Affiliated organizations:\n" + "\n".join(f"- {name}" for name in org_names)
            )

    # Add publications
    for i, d in enumerate(docs, start=1):
        year = d.get("year")
        category = d.get("category")
        meta_bits = []
        if year is not None:
            meta_bits.append(f"Year: {year}")
        if category:
            meta_bits.append(f"Category: {category}")
        meta_str = " | ".join(meta_bits) if meta_bits else ""

        context_chunks.append(
            f"[P{i}] DOI: {d.get('doi')}\n"
            f"Title: {d.get('title') or '(no title)'}\n"
            f"{meta_str}\n"
            f"Abstract: {d.get('abstract') or ''}\n"
        )

    context_text = "\n\n".join(context_chunks) if context_chunks else "(no sources available)"

    return RagDocsResponse(prompt=req.prompt, context_text=context_text)