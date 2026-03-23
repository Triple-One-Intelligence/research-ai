"""Utilities for retrieving and formatting entity connections from the Ricgraph database."""

import base64
import json
import logging
from collections.abc import Callable
from typing import Any, Literal, TypeVar, TypedDict

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

class InvalidCursorError(ValueError):
    pass

EntityType = Literal["person", "organization"]
VALID_ENTITY_TYPES: set[EntityType] = {"person", "organization"}
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
        log.exception("Connections query failed for entity_id=%r", entity_id)
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

def publication_sort_key(title: str | None, doi: str) -> str:
    """Build the same sort key used by publication Cypher queries."""
    normalized_title = (title or "").strip()
    return f"title:{normalized_title.lower()}" if normalized_title else f"doi:{doi}"

def encode_cursor(payload: dict[str, Any]) -> str:
    """Encode cursor payload as URL-safe base64 JSON."""
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")


def decode_cursor(cursor: str | None, required_keys: tuple[str, ...]) -> dict[str, str]:
    """Decode cursor payload and return validated string keys only."""
    if not cursor:
        return {}
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode((cursor + padding).encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exception:
        raise InvalidCursorError("Invalid pagination cursor") from exception
    if not isinstance(payload, dict):
        raise InvalidCursorError("Invalid pagination cursor")
    values: dict[str, str] = {}
    for key in required_keys:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise InvalidCursorError("Invalid pagination cursor")
        values[key] = value
    return values

def encode_publication_cursor(title: str | None, doi: str) -> str:
    """Encode publication cursor payload."""
    payload = {"sort_key": publication_sort_key(title, doi), "doi": doi}
    return encode_cursor(payload)

def decode_publication_cursor(cursor: str | None) -> tuple[str | None, str | None]:
    """Decode publication cursor payload; return empty tuple values on invalid input."""
    payload = decode_cursor(cursor, ("sort_key", "doi"))
    return payload.get("sort_key"), payload.get("doi")

def encode_people_cursor(name: str, author_id: str) -> str:
    """Encode people cursor payload for alphabetical pagination."""
    payload = {"name": name, "author_id": author_id}
    return encode_cursor(payload)

def decode_people_cursor(cursor: str | None) -> tuple[str | None, str | None]:
    """Decode people cursor payload; return empty tuple values on invalid input."""
    payload = decode_cursor(cursor, ("name", "author_id"))
    return payload.get("name"), payload.get("author_id")

def encode_organization_cursor(name: str, organization_id: str) -> str:
    """Encode organization cursor payload for alphabetical pagination."""
    payload = {"name": name.lower(), "organization_id": organization_id}
    return encode_cursor(payload)

def decode_organization_cursor(cursor: str | None) -> tuple[str | None, str | None]:
    """Decode organization cursor payload; return empty tuple values on invalid input."""
    payload = decode_cursor(cursor, ("name", "organization_id"))
    return payload.get("name"), payload.get("organization_id")

def extract_next_cursor(
    items: list[Any],
    limit: int,
    *,
    id_attr: str,
    encode: Callable[..., str],
    name_attr: str | None = None,
    fallback_name_attr: str | None = None,
) -> str | None:
    """Build next-page cursor when we have an extra row (limit+1 strategy)."""
    if not items or len(items) <= limit or limit < 1:
        return None

    last_item = items[limit - 1]
    item_id = getattr(last_item, id_attr, None)
    if not isinstance(item_id, str) or not item_id:
        return None

    if name_attr is None:
        return encode(item_id)

    name = getattr(last_item, name_attr, None)
    if (not isinstance(name, str) or not name) and fallback_name_attr:
        fallback_name = getattr(last_item, fallback_name_attr, None)
        name = fallback_name if isinstance(fallback_name, str) else None
    if not isinstance(name, str):
        return None

    return encode(name, item_id)

def extract_people_next_cursor(people: list[Any], limit: int) -> str | None:
    """Build next-page cursor for people/member lists."""
    return extract_next_cursor(
        people,
        limit,
        id_attr="author_id",
        name_attr="sort_name",
        fallback_name_attr="name",
        encode=encode_people_cursor,
    )

def extract_organization_next_cursor(organizations: list[Organization], limit: int) -> str | None:
    """Build next-page cursor for organization lists."""
    return extract_next_cursor(
        organizations,
        limit,
        id_attr="organization_id",
        name_attr="name",
        encode=encode_organization_cursor,
    )

def extract_publication_next_cursor(publications: list[Publication], limit: int) -> str | None:
    """Build next-page cursor for publication lists."""
    return extract_next_cursor(
        publications,
        limit,
        id_attr="doi",
        name_attr="title",
        encode=encode_publication_cursor,
    )

T = TypeVar("T")
def trim_page(items: list[T], limit: int) -> list[T]:
    """Trim a limit+1 page back to limit items for response payloads."""
    if limit < 1:
        return []
    return items[:limit]

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
        sort_name = row.get("sort_name") if isinstance(row.get("sort_name"), str) else None
        if as_members:
            out.append(Member(author_id=row["author_id"], name=name, sort_name=sort_name))
        else:
            out.append(Person(author_id=row["author_id"], name=name, sort_name=sort_name))
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
    """Convert publication rows into Publication models preserving query order."""
    publications: list[Publication] = []
    for row in rows:
        publications.append(Publication(
            doi=row["doi"],
            title=clean_title(row.get("title")),
            year=parse_year(row.get("year")),
            category=row.get("category"),
            versions=normalize_versions(row.get("versions")),
        ))
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

    cursor_name, cursor_author_id = decode_people_cursor(cursor)
    collaborators = run_query(
        entity_id,
        PERSON_COLLABORATORS,
        rootValue=entity_id,
        excludeCategories=EXCLUDE_CATEGORIES,
        limit=max_collaborators,
        cursorName=cursor_name,
        cursorAuthorId=cursor_author_id,
    )
    return format_people(collaborators)

def get_publications(
    entity_id: str,
    entity_type: str,
    max_publications: int,
    cursor: str | None = None,
) -> list[Publication]:
    """Return publications linked to either a person or organization entity."""
    cursor_key, cursor_doi = decode_publication_cursor(cursor)
    publications = run_type_query(
        entity_id,
        entity_type,
        person_query=PERSON_PUBLICATIONS,
        person_params={
            "rootValue": entity_id,
            "excludeCategories": EXCLUDE_CATEGORIES,
            "limit": max_publications,
            "cursorKey": cursor_key,
            "cursorDoi": cursor_doi,
        },
        organization_query=ORG_PUBLICATIONS,
        organization_params={
            "entityId": entity_id,
            "excludeCategories": EXCLUDE_CATEGORIES,
            "limit": max_publications,
            "cursorKey": cursor_key,
            "cursorDoi": cursor_doi,
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
    cursor_name, cursor_organization_id = decode_organization_cursor(cursor)
    organizations = run_type_query(
        entity_id,
        entity_type,
        person_query=PERSON_ORGANIZATIONS,
        person_params={
            "rootValue": entity_id,
            "limit": max_organizations,
            "cursorName": cursor_name,
            "cursorOrganizationId": cursor_organization_id,
        },
        organization_query=ORG_RELATED_ORGS,
        organization_params={
            "entityId": entity_id,
            "limit": max_organizations,
            "cursorName": cursor_name,
            "cursorOrganizationId": cursor_organization_id,
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

    cursor_name, cursor_author_id = decode_people_cursor(cursor)
    members = run_query(
        entity_id,
        ORG_MEMBERS,
        entityId=entity_id,
        limit=max_members,
        cursorName=cursor_name,
        cursorAuthorId=cursor_author_id,
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
    """Route to the correct connection fetcher based on entity type."""
    validate_entity_type(entity_type)
    if entity_type == "person":
        return person_connections(entity_id, max_publications, max_collaborators, max_organizations)
    return organization_connections(entity_id, max_publications, max_organizations, max_members)
