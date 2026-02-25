from fastapi import APIRouter, Query
from app.utils.schemas import Person, Publication, Organization
from app.utils.schemas.connections import ConnectionsResponse, Member
from app.utils.ricgraph.connections import (
    fetch_publications,
    fetch_collaborators,
    fetch_organizations,
    fetch_members,
)

router = APIRouter(prefix="/connections")


@router.get("/entity", response_model=ConnectionsResponse)
def get_entity_connections(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
):
    """Return connections for a given entity from Ricgraph."""
    pubs = fetch_publications(entity_id)
    publications = [Publication(**p) for p in pubs]
    orgs_raw = fetch_organizations(entity_id)
    organizations = [Organization(**o) for o in orgs_raw]

    if entity_type == "organization":
        mems = fetch_members(entity_id)
        members = [Member(**m) for m in mems]
        return ConnectionsResponse(
            entity_id=entity_id,
            entity_type=entity_type,
            collaborators=[],
            publications=publications,
            organizations=organizations,
            members=members,
        )

    collabs = fetch_collaborators(entity_id)
    collaborators = [Person(**c) for c in collabs]
    return ConnectionsResponse(
        entity_id=entity_id,
        entity_type=entity_type,
        collaborators=collaborators,
        publications=publications,
        organizations=organizations,
        members=[],
    )
