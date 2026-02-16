from pydantic import BaseModel
from typing import List
from .person import Person
from .publication import Publication
from .organization import Organization

class Connections(BaseModel):
    persons: List[Person]
    publications: List[Publication]
    organizations: List[Organization]