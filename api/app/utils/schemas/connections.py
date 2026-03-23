from pydantic import BaseModel, Field

from .organization import Organization
from .person import Person
from .publication import Publication


class Member(BaseModel):
    """A person who is a member of an organization."""
    author_id: str
    name: str
    sort_name: str | None = Field(default=None, exclude=True)

class Connections(BaseModel):
    entity_id: str
    entity_type: str
    collaborators: list[Person]
    publications: list[Publication]
    organizations: list[Organization]
    members: list[Member]
    collaborators_cursor: str | None = None
    publications_cursor: str | None = None
    organizations_cursor: str | None = None
    members_cursor: str | None = None


class CollaboratorsResponse(BaseModel):
    entity_id: str
    entity_type: str
    collaborators: list[Person]
    cursor: str | None = None


class PublicationsResponse(BaseModel):
    entity_id: str
    entity_type: str
    publications: list[Publication]
    cursor: str | None = None


class OrganizationsResponse(BaseModel):
    entity_id: str
    entity_type: str
    organizations: list[Organization]
    cursor: str | None = None


class MembersResponse(BaseModel):
    entity_id: str
    entity_type: str
    members: list[Member]
    cursor: str | None = None
