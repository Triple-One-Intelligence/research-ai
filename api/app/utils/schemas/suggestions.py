from typing import List

from pydantic import BaseModel

from .organization import Organization
from .person import Person


class Suggestions(BaseModel):
    """Autocomplete suggestions containing persons and organizations"""

    persons: List[Person]
    organizations: List[Organization]
