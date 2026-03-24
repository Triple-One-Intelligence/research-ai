"""
System prompt context builders for each pipeline.

- executive_summary:   vector search (publications) + graph (affiliations, collaborators ranked by shared pubs)
- top_organizations:   graph only — traverses co-authors to their orgs, ranked by shared pub count
- top_collaborators:   graph only — co-authors ranked by shared pub count (person); external collaborators ranked by shared pubs (org)
- recent_publications: graph sorted by year DESC + abstract lookup by DOI (vector search doesn't sort by time)
"""
import asyncio

from app.utils.ricgraph_utils.connections_utils import get_connections, clean_name
from app.utils.schemas.ai import EntityRef
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.routers.ai import get_similar_publications, format_entity_context
from app.pipelines.graph import (
    fetch_abstracts, person_collaborators_ranked, person_collab_organizations,
    org_related_orgs_ranked, org_external_collaborators_ranked,
)
from app.pipelines.budget import data_budget, tokens, fit_publications, fit_ranked_lines


def _build(entity: EntityRef, *sections: str) -> str:
    """Joins system prompt, entity context, and data sections."""
    return "\n\n".join([SYSTEM_PROMPT, format_entity_context(entity), *filter(None, sections)])  # filter drops empty sections


def _pub_blocks(fitted: list[str]) -> str:
    """Formats fitted publications as numbered Document [n] blocks."""
    return "\n\n".join(f"Document [{i + 1}]\n{block}" for i, block in enumerate(fitted))


async def _person_graph_sections(entity_id: str) -> list[str]:
    """Fetches affiliations and top collaborators in parallel."""
    affiliations_conn, collabs = await asyncio.gather(
        asyncio.to_thread(
            get_connections, entity_id, "person",
            max_publications=0, max_collaborators=0, max_organizations=10, max_members=0,
        ),
        asyncio.to_thread(person_collaborators_ranked, entity_id, 20),
    )
    sections = []
    if affiliations := affiliations_conn["organizations"]:
        sections.append("Known affiliations:\n" + "\n".join(
            f"  - {org.name}" for org in affiliations if org.name
        ))
    if collabs:
        sections.append("Known top collaborators:\n" + "\n".join(
            f"  - {clean_name(r['rawName'])} ({r['sharedPubs']} shared publications)" for r in collabs
        ))
    return sections


async def _org_graph_sections(entity_id: str, entity_type: str) -> list[str]:
    """Fetches members and related orgs in parallel."""
    members_conn, orgs = await asyncio.gather(
        asyncio.to_thread(
            get_connections, entity_id, entity_type,
            max_publications=0, max_collaborators=0, max_organizations=0, max_members=20,
        ),
        asyncio.to_thread(org_related_orgs_ranked, entity_id, 20),
    )
    sections = []
    if members := members_conn["members"]:
        sections.append("Known members:\n" + "\n".join(f"  - {m.name}" for m in members if m.name))
    if orgs:
        sections.append("Known related organizations:\n" + "\n".join(
            f"  - {r['name']} ({r['sharedMembers']} shared members)" for r in orgs
        ))
    return sections


async def executive_summary_context(entity: EntityRef, prompt: str) -> str:
    """Vector search + graph sections, budget split between the two."""
    graph_fetch = (
        _person_graph_sections(entity.id)
        if entity.type == "person"
        else _org_graph_sections(entity.id, entity.type)
    )
    similar_docs, graph_sections = await asyncio.gather(
        get_similar_publications(prompt, entity, top_k=10),
        graph_fetch,
    )
    graph_text = "\n\n".join(graph_sections)
    pubs_budget = max(0, data_budget(entity, prompt) - tokens(graph_text))  # graph context occupies part of the budget

    pubs_data = [
        (
            "\n".join(filter(None, [
                f"DOI: {pub['doi']}",
                f"Title: {pub['title']}" if pub.get("title") else None,
                f"Year: {pub['year']}" if pub.get("year") else None,
                f"Category: {pub['category']}" if pub.get("category") else None,
            ])),
            f"Abstract: {pub['abstract']}" if pub.get("abstract") else "",
        )
        for pub in similar_docs
    ]
    fitted = fit_publications(pubs_data, pubs_budget)
    return _build(entity, graph_text, _pub_blocks(fitted) if fitted else "No publications with abstracts were found.")


