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
    ChatRequest, EntityRef, Message, TopColleaguesRequest, ColleagueOut
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

    USER_PROMPT = """Generate a short summary regarding the selected documents if availible and list them off. 
    Start of by cyting the name of the entity and give a small list of all the given documents.
    Make an effort to include all provided documents. If a document contains to little information, note this.
    Try ending the response with a short compliment regarding the entity, based on the prevously mentioned documents.
    Styling: For each document make the title bold and italic. Start the Response with 'The five most recent publications for' and the entity name in H1."""
    
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




@router.post("/top_colleagues", response_model=list[ColleagueOut])
def top_colleagues(req: TopColleaguesRequest):
    person_id = req.person_id
    top_k = req.top_n

    query = """
    MATCH (target:RicgraphNode {name: "person-root", value: $target_person_id})

    // Get all colleagues (coauthors + org mates)
    OPTIONAL MATCH (target)-[:LINKS_TO]->(pub:RicgraphNode {name: "DOI"})-[:LINKS_TO]->(coauthor:RicgraphNode {name: "person-root"})
    WHERE coauthor.value <> target.value

    OPTIONAL MATCH (target)-[:LINKS_TO]->(org:RicgraphNode {name: "ORGANIZATION_NAME"})-[:LINKS_TO]->(orgmate:RicgraphNode {name: "person-root"})
    WHERE orgmate.value <> target.value

    WITH target, COLLECT(DISTINCT coauthor) + COLLECT(DISTINCT orgmate) AS all_colleagues
    UNWIND all_colleagues AS colleague

    // Papers together
    OPTIONAL MATCH (target)-[:LINKS_TO]->(shared_pub:RicgraphNode {name: "DOI"})-[:LINKS_TO]->(colleague)
    WITH target, colleague, COUNT(DISTINCT shared_pub) AS papers_together, COLLECT(DISTINCT shared_pub) AS shared_pubs

    // Target's other publications (excluding cowritten)
    OPTIONAL MATCH (target)-[:LINKS_TO]->(target_pub:RicgraphNode {name: "DOI"})
    WHERE NOT target_pub IN shared_pubs
    WITH target, colleague, papers_together, shared_pubs, COLLECT(target_pub.embedding) AS target_embeddings

    // Colleague's other publications (excluding cowritten)
    OPTIONAL MATCH (colleague)-[:LINKS_TO]->(colleague_pub:RicgraphNode {name: "DOI"})
    WHERE NOT colleague_pub IN shared_pubs
    WITH target, colleague, papers_together, target_embeddings, COLLECT(colleague_pub.embedding) AS colleague_embeddings

    // Handle case where colleague has no other publications
    WITH target, colleague, papers_together, target_embeddings, colleague_embeddings,
        CASE 
        WHEN size(target_embeddings) = 0 OR size(colleague_embeddings) = 0 THEN 0.0
        ELSE null  // marker to calculate similarity
        END AS early_exit_score

    // If early_exit_score is not null, use it; otherwise calculate
    WITH target, colleague, papers_together, target_embeddings, colleague_embeddings, early_exit_score,
        CASE 
        WHEN early_exit_score IS NOT NULL THEN early_exit_score
        ELSE (
            // Calculate magnitudes for target embeddings
            [t_emb IN target_embeddings | 
            {
                embedding: t_emb,
                magnitude: sqrt(reduce(sum = 0.0, i IN range(0, size(t_emb) - 1) | sum + t_emb[i] * t_emb[i]))
            }
            ]  // Get first for now
        )
        END AS placeholder

    // Calculate dot product and magnitudes for each target embedding
    WITH target, colleague, papers_together, target_embeddings, colleague_embeddings, early_exit_score,
        [t_emb IN target_embeddings | 
        {
            embedding: t_emb,
            magnitude: sqrt(reduce(sum = 0.0, i IN range(0, size(t_emb) - 1) | sum + t_emb[i] * t_emb[i]))
        }
        ] AS target_emb_data

    // Calculate dot product and magnitudes for each colleague embedding
    WITH target, colleague, papers_together, target_emb_data, colleague_embeddings, early_exit_score,
        [c_emb IN colleague_embeddings | 
        {
            embedding: c_emb,
            magnitude: sqrt(reduce(sum = 0.0, i IN range(0, size(c_emb) - 1) | sum + c_emb[i] * c_emb[i]))
        }
        ] AS colleague_emb_data

    // Calculate best embedding overlap
    WITH target, colleague, papers_together, early_exit_score,
        CASE 
        WHEN early_exit_score IS NOT NULL THEN early_exit_score
        ELSE (
            // Calculate all pairwise similarities
            CASE 
            WHEN size(target_emb_data) > 0 AND size(colleague_emb_data) > 0 THEN
                reduce(max_sim = 0.0, t_data IN target_emb_data |
                reduce(current_max = max_sim, c_data IN colleague_emb_data |
                    CASE 
                    WHEN t_data.magnitude = 0 OR c_data.magnitude = 0 THEN current_max
                    ELSE CASE 
                        WHEN (reduce(sum = 0.0, i IN range(0, size(t_data.embedding) - 1) | 
                        sum + t_data.embedding[i] * c_data.embedding[i]) / (t_data.magnitude * c_data.magnitude)) > current_max
                        THEN (reduce(sum = 0.0, i IN range(0, size(t_data.embedding) - 1) | 
                        sum + t_data.embedding[i] * c_data.embedding[i]) / (t_data.magnitude * c_data.magnitude))
                        ELSE current_max
                    END
                    END
                )
                )
            ELSE 0.0
            END
        )
        END AS best_embedding_overlap

    // Same organisation
    OPTIONAL MATCH (target)-[:LINKS_TO]->(shared_org:RicgraphNode {name: "ORGANIZATION_NAME"})-[:LINKS_TO]->(colleague)
    WITH target, colleague, papers_together, best_embedding_overlap, COUNT(shared_org) > 0 AS same_org

    // Get colleague name
    OPTIONAL MATCH (colleague)-[:LINKS_TO]->(name:RicgraphNode {name: "FULL_NAME"})

    // Calculate final score
    WITH colleague.value AS colleague_id,
        name.value AS colleague_name,
        papers_together,
        same_org,
        COALESCE(best_embedding_overlap, 0.0) AS best_embedding_overlap,
        (
        (CASE WHEN papers_together > 0 THEN CASE WHEN papers_together / 5.0 > 1.0 THEN 1.0 ELSE papers_together / 5.0 END ELSE 0.0 END) * 0.5 +
        (CASE WHEN same_org THEN 1.0 ELSE 0.0 END) * 0.3 +
        COALESCE(best_embedding_overlap, 0.0) * 0.2
        ) AS final_score

    RETURN 
    colleague_id,
    colleague_name,
    papers_together,
    same_org,
    ROUND(best_embedding_overlap, 3) AS best_embedding_overlap,
    ROUND(final_score, 3) AS final_score
    ORDER BY final_score DESC
    LIMIT $top_k
    """

    # small extra: try to fetch a coauthor name stored in a linked FULL_NAME node if present
    # we can post-process names by running an additional lookup per returned person if needed

    try:
        with get_graph().session() as session:
            results = session.run(query, target_person_id=person_id, top_k=top_k)
            rows = [dict(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    out = []
    for r in rows:
        out.append({
            "colleague_id": r.get("colleague_id"),
            "colleague_name": r.get("colleague_name"),  # may be null; populate with separate query if required
            "papers_together": int(r.get("papers_together") or 0),
            "same_organization": bool(r.get("same_org")),
            "embedding_similarity": float(r.get("best_embedding_overlap") or 0.0),
            "score": float(r.get("final_score") or 0.0),
        })
    return out
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