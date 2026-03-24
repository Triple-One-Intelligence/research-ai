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




@router.post("/top_colleagueList", response_model=list[ColleagueOut])
def top_colleagues(req: TopColleaguesRequest):
    person_id = req.person_id
    topK = req.top_n

    query = """
    // Step 1: Find all potential colleagues and their co-authored publications
    MATCH (target:RicgraphNode {name: "person-root", value: $target_person_id})
    MATCH (target)-[:LINKS_TO]->(publication:RicgraphNode {name: "DOI"})
    MATCH (publication)-[:LINKS_TO]->(colleague:RicgraphNode {name: "person-root"})
    WHERE colleague.value <> target.value

    WITH DISTINCT colleague, target, publication
    WITH colleague, target, COLLECT(DISTINCT publication.value) AS coauthor_publications

    // Step 2: Get all publications for target
    MATCH (target)-[:LINKS_TO]->(targetPub:RicgraphNode {name: "DOI"})
    WITH colleague, target, coauthor_publications, COLLECT(DISTINCT targetPub.value) AS target_publications

    // Step 3: Get all publications for colleague (excluding co-authored)
    MATCH (colleague)-[:LINKS_TO]->(colleaguePub:RicgraphNode {name: "DOI"})
    WHERE NOT colleaguePub.value IN coauthor_publications
    WITH colleague, target, coauthor_publications, target_publications, 
        COLLECT(DISTINCT colleaguePub.value) AS colleague_publications

    // Step 4: Get organization connections
    MATCH (target)-[:LINKS_TO]->(targetOrg:RicgraphNode {name: "ORGANIZATION_NAME"})
    WITH colleague, target, coauthor_publications, target_publications, colleague_publications,
        COLLECT(DISTINCT targetOrg.value) AS target_orgs

    MATCH (colleague)-[:LINKS_TO]->(colleagueOrg:RicgraphNode {name: "ORGANIZATION_NAME"})
    WITH colleague, target, coauthor_publications, target_publications, colleague_publications, target_orgs,
        COLLECT(DISTINCT colleagueOrg.value) AS colleague_orgs

    // Step 5: Calculate basic metrics
    WITH colleague, target, coauthor_publications, target_publications, colleague_publications,
        target_orgs, colleague_orgs,
        SIZE(coauthor_publications) AS papers_together,
        SIZE([org IN target_orgs WHERE org IN colleague_orgs]) > 0 AS same_organisation

    // Step 6: Get colleague name
    MATCH (colleague)-[:LINKS_TO]->(name:RicgraphNode {name: "FULL_NAME"})
    WITH colleague, target, coauthor_publications, target_publications, colleague_publications,
        papers_together, same_organisation, name.value AS colleague_name

    // Step 7: Calculate embedding overlap using manual cosine similarity
    UNWIND target_publications AS targetPubId
    UNWIND colleague_publications AS colleaguePubId
    MATCH (targetPub:RicgraphNode {name: "DOI", value: targetPubId})
    MATCH (colleaguePub:RicgraphNode {name: "DOI", value: colleaguePubId})

    WITH colleague, target, papers_together, same_organisation, colleague_name,
        targetPub.embedding AS vec1, colleaguePub.embedding AS vec2,
        // Cosine similarity: dot_product / (magnitude1 * magnitude2)
        REDUCE(dot = 0.0, i IN RANGE(0, SIZE(targetPub.embedding) - 1) | 
        dot + (targetPub.embedding[i] * colleaguePub.embedding[i])
        ) AS dot_product,
        SQRT(REDUCE(sum = 0.0, i IN RANGE(0, SIZE(targetPub.embedding) - 1) | 
        sum + (targetPub.embedding[i] * targetPub.embedding[i])
        )) AS magnitude1,
        SQRT(REDUCE(sum = 0.0, i IN RANGE(0, SIZE(colleaguePub.embedding) - 1) | 
        sum + (colleaguePub.embedding[i] * colleaguePub.embedding[i])
        )) AS magnitude2

    WITH colleague, target, papers_together, same_organisation, colleague_name,
        CASE 
        WHEN magnitude1 = 0 OR magnitude2 = 0 THEN 0.0
        ELSE dot_product / (magnitude1 * magnitude2)
        END AS embedding_score

    WITH colleague, target, papers_together, same_organisation, colleague_name,
        MAX(embedding_score) AS best_embedding_overlap

    // Step 8: Calculate final score and return
    WITH colleague.value AS colleague_id, 
        colleague_name,
        papers_together,
        same_organisation,
        best_embedding_overlap,
        (papers_together * 3.0) + 
        (CASE WHEN same_organisation THEN 2.0 ELSE 0.0 END) +
        (best_embedding_overlap * 1.0) AS final_score

    RETURN colleague_id, colleague_name, papers_together, same_organisation, 
        best_embedding_overlap, final_score
    ORDER BY final_score DESC
    """

    # small extra: try to fetch a coauthor name stored in a linked FULL_NAME node if present
    # we can post-process names by running an additional lookup per returned person if needed

    try:
        with get_graph().session() as session:
            results = session.run(query, target_person_id=person_id)
            rows = [dict(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    out = []
    for r in rows:
        out.append({
            "person_id": r.get("person_id"),
            "name": r.get("name"),  # may be null; populate with separate query if required
            "coauthor_publications": int(r.get("shared_pub_count") or 0),
            "same_organization": bool(r.get("same_org")),
            "embedding_similarity": float(r.get("embedding_similarity") or 0.0),
            "score": float(r.get("score") or 0.0),
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