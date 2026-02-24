from pydantic import BaseModel
from typing import List, Optional
from .person import Person
from .publication import Publication
from .organization import Organization


class Member(BaseModel):
    """A person who is a member of an organization, with optional role."""
    author_id: str
    name: str
    role: Optional[str] = None


class ConnectionsResponse(BaseModel):
    entity_id: str
    entity_type: str
    collaborators: List[Person]
    publications: List[Publication]
    organizations: List[Organization]
    members: List[Member]


# Kept for backward compatibility with existing /connections/person/{id} endpoint
class Connections(BaseModel):
    persons: List[Person]
    publications: List[Publication]
    organizations: List[Organization]
