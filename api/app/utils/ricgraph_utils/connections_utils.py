from typing import Any, Dict, List, Optional
from app.utils.database_utils import database_utils
from app.utils.schemas import Person, Publication, Organization
from app.utils.schemas.connections import Member
from app.utils.ricgraph_utils.queries.connections_queries import (
    PERSON_PUBLICATIONS, PERSON_COLLABORATORS,
    PERSON_ORGANIZATIONS, ORG_MEMBERS, ORG_PUBLICATIONS, ORG_RELATED_ORGS,
)

EXCLUDE_CATEGORIES: List[str] = []

class ConnectionsError(RuntimeError):
    pass

class InvalidEntityTypeError(ValueError):
    pass

def clean_name(raw: Optional[str]) -> str:
    if not raw:
        return ""
    name = raw.split("#")[0].strip()
    return name[1:].strip() if name.startswith(",") else name

def clean_title(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, str):
        return raw.strip() or None
    return None

def parse_year(raw: Any) -> Optional[int]:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return int(raw)
        except ValueError:
            return None
    return None

def format_people(rows: List[Dict[str, Any]], *, as_members: bool = False) -> list:
    """Format person rows as Person or Member models."""
    out: list = []
    for row in rows:
        name = clean_name(row.get("rawName"))
        if as_members:
            out.append(Member(author_id=row["author_id"], name=name, role=None))
        else:
            out.append(Person(author_id=row["author_id"], name=name))
    return out

def format_organizations(rows: List[Dict[str, Any]]) -> List[Organization]:
    return [Organization(organization_id=r["organization_id"], name=r["name"]) for r in rows]

def format_publications(rows: List[Dict[str, Any]]) -> List[Publication]:
    grouped: Dict[str, List[Publication]] = {}
    no_title: List[Publication] = []

    for row in rows:
        title = clean_title(row.get("title"))
        entry = Publication(
            doi=row["doi"], title=title, publication_rootid=None,
            year=parse_year(row.get("year")), category=row.get("category"),
            name=None,
        )
        if title is not None:
            grouped.setdefault(title.lower(), []).append(entry)
        else:
            no_title.append(entry)

    out: List[Publication] = []
    for entries in grouped.values():
        rep = entries[0].model_copy()
        if len(entries) > 1:
            versions = [{"doi": e.doi, "year": e.year, "category": e.category}
                        for e in entries]
            rep.versions = versions if versions else None
        out.append(rep)

    out.extend(no_title)
    out.sort(key=lambda p: (p.year is not None, p.year or 0), reverse=True)
    return out

def person_connections(entity_id: str, max_publications: int, max_collaborators: int, max_organizations: int) -> Dict[str, Any]:
    driver = database_utils.get_graph()

    with driver.session() as session:
        collaborators = session.run(
            PERSON_COLLABORATORS, rootKey=entity_id, excludeCategories=EXCLUDE_CATEGORIES, limit=max_collaborators
        ).data()
        publications = session.run(
            PERSON_PUBLICATIONS, rootKey=entity_id, excludeCategories=EXCLUDE_CATEGORIES, limit=max_publications
        ).data()
        organizations = session.run(
            PERSON_ORGANIZATIONS, rootKey=entity_id, limit=max_organizations
        ).data()

    return {
        "collaborators": format_people(collaborators),
        "publications": format_publications(publications),
        "organizations": format_organizations(organizations),
        "members": [],
    }

def organization_connections(entity_id: str, max_publications: int, max_organizations: int, max_members: int) -> Dict[str, Any]:
    driver = database_utils.get_graph()
    with driver.session() as session:
        publications = session.run(
            ORG_PUBLICATIONS, entityId=entity_id, excludeCategories=EXCLUDE_CATEGORIES, limit=max_publications
        ).data()
        organizations = session.run(
            ORG_RELATED_ORGS, entityId=entity_id, limit=max_organizations
        ).data()
        members = session.run(
            ORG_MEMBERS, entityId=entity_id, limit=max_members
        ).data()

    return {
        "collaborators": [],
        "publications": format_publications(publications),
        "organizations": format_organizations(organizations),
        "members": format_people(members, as_members=True),
    }

def get_connections(entity_id: str, entity_type: str, max_publications: int = 50, max_collaborators: int = 50, max_organizations: int = 50, max_members: int = 50) -> Dict[str, Any]:
    if entity_type not in ("person", "organization"):
        raise InvalidEntityTypeError("entity_type must be 'person' or 'organization'")

    try:
        if entity_type == "person":
            return person_connections(entity_id, max_publications, max_collaborators, max_organizations)
        return organization_connections(entity_id, max_publications, max_organizations, max_members)
    except Exception as exc:
        print(f"Connections query failed for entity_id={entity_id!r}")
        raise ConnectionsError("Connections query failed") from exc
