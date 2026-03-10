import os
from typing import List, Literal, Optional
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.utils.database_utils.database_utils import get_graph, VECTOR_INDEX_NAME
from app.utils.ai_utils.ai_utils import async_embed, generate
from app.utils.ricgraph_utils.queries import rag_queries 



router = APIRouter()

# --------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------

class EntityRef(BaseModel):
    id: str
    type: Literal["person", "organization"]
    label: str

class RagAskRequest(BaseModel):
    entity: EntityRef
    prompt: str
    top_k: int = 8



# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------

async def get_similar_publications(prompt: str, top_k: int) -> list[dict]:
    prompt_embedding = await async_embed(prompt)

    with get_graph().session() as session:
        results = session.run(rag_queries.SIMILAR_PUBLICATIONS, 
                              indexName=VECTOR_INDEX_NAME, 
                              k=top_k, 
                              prompt_embedding=prompt_embedding)

        top_k_publications = [
        {
            "doi": r["doi"],
            "title": r["title"],
            "year": r["year"],
            "category": r["category"],
            "abstract": r["abstract"]
        }
        for r in results
        ]
        return top_k_publications    
    
def format_similar_publications_for_rag(similar_publications: list[dict]) -> str:
    """
    Turn a list of similar publications into a single string for RAG context.
    Each publications is formatted with its DOI, title, year, and optionally category and abstract.
    """
    lines = []
    for doc in similar_publications:
        parts = [
            f"DOI: {doc.get('doi', 'available')}",
            f"Title: {doc.get('title', 'not available')}",
            f"Year: {doc.get('year', 'available')}"
        ]
        if "category" in doc:
            parts.append(f"Category: {doc['category']}")
        if "abstract" in doc:
            parts.append(f"Abstract: {doc['text']}")
        lines.append(" | ".join(parts))


    # Join all documents with double newlines to separate them clearly
    return "\n\n".join(lines)

def format_entity_context(entity: EntityRef) -> str:
    """
    Returns a string instructing the AI that the prompt is about a given entity.
    """
    return (
        f"The following user query is related to a {entity.type} named '{entity.label}.'"
    )

# --------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------


@router.post("/generate", response_model=str)
async def rag_ask(req: RagAskRequest) -> str:

    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")

    similar_docs = await get_similar_publications(req.prompt, 10)
    rag_context = format_similar_publications_for_rag(similar_docs)
    entity_context = format_entity_context(req.entity)

    final_prompt = f"{entity_context}\n\n{rag_context}\n\n{req.prompt}"

    answer = await generate(final_prompt)
    response = answer.get("response")
    if response is None:
        raise ValueError("AI response missing")
    return response