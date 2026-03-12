"""Router for entity connection endpoints backed by the Ricgraph database."""

import logging

from fastapi import APIRouter, Query, HTTPException
from app.utils.schemas import Connections
from app.utils.ricgraph_utils.connections_utils import get_connections, InvalidEntityTypeError, ConnectionsError

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
