import logging
import json
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.utils.ai_utils import format_for_ai as aiF
from app.utils.database_utils.database_utils import get_graph
# Refactoring: Shotgun Surgery fix — constants centralized in ai_utils
from app.utils.ai_utils.ai_utils import (
    AI_SERVICE_URL, CHAT_MODEL, CHAT_MAX_TOKENS, async_embed, send_async_ai_request,
)
from app.utils.ricgraph_utils.queries import rag_queries
from app.utils.schemas.ai import (
    EntityRef, Message, ColleagueOut, SimilarPublication
)



router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/prompt_top5publications")
def _stream_5mostRecentPublications_response(selected_entity: EntityRef, language: str = "English") -> StreamingResponse:

    USER_PROMPT = """Generate a short summary regarding the selected documents if availible and list them off. 
    Start of by cyting the name of the entity and give a small list of all the given documents.
    Make an effort to include all provided documents. If a document contains to little information, note this.
    Try ending the response with a short compliment regarding the entity, based on the prevously mentioned documents.
    Styling: For each document make the title bold and italic. Start the Response with 'The five most recent publications for' and the entity name in H1."""
    
    # Retrieve the latest publications from Neo4j 
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
    
    # Format the context to a string so the ai make use of it
    rag_context = aiF.format_similar_publications_for_rag(documentList)
    system_prompt = aiF.build_rag_system_prompt(selected_entity, rag_context)

    messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": "Respond in: " + language},
            {"role": "user", "content": USER_PROMPT},
        ]
    
    # Send it all to the AI
    return streaming_chat_response(messages)




@router.post("/top_colleagues", response_model=list[ColleagueOut])
def top_colleagues(selected_entity: EntityRef, top_k_colleagues: int = 10, language: str = "English"):
    person_id = selected_entity.id
    top_k = top_k_colleagues

    #TODO: improve user prompt
    USER_PROMPT = """Symply list out the provided list of colleagues in a pretty way. Do not stray from the given order"""

    # Get a list of colleagues ranked on how ralated the are to the original entity
    # Further insights into ranking can be gain by looking at the Neo4j cypher (query)
    query = rag_queries.get_TOPK_COLLEAGUES
    try:
        with get_graph().session() as session:
            results = session.run(query, target_person_id=person_id, top_k=top_k)
            rows = [dict(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    rawColleagues: list[ColleagueOut] = []
    for r in rows:
        rawColleagues.append(ColleagueOut(
            person_id = r.get("colleague_id"),
            name = aiF.format_raw_name(r.get("colleague_name")),
            coauthor_publications = int(r.get("papers_together") or 0),
            same_organization = bool(r.get("same_org")),
            embedding_similarity = float(r.get("best_embedding_overlap") or 0.0),
            score = float(r.get("final_score") or 0.0),
        ))
    
    # Format the raw data in such a way the ai can use it (all to a string)
    rag_context = aiF.format_colleagues_for_llm(rawColleagues)
    system_prompt = aiF.build_rag_system_prompt(selected_entity, rag_context)

    messages: list[Message] = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": "Respond in: " + language},
            {"role": "user", "content": USER_PROMPT},
        ]
    
    # Send it all to the AI
    return streaming_chat_response(messages)

def streaming_chat_response(messages: list[Message]) -> StreamingResponse:
    """
    Return a StreamingResponse that proxies Ollama /api/chat as SSE.

    Pattern: Proxy — wraps the Ollama API and transforms its response format.
    """
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