def top_organizations_context(entity: EntityRef, prompt: str) -> str:
    """Graph only — collaborating orgs ranked by shared pubs (person) or shared members (org)."""
    budget = data_budget(entity, prompt)

    if entity.type == "person":
        orgs = person_collab_organizations(entity.id, limit=50)
        fitted = fit_ranked_lines([f"{i + 1}. {r['name']} ({r['sharedPubs']} shared publications)" for i, r in enumerate(orgs)], budget)
        section = ("Collaborating organizations ranked by shared publications:\n" + "\n".join(fitted)) if fitted else "No collaborating organizations found."
    else:
        orgs = org_related_orgs_ranked(entity.id, limit=50)
        fitted = fit_ranked_lines([f"{i + 1}. {r['name']} ({r['sharedMembers']} shared members)" for i, r in enumerate(orgs)], budget)
        section = ("Related organizations ranked by shared members:\n" + "\n".join(fitted)) if fitted else "No related organizations found."

    return _build(entity, section)


def top_collaborators_context(entity: EntityRef, prompt: str) -> str:
    """Graph only — co-authors ranked by shared pubs (person) or external collaborators (org)."""
    budget = data_budget(entity, prompt)

    if entity.type == "person":
        collabs = person_collaborators_ranked(entity.id, limit=50)
        fitted = fit_ranked_lines([f"{i + 1}. {clean_name(r['rawName'])} ({r['sharedPubs']} shared publications)" for i, r in enumerate(collabs)], budget)
        section = ("Collaborators ranked by shared publications:\n" + "\n".join(fitted)) if fitted else "No collaborators found."
    else:
        collabs = org_external_collaborators_ranked(entity.id, limit=50)
        fitted = fit_ranked_lines([f"{i + 1}. {clean_name(r['rawName'])} ({r['sharedPubs']} shared publications)" for i, r in enumerate(collabs)], budget)
        section = ("External collaborators ranked by shared publications:\n" + "\n".join(fitted)) if fitted else "No external collaborators found."

    return _build(entity, section)


def _find_abstract(pub, abstracts: dict[str, str]) -> str:
    """Looks up abstract by DOI, falling back to versioned DOIs."""
    if pub.doi in abstracts:
        return abstracts[pub.doi]
    for v in (pub.versions or []):
        if v.get("doi") in abstracts:
            return abstracts[v["doi"]]
    return ""


def recent_publications_context(entity: EntityRef, prompt: str) -> str:
    """Graph sorted by year DESC + abstract lookup by DOI."""
    publications = get_connections(entity.id, entity.type, max_publications=50, max_collaborators=0, max_organizations=0, max_members=0)["publications"]

    all_dois = [pub.doi for pub in publications]
    for pub in publications:
        if pub.versions:
            all_dois.extend(v["doi"] for v in pub.versions if v.get("doi"))
    abstracts = fetch_abstracts(all_dois)

    pubs_data = []
    for pub in publications:
        abstract = _find_abstract(pub, abstracts)
        pubs_data.append((
            "\n".join(filter(None, [
                f"DOI: {pub.doi}",
                f"Title: {pub.title}" if pub.title else None,
                f"Year: {pub.year}" if pub.year else None,
                f"Category: {pub.category}" if pub.category else None,
            ])),
            f"Abstract: {abstract}" if abstract else "",
        ))
    fitted = fit_publications(pubs_data, data_budget(entity, prompt))
    return _build(entity, _pub_blocks(fitted) if fitted else "No publications found.")
