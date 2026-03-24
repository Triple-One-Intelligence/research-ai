"""Utilities for retrieving and formatting entity connections from the Ricgraph database."""

import logging
from typing import Any, TypedDict

from app.utils.database_utils import database_utils
from app.utils.schemas import Person, Publication, Organization
from app.utils.schemas.connections import Member
from app.utils.ricgraph_utils.queries.connections_queries import (
    PERSON_PUBLICATIONS, PERSON_COLLABORATORS,
    PERSON_ORGANIZATIONS, ORG_MEMBERS, ORG_PUBLICATIONS, ORG_RELATED_ORGS,
)

log = logging.getLogger(__name__)

EXCLUDE_CATEGORIES: list[str] = []
"""Categories of publications to exclude from connections queries.

An empty list means "no exclusions". This is passed directly into the Cypher
queries via the `$excludeCategories` parameter.
"""

class ConnectionsError(RuntimeError):
    pass

class InvalidEntityTypeError(ValueError):
    pass

def clean_name(raw: str | None) -> str:
    if not raw:
        return ""
    name = raw.split("#")[0].strip()
    return name[1:].strip() if name.startswith(",") else name

def clean_title(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, str):
        return raw.strip() or None
    return None

def parse_year(raw: Any) -> int | None:
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return int(raw)
        except ValueError:
            return None
    return None

PeopleOrMembers = Person | Member

class ConnectionsPayload(TypedDict):
    collaborators: list[Person]
    publications: list[Publication]
    organizations: list[Organization]
    members: list[Member]

def format_people(rows: list[dict[str, Any]], *, as_members: bool = False) -> list[PeopleOrMembers]:
    """Format person rows as Person or Member models."""
    out: list[PeopleOrMembers] = []
    for row in rows:
        name = clean_name(row.get("rawName"))
        if as_members:
            out.append(Member(author_id=row["author_id"], name=name))
        else:
            out.append(Person(author_id=row["author_id"], name=name))
    return out

def format_organizations(rows: list[dict[str, Any]]) -> list[Organization]:
    return [Organization(organization_id=row["organization_id"], name=row["name"]) for row in rows]

def format_publications(rows: list[dict[str, Any]]) -> list[Publication]:
    grouped: dict[str, list[Publication]] = {}
    no_title: list[Publication] = []

    for row in rows:
        title = clean_title(row.get("title"))
        entry = Publication(
            doi=row["doi"], title=title,
            year=parse_year(row.get("year")), category=row.get("category")
        )
        if title is not None:
            grouped.setdefault(title.lower(), []).append(entry)
        else:
            no_title.append(entry)

    out: list[Publication] = []
    for entries in grouped.values():
        rep = entries[0].model_copy()
        if len(entries) > 1:
            versions = [{"doi": entry.doi, "year": entry.year, "category": entry.category}
                        for entry in entries]
            rep.versions = versions if versions else None
        out.append(rep)

    out.extend(no_title)
    out.sort(key=lambda publication: (publication.year is not None, publication.year or 0), reverse=True)
    return out

def person_connections(
    entity_id: str,
    max_publications: int,
    max_collaborators: int,
    max_organizations: int,
) -> ConnectionsPayload:
    driver = database_utils.get_graph()

    with driver.session() as session:
        collaborators = session.run(
            PERSON_COLLABORATORS, rootValue=entity_id, excludeCategories=EXCLUDE_CATEGORIES, limit=max_collaborators
        ).data()
        publications = session.run(
            PERSON_PUBLICATIONS, rootValue=entity_id, excludeCategories=EXCLUDE_CATEGORIES, limit=max_publications
        ).data()
        organizations = session.run(
            PERSON_ORGANIZATIONS, rootValue=entity_id, limit=max_organizations
        ).data()

    return {
        "collaborators": format_people(collaborators),
        "publications": format_publications(publications),
        "organizations": format_organizations(organizations),
        "members": [],
    }

def organization_connections(
    entity_id: str,
    max_publications: int,
    max_organizations: int,
    max_members: int,
) -> ConnectionsPayload:
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

def get_connections(
    entity_id: str,
    entity_type: str,
    max_publications: int = 50,
    max_collaborators: int = 50,
    max_organizations: int = 50,
    max_members: int = 50,
) -> ConnectionsPayload:
    if entity_type not in ("person", "organization"):
        raise InvalidEntityTypeError("entity_type must be 'person' or 'organization'")

    try:
        if entity_type == "person":
            return person_connections(entity_id, max_publications, max_collaborators, max_organizations)
        return organization_connections(entity_id, max_publications, max_organizations, max_members)
    except Exception as exception:
        log.error("Connections query failed for entity_id=%r", entity_id)
        raise ConnectionsError("Connections query failed") from exception
