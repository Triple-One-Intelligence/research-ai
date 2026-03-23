from typing import Any, TypedDict

from app.utils.schemas import Person, Publication, Organization
from app.utils.schemas.connections import Member
from app.utils.database_utils import database_utils
from app.utils.ricgraph_utils.queries.connections_queries import (
    PERSON_PUBLICATIONS,
    PERSON_COLLABORATORS,
    PERSON_ORGANIZATIONS,
    ORG_MEMBERS,
    ORG_PUBLICATIONS,
    ORG_RELATED_ORGS,
)

from .constants import EXCLUDE_CATEGORIES, validate_entity_type, ConnectionsError
from .formatters import format_people, format_publications, format_organizations
from .pagination import decode_cursor_pair

class ConnectionsPayload(TypedDict):
    collaborators: list[Person]
    publications: list[Publication]
    organizations: list[Organization]
    members: list[Member]

def run_query(query: str, **params: Any) -> list[dict[str, Any]]:
    """Execute a single graph query with unified error handling."""
    try:
        return database_utils.execute_cypher(query, **params)
    except Exception as exception:
        raise ConnectionsError("Connections query failed") from exception

def run_type_query(
    entity_type: str,
    *,
    person_query: str,
    person_params: dict[str, Any],
    organization_query: str,
    organization_params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute the person/org specific query after validating entity type."""
    validate_entity_type(entity_type)
    # Keep person/org query selection centralized so endpoint helpers stay small.
    if entity_type == "person":
        return run_query(person_query, **person_params)
    return run_query(organization_query, **organization_params)

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

def get_collaborators(
    entity_id: str,
    entity_type: str,
    max_collaborators: int,
    cursor: str | None = None,
) -> list[Person]:
    """Return collaborators for person entities; organizations have none."""
    validate_entity_type(entity_type)

    # Collaborators are only defined for person roots in this API.
    if entity_type == "organization":
        return []

    cursor_name, cursor_author_id = decode_cursor_pair(cursor, "name", "author_id")
    collaborators = run_query(
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
    cursor_key, cursor_doi = decode_cursor_pair(cursor, "sort_key", "doi")
    publications = run_type_query(
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
    cursor_name, cursor_organization_id = decode_cursor_pair(cursor, "name", "organization_id")
    organizations = run_type_query(
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

    # Members are only defined for organization roots in this API.
    if entity_type == "person":
        return []

    cursor_name, cursor_author_id = decode_cursor_pair(cursor, "name", "author_id")
    members = run_query(
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
