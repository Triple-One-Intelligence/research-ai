from pydantic import BaseModel
from typing import List
from .person import Person
from .publication import Publication
from .organization import Organization

class Member(BaseModel):
    """A person who is a member of an organization."""
    author_id: str
    name: str

class Connections(BaseModel):
    entity_id: str
    entity_type: str
    collaborators: List[Person]
    publications: List[Publication]
    organizations: List[Organization]
    members: List[Member]
