"""
System prompt context builders for each pipeline.

- executive_summary:   vector search (publications) + graph (collaborators, orgs ranked by shared pubs)
- top_organizations:   graph only — traverses co-authors to their orgs, ranked by shared pub count
                       (PERSON_ORGANIZATIONS returns own affiliations, not collaboration orgs)
- top_collaborators:   graph only — co-authors ranked by shared pub count
- recent_publications: graph sorted by year DESC + abstract lookup by DOI (vector search doesn't sort by time)
"""
from app.utils.ricgraph_utils.connections_utils import get_connections, clean_name
from app.utils.schemas.ai import EntityRef
from app.prompts.system_prompt import SYSTEM_PROMPT
from app.routers.ai import get_similar_publications, format_entity_context
from app.pipelines.graph import (
    fetch_abstracts, person_collaborators_ranked, person_collab_organizations, org_related_orgs_ranked,
)
from app.pipelines.budget import data_budget, tokens, fit_publications, fit_ranked_lines


def _build(entity: EntityRef, *sections: str) -> str:
    return "\n\n".join([SYSTEM_PROMPT, format_entity_context(entity), *filter(None, sections)])  # filter drops empty sections


def _pub_blocks(fitted: list[str]) -> str:
    return "\n\n".join(f"Document [{i + 1}]\n{block}" for i, block in enumerate(fitted))


async def executive_summary_context(entity: EntityRef, prompt: str) -> str:
    similar_docs = await get_similar_publications(prompt, entity, top_k=10)
    graph_sections = []

    if entity.type == "person":
        if collabs := person_collaborators_ranked(entity.id, limit=20):
            graph_sections.append("Known top collaborators:\n" + "\n".join(
                f"  - {clean_name(r['rawName'])} ({r['sharedPubs']} shared publications)" for r in collabs
            ))
        if orgs := person_collab_organizations(entity.id, limit=20):
            graph_sections.append("Known collaborating organizations:\n" + "\n".join(
                f"  - {r['name']} ({r['sharedPubs']} shared publications)" for r in orgs
            ))
    else:
        members = get_connections(entity.id, entity.type, max_publications=0, max_collaborators=0, max_organizations=0, max_members=20)["members"]
        if members:
            graph_sections.append("Known members:\n" + "\n".join(f"  - {m.name}" for m in members if m.name))
        if orgs := org_related_orgs_ranked(entity.id, limit=20):
            graph_sections.append("Known related organizations:\n" + "\n".join(
                f"  - {r['name']} ({r['sharedMembers']} shared members)" for r in orgs
            ))

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
    budget = data_budget(entity, prompt)

    if entity.type == "person":
        orgs = person_collab_organizations(entity.id, limit=50)
        fitted = fit_ranked_lines([f"{i + 1}. {r['name']} ({r['sharedPubs']} shared publications)" for i, r in enumerate(orgs)], budget)
        section = "Collaborating organizations ranked by shared publications:\n" + "\n".join(fitted) if fitted else "No collaborating organizations found."
    else:
        orgs = org_related_orgs_ranked(entity.id, limit=50)
        fitted = fit_ranked_lines([f"{i + 1}. {r['name']} ({r['sharedMembers']} shared members)" for i, r in enumerate(orgs)], budget)
        section = "Related organizations ranked by shared members:\n" + "\n".join(fitted) if fitted else "No related organizations found."

    return _build(entity, section)


def top_collaborators_context(entity: EntityRef, prompt: str) -> str:
    budget = data_budget(entity, prompt)

    if entity.type == "person":
        collabs = person_collaborators_ranked(entity.id, limit=50)
        fitted = fit_ranked_lines([f"{i + 1}. {clean_name(r['rawName'])} ({r['sharedPubs']} shared publications)" for i, r in enumerate(collabs)], budget)
        section = "Collaborators ranked by shared publications:\n" + "\n".join(fitted) if fitted else "No collaborators found."
    else:
        members = get_connections(entity.id, entity.type, max_publications=0, max_collaborators=0, max_organizations=0, max_members=50)["members"]
        fitted = fit_ranked_lines([f"{i + 1}. {m.name}" for i, m in enumerate(members) if m.name], budget)
        section = "Organization members:\n" + "\n".join(fitted) if fitted else "No members found."

    return _build(entity, section)


def recent_publications_context(entity: EntityRef, prompt: str) -> str:
    publications = get_connections(entity.id, entity.type, max_publications=50, max_collaborators=0, max_organizations=0, max_members=0)["publications"]
    abstracts = fetch_abstracts([pub.doi for pub in publications])

    pubs_data = [
        (
            "\n".join(filter(None, [
                f"DOI: {pub.doi}",
                f"Title: {pub.title}" if pub.title else None,
                f"Year: {pub.year}" if pub.year else None,
                f"Category: {pub.category}" if pub.category else None,
            ])),
            f"Abstract: {abstracts[pub.doi]}" if pub.doi in abstracts else "",
        )
        for pub in publications
    ]
    fitted = fit_publications(pubs_data, data_budget(entity, prompt))
    return _build(entity, _pub_blocks(fitted) if fitted else "No publications found.")
