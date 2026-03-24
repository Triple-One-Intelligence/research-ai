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
    // params: $targetId, $topK (e.g. 20)
    MATCH (target:RicgraphNode {name:'person-root', value: $targetId})

    // 1) target DOIs with embeddings and target centroid
    OPTIONAL MATCH (target)-[:LINKS_TO]->(td:RicgraphNode {name:'DOI'})
    WHERE td.embedding IS NOT NULL
    WITH target, collect(td) AS target_dois
    WITH target, target_dois,
        CASE WHEN size(target_dois)>0 THEN
        [i IN range(0, size(target_dois[0].embedding)-1) |
            toFloat(reduce(s = 0.0, d IN target_dois | s + toFloat(d.embedding[i]))) / toFloat(size(target_dois))
        ]
        ELSE NULL END AS target_centroid

    // 2) candidates: coauthors (via DOI) and org-mates
    OPTIONAL MATCH (target)-[:LINKS_TO]->(d:RicgraphNode {name:'DOI'})<-[:LINKS_TO]-(coauthor:RicgraphNode {name:'person-root'})
    OPTIONAL MATCH (target)-[:LINKS_TO]->(o:RicgraphNode {name:'ORGANIZATION_NAME'})<-[:LINKS_TO]-(orgmate:RicgraphNode {name:'person-root'})
    WITH target, target_dois, target_centroid, coauthor, orgmate
    WITH target, target_dois, target_centroid, collect(coauthor) + collect(orgmate) AS raw_list
    UNWIND raw_list AS cand
    WITH DISTINCT cand, target_dois, target_centroid
    WHERE cand IS NOT NULL AND cand.value <> $targetId

    // 3) shared pubs and orgs
    OPTIONAL MATCH (target)-[:LINKS_TO]->(shared_d:RicgraphNode {name:'DOI'})<-[:LINKS_TO]-(cand)
    WITH cand, target_dois, target_centroid,
        COUNT(DISTINCT shared_d) AS shared_pub_count,
        collect(DISTINCT shared_d.value) AS shared_doc_values

    OPTIONAL MATCH (target)-[:LINKS_TO]->(shared_o:RicgraphNode {name:'ORGANIZATION_NAME'})<-[:LINKS_TO]-(cand)
    WITH cand, target_dois, target_centroid, shared_pub_count, shared_doc_values,
        COUNT(DISTINCT shared_o) AS shared_org_count

    // 4) candidate DOI embeddings -> centroid (if any)
    OPTIONAL MATCH (cand)-[:LINKS_TO]->(cdoi:RicgraphNode {name:'DOI'})
    WHERE cdoi.embedding IS NOT NULL
    WITH cand, target_dois, target_centroid, shared_pub_count, shared_doc_values, shared_org_count,
        collect(cdoi.embedding) AS candidate_embs

    WITH cand, target_dois, target_centroid, shared_pub_count, shared_doc_values, shared_org_count,
        CASE WHEN size(candidate_embs)>0 AND size(candidate_embs[0]) = (CASE WHEN target_centroid IS NULL THEN size(candidate_embs[0]) ELSE size(target_centroid) END) THEN
        [i IN range(0, size(candidate_embs[0]) - 1) |
            toFloat(reduce(s = 0.0, vec IN candidate_embs | s + toFloat(vec[i]))) / toFloat(size(candidate_embs))
        ]
        ELSE NULL END AS candidate_centroid

    // 5) compute best embedding_overlap score WITHOUT CALL: cosine similarity between candidate_centroid and each target DOI embedding, take max
    WITH cand, target_dois, shared_pub_count, shared_doc_values, shared_org_count, candidate_centroid
    UNWIND CASE WHEN candidate_centroid IS NOT NULL THEN target_dois ELSE [] END AS td
    WITH cand, shared_pub_count, shared_doc_values, shared_org_count, candidate_centroid, td
    WHERE td.embedding IS NOT NULL AND candidate_centroid IS NOT NULL AND size(td.embedding) = size(candidate_centroid)
    WITH cand, shared_pub_count, shared_doc_values, shared_org_count, candidate_centroid, td,
        reduce(acc = 0.0, i IN range(0, size(candidate_centroid)-1) | acc + toFloat(candidate_centroid[i]) * toFloat(td.embedding[i])) AS dot,
        sqrt(reduce(acc = 0.0, i IN range(0, size(candidate_centroid)-1) | acc + toFloat(candidate_centroid[i]) * toFloat(candidate_centroid[i]))) AS norm_c,
        sqrt(reduce(acc = 0.0, i IN range(0, size(td.embedding)-1) | acc + toFloat(td.embedding[i]) * toFloat(td.embedding[i]))) AS norm_t
    WITH cand, shared_pub_count, shared_doc_values, shared_org_count,
        CASE WHEN norm_c > 0.0 AND norm_t > 0.0 THEN dot / (norm_c * norm_t) ELSE 0.0 END AS sim
    WITH cand, shared_pub_count, shared_doc_values, shared_org_count, coalesce(max(sim), 0.0) AS best_score

    OPTIONAL MATCH (cand)-[:LINKS_TO]->(fn:RicgraphNode {name:'FULL_NAME'})

    // 6) final scoring (weights as params or inline)
    WITH cand.value AS person_id,
        coalesce(fn.value, NULL) AS name,
        shared_pub_count,
        (shared_org_count > 0) AS same_org,
        best_score AS embedding_similarity,
        (
        (CASE WHEN shared_pub_count > 0 THEN log(shared_pub_count + 1) ELSE 0 END) * 3.0
        + (CASE WHEN shared_org_count > 0 THEN 2.5 ELSE 0 END)
        + (best_score * 2.0)
        + (CASE WHEN shared_pub_count > 0 AND shared_org_count > 0 THEN 2.0 ELSE 0 END)
        ) AS score
    RETURN person_id, name, shared_pub_count, same_org, embedding_similarity, score
    ORDER BY score DESC
    LIMIT coalesce($topK,20);
    """

    # small extra: try to fetch a coauthor name stored in a linked FULL_NAME node if present
    # we can post-process names by running an additional lookup per returned person if needed

    try:
        with get_graph().session() as session:
            results = session.run(query, targetId=person_id, topK=topK)
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