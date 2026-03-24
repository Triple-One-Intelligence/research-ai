import logging

from app.utils.schemas.ai import (
    ChatRequest, EntityRef, Message, TopColleaguesRequest, ColleagueOut, SimilarPublication
)

log = logging.getLogger(__name__)

def format_raw_name(rawName: str) -> str:
    """
    Tries converting raw RicGraph names 
    Such as:    "Doe, Jane#"0a12baa3-b456-7c89-dd91-2e34567e8ee9"
    To:         "Jane Doe"
    """
    try:
        name_part: list[str] = rawName.split('#')
        parts = name_part[0].split(', ')
        if len(parts) != 2:
            return rawName
        last_name, first_name = parts

            
        if last_name.strip() and first_name.strip():
            return f"{first_name} {last_name}"
        else:
            return rawName

    except Exception:
        return rawName

def format_colleagues_for_llm(colleagues: list[ColleagueOut]) -> str:
    """
    Format a list of ColleagueOut objects into a readable string for LLM consumption.
    """
    if not colleagues:
        return "No colleagues found."
    
    formatted_lines = ["Top Colleagues:"]
    
    for i, colleague in enumerate(colleagues, 1):
        line = (
            f"{i}. {colleague.name or 'Unknown'} "
            f"(ID: {colleague.person_id}) - "
            f"Score: {colleague.score:.2f} | "
            f"Co-authored: {colleague.coauthor_publications} publications | "
            f"Same organization: {colleague.same_organization} | "
            f"Embedding similarity: {colleague.embedding_similarity:.3f}"
        )
        formatted_lines.append(line)
    
    return "\n".join(formatted_lines)

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


def build_rag_system_prompt(entity: EntityRef | None, publications_context: str) -> str:
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


