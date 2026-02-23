from pydantic import BaseModel

class Suggestions(BaseModel):
    """Autocomplete suggestions containing persons and organizations"""
    persons: List[Person]
    organizations: List[Organization]