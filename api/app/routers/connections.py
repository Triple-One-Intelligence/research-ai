# this file deals with API endpoints whose responses need Ricgraph
# (e.g. to return all connections between a person and their publications)

from app.utils.schemas import Connections
from fastapi import APIRouter

# these endpoints can be reached using the /connections URL prefix
router = APIRouter(prefix="/connections")


@router.get("/entity", response_model=Connections)
def get_person_connections(entity_id: str, entity_type: str):
    return Connections(entity_id=entity_id, entity_type=entity_type)


# @router.get("/organization/{organization_id}", response_model=Connections)
# def get_person_publication_connections(organization_id: str):
#     return fetch_collaborators(organization_id)
