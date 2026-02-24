# this file deals with API endpoints whose responses need Ricgraph
# (e.g. to return all connections between a person and their publications)

from fastapi import APIRouter, Query
from app.utils.schemas import Person, Publication, Organization, Connections
from app.utils.schemas.connections import ConnectionsResponse, Member


# these endpoints can be reached using the /connections URL prefix
router = APIRouter(prefix="/connections")


# ---------------------------------------------------------------------------
# Mock data — replace with real Ricgraph queries later
# ---------------------------------------------------------------------------

_MOCK_PERSON = ConnectionsResponse(
    entity_id="",
    entity_type="person",
    collaborators=[
        Person(author_id="person-2", name="Jansen, B."),
        Person(author_id="person-3", name="De Vries, C.M."),
        Person(author_id="person-4", name="Van den Berg, D."),
    ],
    publications=[
        Publication(
            doi="10.1234/example-001",
            title="Machine Learning in Academic Research",
            year=2024,
            category="journal-article",
            name="Jansen, B.",
        ),
        Publication(
            doi="10.1234/example-002",
            title="Graph-Based Knowledge Discovery",
            year=2023,
            category="conference-paper",
            name="De Vries, C.M.",
        ),
        Publication(
            doi="10.1234/example-003",
            title="Open Science and FAIR Data Principles",
            year=2023,
            category="journal-article",
        ),
    ],
    organizations=[
        Organization(organization_id="org-1", name="Utrecht University"),
        Organization(organization_id="org-2", name="Department of Information and Computing Sciences"),
    ],
    members=[],
)

_MOCK_ORG = ConnectionsResponse(
    entity_id="",
    entity_type="organization",
    collaborators=[],
    publications=[
        Publication(
            doi="10.1234/example-004",
            title="Annual Report on Research Output 2024",
            year=2024,
            category="report",
        ),
        Publication(
            doi="10.1234/example-005",
            title="Collaborative Research in the Netherlands",
            year=2023,
            category="journal-article",
        ),
    ],
    organizations=[
        Organization(organization_id="org-3", name="SURF"),
        Organization(organization_id="org-4", name="NWO"),
    ],
    members=[
        Member(author_id="person-1", name="De Groot, A.", role="Professor"),
        Member(author_id="person-2", name="Jansen, B.", role="PhD Candidate"),
        Member(author_id="person-3", name="De Vries, C.M.", role="Postdoc"),
    ],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/entity", response_model=ConnectionsResponse)
def get_entity_connections(
    entity_id: str = Query(..., description="ID of the entity"),
    entity_type: str = Query(..., description="'person' or 'organization'"),
):
    """
    Return connections for a given entity.
    Currently returns hardcoded mock data — will be replaced with real Ricgraph queries.
    """
    if entity_type == "organization":
        return _MOCK_ORG.model_copy(update={"entity_id": entity_id})
    return _MOCK_PERSON.model_copy(update={"entity_id": entity_id})


@router.get("/person/{author_id}", response_model=Connections)
def get_person_connections(author_id: str):
    return Connections(persons=[], publications=[], organizations=[])
