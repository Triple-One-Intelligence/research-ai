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

VALID_ENTITY_TYPES = {"person", "organization"}
def validate_entity_type(entity_type: str) -> None:
    if entity_type not in VALID_ENTITY_TYPES:
        raise InvalidEntityTypeError("entity_type must be 'person' or 'organization'")

def run_query(entity_id: str, query: str, **params: Any) -> list[dict[str, Any]]:
    """Execute a single graph query with unified error handling."""
    try:
        driver = database_utils.get_graph()
        with driver.session() as session:
            return session.run(query, **params).data()
    except Exception as exception:
        log.error("Connections query failed for entity_id=%r", entity_id)
        raise ConnectionsError("Connections query failed") from exception

def run_type_query(
    entity_id: str,
    entity_type: str,
    *,
    person_query: str,
    person_params: dict[str, Any],
    organization_query: str,
    organization_params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute the person/org specific query after validating entity type."""
    validate_entity_type(entity_type)
    if entity_type == "person":
        return run_query(entity_id, person_query, **person_params)
    return run_query(entity_id, organization_query, **organization_params)

def clean_name(raw: str | None) -> str:
    """Normalize a raw person name from graph values."""
    if not raw:
        return ""
    name = raw.split("#")[0].strip()
    return name[1:].strip() if name.startswith(",") else name

def clean_title(raw: Any) -> str | None:
    """Normalize title values from mixed query payload shapes."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, str):
        return raw.strip() or None
    return None

def parse_year(raw: Any) -> int | None:
    """Parse a year value into an integer when possible."""
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
    """Format person rows as Person or Member models.

    Pattern: Factory Method — creates Person or Member based on as_members flag."""
    out: list[PeopleOrMembers] = []
    for row in rows:
        name = clean_name(row.get("rawName"))
        if as_members:
            out.append(Member(author_id=row["author_id"], name=name))
        else:
            out.append(Person(author_id=row["author_id"], name=name))
    return out

def format_organizations(rows: list[dict[str, Any]]) -> list[Organization]:
    """Convert organization query rows into Organization models."""
    return [Organization(organization_id=row["organization_id"], name=row["name"]) for row in rows]


def normalize_versions(raw_versions: Any) -> list[dict[str, Any]] | None:
    """Normalize optional publication version payloads."""
    if not isinstance(raw_versions, list):
        return None

    versions = [
        {
            "doi": version.get("doi"),
            "year": parse_year(version.get("year")),
            "category": version.get("category"),
        }
        for version in raw_versions
        if isinstance(version, dict)
    ]
    return versions or None


def format_publications(rows: list[dict[str, Any]]) -> list[Publication]:
    """Convert publication rows into Publication models sorted by year."""
    publications: list[Publication] = []
    for row in rows:
        publications.append(Publication(
            doi=row["doi"],
            title=clean_title(row.get("title")),
            year=parse_year(row.get("year")),
            category=row.get("category"),
            versions=normalize_versions(row.get("versions")),
        ))

    publications.sort(key=lambda publication: (publication.year is not None, publication.year or 0), reverse=True)
    return publications

def person_connections(
    entity_id: str,
    max_publications: int,
    max_collaborators: int,
    max_organizations: int,
) -> ConnectionsPayload:
    """Fetch and format collaborators, publications, and organizations for a person."""
    return {
        "collaborators": get_collaborators(entity_id, "person", max_collaborators),
        "publications": get_publications(entity_id, "person", max_publications),
        "organizations": get_organizations(entity_id, "person", max_organizations),
        "members": [],
    }

def organization_connections(
    entity_id: str,
    max_publications: int,
    max_organizations: int,
    max_members: int,
) -> ConnectionsPayload:
    """Fetch and format publications, related organizations, and members for an organization."""
    return {
        "collaborators": [],
        "publications": get_publications(entity_id, "organization", max_publications),
        "organizations": get_organizations(entity_id, "organization", max_organizations),
        "members": get_members(entity_id, "organization", max_members),
    }

# Type-specific retrieval helpers (for per-endpoint queries)

def get_collaborators(
    entity_id: str,
    entity_type: str,
    max_collaborators: int,
    cursor: str | None = None,
) -> list[Person]:
    """Return collaborators for person entities; organizations have none."""
    validate_entity_type(entity_type)

    if entity_type == "organization":
        return []

    collaborators = run_query(
        entity_id,
        PERSON_COLLABORATORS,
        rootValue=entity_id,
        excludeCategories=EXCLUDE_CATEGORIES,
        limit=max_collaborators,
    )
    return format_people(collaborators)

def get_publications(
    entity_id: str,
    entity_type: str,
    max_publications: int,
    cursor: str | None = None,
) -> list[Publication]:
    """Return publications linked to either a person or organization entity."""
    publications = run_type_query(
        entity_id,
        entity_type,
        person_query=PERSON_PUBLICATIONS,
        person_params={
            "rootValue": entity_id,
            "excludeCategories": EXCLUDE_CATEGORIES,
            "limit": max_publications,
        },
        organization_query=ORG_PUBLICATIONS,
        organization_params={
            "entityId": entity_id,
            "excludeCategories": EXCLUDE_CATEGORIES,
            "limit": max_publications,
        },
    )
    return format_publications(publications)

def get_organizations(
    entity_id: str,
    entity_type: str,
    max_organizations: int,
    cursor: str | None = None,
) -> list[Organization]:
    """Return organizations linked to the entity using type-specific queries."""
    organizations = run_type_query(
        entity_id,
        entity_type,
        person_query=PERSON_ORGANIZATIONS,
        person_params={
            "rootValue": entity_id,
            "limit": max_organizations,
        },
        organization_query=ORG_RELATED_ORGS,
        organization_params={
            "entityId": entity_id,
            "limit": max_organizations,
        },
    )
    return format_organizations(organizations)

def get_members(
    entity_id: str,
    entity_type: str,
    max_members: int,
    cursor: str | None = None,
) -> list[Member]:
    """Return members for organization entities; person entities return none."""
    validate_entity_type(entity_type)

    if entity_type == "person":
        return []

    members = run_query(
        entity_id,
        ORG_MEMBERS,
        entityId=entity_id,
        limit=max_members,
    )
    return format_people(members, as_members=True)

def get_connections(
    entity_id: str,
    entity_type: str,
    max_publications: int = 50,
    max_collaborators: int = 50,
    max_organizations: int = 50,
    max_members: int = 50,
) -> ConnectionsPayload:
    """Route to the correct connection fetcher based on entity type.

    Pattern: Facade — callers don't need to know about person vs organization retrieval."""
    validate_entity_type(entity_type)

    try:
        if entity_type == "person":
            return person_connections(entity_id, max_publications, max_collaborators, max_organizations)
        return organization_connections(entity_id, max_publications, max_organizations, max_members)
    except ConnectionsError:
        raise
    except Exception as exception:
        log.error("Connections query failed for entity_id=%r", entity_id)
        raise ConnectionsError("Connections query failed") from exception
