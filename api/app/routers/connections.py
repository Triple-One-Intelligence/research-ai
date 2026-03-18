"""Router for entity connection endpoints backed by the Ricgraph database."""

import logging

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
    try:
        result = get_connections(
            entity_id=entity_id,
            entity_type=entity_type,
            max_publications=max_publications,
            max_collaborators=max_collaborators,
            max_organizations=max_organizations,
            max_members=max_members,
        )
        # Build response model
        return Connections(**{**result, "entity_id": entity_id, "entity_type": entity_type})
    except InvalidEntityTypeError as exception:
        raise HTTPException(status_code=400, detail=str(exception))
    except ConnectionsError:
        log.error("Connections service error for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")
    except Exception:
        log.error("Unexpected error while handling connections for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")


@router.get("/collaborators", response_model=CollaboratorsResponse)
def get_collaborators(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of collaborators to return"),
    cursor: str | None = Query(None, description="Pagination cursor (ignored for now)"),
):
    """Return collaborator connections for a given entity."""
    try:
        collaborators = get_collaborators_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_collaborators=limit,
            cursor=cursor,
        )
        next_cursor = collaborators[-1].author_id if collaborators and len(collaborators) == limit else None
        return CollaboratorsResponse(
            entity_id=entity_id,
            entity_type=entity_type,
            collaborators=collaborators,
            next_cursor=next_cursor,
        )
    except InvalidEntityTypeError as exception:
        raise HTTPException(status_code=400, detail=str(exception))
    except ConnectionsError:
        log.error("Connections service error for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")
    except Exception:
        log.error("Unexpected error while handling collaborators for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")


@router.get("/publications", response_model=PublicationsResponse)
def get_publications(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of publications to return"),
    cursor: str | None = Query(None, description="Pagination cursor (ignored for now)"),
):
    """Return publication connections for a given entity."""
    try:
        publications = get_publications_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_publications=limit,
            cursor=cursor,
        )
        next_cursor = publications[-1].doi if publications and len(publications) == limit else None
        return PublicationsResponse(
            entity_id=entity_id,
            entity_type=entity_type,
            publications=publications,
            next_cursor=next_cursor,
        )
    except InvalidEntityTypeError as exception:
        raise HTTPException(status_code=400, detail=str(exception))
    except ConnectionsError:
        log.error("Connections service error for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")
    except Exception:
        log.error("Unexpected error while handling publications for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")


@router.get("/organizations", response_model=OrganizationsResponse)
def get_organizations(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of organizations to return"),
    cursor: str | None = Query(None, description="Pagination cursor (ignored for now)"),
):
    """Return organization connections for a given entity."""
    try:
        organizations = get_organizations_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_organizations=limit,
            cursor=cursor,
        )
        next_cursor = organizations[-1].organization_id if organizations and len(organizations) == limit else None
        return OrganizationsResponse(
            entity_id=entity_id,
            entity_type=entity_type,
            organizations=organizations,
            next_cursor=next_cursor,
        )
    except InvalidEntityTypeError as exception:
        raise HTTPException(status_code=400, detail=str(exception))
    except ConnectionsError:
        log.error("Connections service error for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")
    except Exception:
        log.error("Unexpected error while handling organizations for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")


@router.get("/members", response_model=MembersResponse)
def get_members(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of members to return"),
    cursor: str | None = Query(None, description="Pagination cursor (ignored for now)"),
):
    """Return member connections for a given organization entity."""
    try:
        members = get_members_list(
            entity_id=entity_id,
            entity_type=entity_type,
            max_members=limit,
            cursor=cursor,
        )
        next_cursor = members[-1].author_id if members and len(members) == limit else None
        return MembersResponse(
            entity_id=entity_id,
            entity_type=entity_type,
            members=members,
            next_cursor=next_cursor,
        )
    except InvalidEntityTypeError as exception:
        raise HTTPException(status_code=400, detail=str(exception))
    except ConnectionsError:
        log.error("Connections service error for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")
    except Exception:
        log.error("Unexpected error while handling members for entity_id=%r", entity_id)
        raise HTTPException(status_code=500, detail="Connections query failed.")
