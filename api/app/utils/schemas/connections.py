from pydantic import BaseModel

from .organization import Organization
from .person import Person
from .publication import Publication


class Member(BaseModel):
    """A person who is a member of an organization."""
    author_id: str
    name: str

class Connections(BaseModel):
    entity_id: str
    entity_type: str
    collaborators: list[Person]
    publications: list[Publication]
    organizations: list[Organization]
    members: list[Member]
