"""Router for entity connection endpoints backed by the Ricgraph database."""

import logging
from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Query, HTTPException
from app.utils.schemas import (
    Connections,
    CollaboratorsResponse,
    PublicationsResponse,
    OrganizationsResponse,
    MembersResponse,
)
from app.utils.ricgraph_utils.connections_utils import (
    get_connections,
    get_collaborators as get_collaborators_list,
    get_publications as get_publications_list,
    get_organizations as get_organizations_list,
    get_members as get_members_list,
    InvalidEntityTypeError,
    ConnectionsError,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/connections")
T = TypeVar("T")

def run_connections_action(entity_id: str, action: Callable[[], T]) -> T:
    """Map connections service exceptions to HTTP errors."""
    try:
        return action()
    except InvalidEntityTypeError as exception:
        raise HTTPException(status_code=400, detail=str(exception))
    except ConnectionsError:
        log.error("Connections service error for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")
    except Exception:
        log.error("Unexpected error while handling connections for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")

def extract_next_cursor(items: list[object], limit: int, field_name: str) -> str | None:
    """Return the next cursor field when current page is full."""
    if not items or len(items) != limit:
        return None
    return getattr(items[-1], field_name, None)

@router.get("/entity", response_model=Connections)
def get_entity_connections(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    max_publications: int = Query(50, ge=1, le=200, description="Maximum number of publications to return"),
    max_collaborators: int = Query(50, ge=1, le=200, description="Maximum number of collaborators to return"),
    max_organizations: int = Query(50, ge=1, le=200, description="Maximum number of organizations to return"),
    max_members: int = Query(50, ge=1, le=200, description="Maximum number of members to return"),
):
    """Return connections for a given entity using the Ricgraph database.

    Query parameters are converted and passed to the ricgraph service
    implementation in `app.utils.ricgraph_utils.connections_utils`.
    """
    result = run_connections_action(
        entity_id,
        lambda: get_connections(
            entity_id=entity_id,
            entity_type=entity_type,
            max_publications=max_publications,
            max_collaborators=max_collaborators,
            max_organizations=max_organizations,
            max_members=max_members,
        ),
    )
    return Connections(**{**result, "entity_id": entity_id, "entity_type": entity_type})


@router.get("/collaborators", response_model=CollaboratorsResponse)
def get_collaborators(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of collaborators to return"),
    cursor: str | None = Query(None, description="Pagination cursor"),
):
    """Return collaborator connections for a given entity."""
    collaborators = run_connections_action(
        entity_id,
        lambda: get_collaborators_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_collaborators=limit,
            cursor=cursor,
        ),
    )
    return CollaboratorsResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        collaborators=collaborators,
        next_cursor=extract_next_cursor(collaborators, limit, "author_id"),
    )


@router.get("/publications", response_model=PublicationsResponse)
def get_publications(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of publications to return"),
    cursor: str | None = Query(None, description="Pagination cursor"),
):
    """Return publication connections for a given entity."""
    publications = run_connections_action(
        entity_id,
        lambda: get_publications_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_publications=limit,
            cursor=cursor,
        ),
    )
    return PublicationsResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        publications=publications,
        next_cursor=extract_next_cursor(publications, limit, "doi"),
    )


@router.get("/organizations", response_model=OrganizationsResponse)
def get_organizations(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of organizations to return"),
    cursor: str | None = Query(None, description="Pagination cursor"),
):
    """Return organization connections for a given entity."""
    organizations = run_connections_action(
        entity_id,
        lambda: get_organizations_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_organizations=limit,
            cursor=cursor,
        ),
    )
    return OrganizationsResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        organizations=organizations,
        next_cursor=extract_next_cursor(organizations, limit, "organization_id"),
    )


@router.get("/members", response_model=MembersResponse)
def get_members(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of members to return"),
    cursor: str | None = Query(None, description="Pagination cursor"),
):
    """Return member connections for a given organization entity."""
    members = run_connections_action(
        entity_id,
        lambda: get_members_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_members=limit,
            cursor=cursor,
        ),
    )
    return MembersResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        members=members,
        next_cursor=extract_next_cursor(members, limit, "author_id"),
    )
